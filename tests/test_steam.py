import io
import json
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from steam_analytics.steam import SteamClient, SteamError

STEAMID = "76561198000000001"


def response(payload):
    return io.BytesIO(json.dumps(payload).encode())


def test_owned_games_uses_service_json_and_preserves_unknown_playtime():
    opener = Mock(
        return_value=response(
            {
                "response": {
                    "game_count": 2,
                    "games": [
                        {"appid": 20, "name": "Zelda", "playtime_forever": 90},
                        {"appid": 10, "name": "Alpha"},
                    ],
                }
            }
        )
    )
    games = SteamClient("secret", opener=opener).owned_games(STEAMID)
    request = opener.call_args.args[0]
    query = parse_qs(urlsplit(request.full_url).query)
    assert urlsplit(request.full_url).hostname == "api.steampowered.com"
    assert json.loads(query["input_json"][0]) == {
        "steamid": STEAMID,
        "include_appinfo": True,
        "include_played_free_games": True,
    }
    assert [g["appid"] for g in games] == [10, 20]
    assert games[0]["playtime_forever"] is None
    assert games[1]["playtime_hours"] == 1.5


@pytest.mark.parametrize(
    "payload",
    [
        {"response": {}},
        {"response": {"game_count": 2, "games": []}},
        {"response": {"game_count": 1, "games": [{"appid": "bad"}]}},
        {"response": {"game_count": 2, "games": [{"appid": 1}, {"appid": 1}]}},
        {"response": {"game_count": 1, "games": [{"appid": 1, "playtime_forever": -1}]}},
        {"response": []},
    ],
)
def test_unavailable_or_malformed_library_is_not_empty(payload):
    with pytest.raises(SteamError):
        SteamClient("secret", opener=Mock(return_value=response(payload))).owned_games(STEAMID)


def test_explicit_empty_library_is_valid():
    assert (
        SteamClient("secret", opener=Mock(return_value=response({"response": {"game_count": 0}}))).owned_games(STEAMID)
        == []
    )


@pytest.mark.parametrize("profile", [STEAMID, f"https://steamcommunity.com/profiles/{STEAMID}/"])
def test_numeric_profile_does_not_require_resolution(profile):
    opener = Mock()
    assert SteamClient("secret", opener=opener).resolve_profile(profile) == STEAMID
    opener.assert_not_called()


def test_vanity_profile_resolution():
    opener = Mock(return_value=response({"response": {"success": 1, "steamid": STEAMID}}))
    assert (
        SteamClient("secret", opener=opener).resolve_profile("https://steamcommunity.com/id/cidosilvestre/") == STEAMID
    )
    assert parse_qs(urlsplit(opener.call_args.args[0].full_url).query)["vanityurl"] == ["cidosilvestre"]


@pytest.mark.parametrize(
    "profile",
    ["https://evil.example/id/bruno", "https://[invalid", "../secret", "https://steamcommunity.com/profiles/bad"],
)
def test_invalid_profile_is_rejected_without_network(profile):
    opener = Mock()
    with pytest.raises(SteamError):
        SteamClient("secret", opener=opener).resolve_profile(profile)
    opener.assert_not_called()


def test_transient_error_is_retried():
    opener = Mock(side_effect=[URLError("secret URL"), response({"response": {"game_count": 0}})])
    sleep = Mock()
    assert SteamClient("secret", opener=opener, sleep=sleep).owned_games(STEAMID) == []
    assert opener.call_count == 2
    sleep.assert_called_once_with(1)


def test_auth_error_does_not_expose_secret_or_retry():
    opener = Mock(side_effect=HTTPError("https://example/?key=secret", 403, "secret", {}, None))
    with pytest.raises(SteamError) as error:
        SteamClient("secret", opener=opener).owned_games(STEAMID)
    assert "secret" not in str(error.value)
    assert opener.call_count == 1


def test_invalid_json_is_a_safe_error():
    with pytest.raises(SteamError, match="JSON inválida"):
        SteamClient("secret", opener=Mock(return_value=io.BytesIO(b"<html>secret</html>"))).owned_games(STEAMID)


def test_achievement_progress_comes_from_playerstats():
    payload = {
        "playerstats": {
            "success": True,
            "achievements": [
                {"apiname": "A", "name": "Começar", "achieved": 1},
                {"apiname": "B", "achieved": 0},
            ],
        }
    }
    result = SteamClient("secret", opener=Mock(return_value=response(payload))).player_achievements(STEAMID, 1)
    assert result["percent"] == 50
    assert result["unlocked"] == 1
    assert result["complete"] is False
    assert result["items"][1]["name"] == "B"


@pytest.mark.parametrize(
    "stats",
    [
        {"success": False},
        {"success": True},
        {"success": True, "achievements": [{"apiname": "A", "achieved": "1"}]},
        {"success": True, "achievements": [{"apiname": "A", "achieved": 1}] * 2},
    ],
)
def test_missing_or_invalid_achievements_are_not_zero_percent(stats):
    with pytest.raises(SteamError):
        SteamClient("secret", opener=Mock(return_value=response({"playerstats": stats}))).player_achievements(
            STEAMID, 1
        )


def test_empty_achievement_list_is_not_a_completed_game():
    result = SteamClient(
        "secret",
        opener=Mock(
            return_value=response(
                {
                    "playerstats": {
                        "success": True,
                        "achievements": [],
                    }
                }
            )
        ),
    ).player_achievements(STEAMID, 1)
    assert result["total"] == 0
    assert result["percent"] is None
    assert result["complete"] is False
