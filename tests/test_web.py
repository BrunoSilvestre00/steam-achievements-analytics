from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from steam_analytics.service import LibraryService
from steam_analytics.steam import SteamError, normalize_game
from steam_analytics.storage import load_library, save_library
from steam_analytics.web import create_app

STEAMID = "76561198000000001"
OTHER_ID = "76561198000000002"
GAMES = [
    normalize_game(g)
    for g in [
        {"appid": 1, "name": "Alpha", "playtime_forever": 0},
        {"appid": 2, "name": "Portal", "playtime_forever": 150, "rtime_last_played": 123},
        {"appid": 3, "name": "Unknown <script>alert(1)</script>"},
    ]
]


@pytest.fixture
def setup(tmp_path):
    steam = Mock()
    steam.owned_games.return_value = GAMES
    steam.player_achievements.return_value = {
        "available": True,
        "total": 2,
        "unlocked": 1,
        "percent": 50.0,
        "complete": False,
        "error": None,
        "items": [
            {"apiname": "FIRST", "name": "First step", "description": "Start", "unlocked": True},
            {"apiname": "LAST", "name": "Last step", "description": "Finish", "unlocked": False},
        ],
    }
    service = LibraryService("secret-never-rendered", tmp_path / "steam.sqlite3", client=steam)
    service.hltb_client = Mock()
    service.hltb_client.search.side_effect = Exception("offline test")
    with TestClient(create_app(service=service)) as client:
        yield client, service, steam


def test_home_and_profile_form_redirect(setup):
    client, _, steam = setup
    assert client.get("/").status_code == 200
    result = client.get("/profile", params={"profile": STEAMID}, follow_redirects=False)
    assert result.status_code == 303
    assert result.headers["location"] == f"/profile/{STEAMID}"
    steam.owned_games.assert_not_called()


def test_custom_profile_link_redirects_to_numeric_id(setup, monkeypatch):
    client, _, steam = setup
    from steam_analytics.steam import SteamClient

    resolve = Mock(return_value=STEAMID)
    monkeypatch.setattr(SteamClient, "resolve_profile", resolve)
    result = client.get(
        "/profile", params={"profile": "https://steamcommunity.com/id/cidosilvestre/"}, follow_redirects=False
    )
    assert result.status_code == 303
    assert result.headers["location"] == f"/profile/{STEAMID}"
    resolve.assert_called_once_with("https://steamcommunity.com/id/cidosilvestre/")
    steam.owned_games.assert_not_called()


def test_missing_key_keeps_custom_profile_input_and_workspace(tmp_path):
    with TestClient(create_app(service=LibraryService("", tmp_path / "empty.db"))) as client:
        result = client.get("/profile", params={"profile": "https://steamcommunity.com/id/cidosilvestre/"})
        assert result.status_code == 503
        assert 'value="https://steamcommunity.com/id/cidosilvestre/"' in result.text
        assert 'role="alert"' in result.text


def test_profile_renders_real_response_and_escapes_external_names(setup):
    client, _, _ = setup
    result = client.get(f"/profile/{STEAMID}")
    assert result.status_code == 200
    assert "Portal" in result.text and "2,5" in result.text
    assert "&lt;script&gt;" in result.text
    assert "<script>" not in result.text
    assert "secret-never-rendered" not in result.text
    assert 'method="post"' in result.text
    assert 'data-selected-game="1"' in result.text
    assert "1 de 2 conquistas" in result.text


def test_search_filters_and_ordering_work_in_python(setup):
    client, _, _ = setup
    result = client.get(f"/profile/{STEAMID}", params={"q": "PORT", "played": "played"})
    assert "Portal" in result.text and ">Alpha<" not in result.text
    result = client.get(f"/profile/{STEAMID}", params={"played": "unplayed"})
    assert ">Alpha<" in result.text and ">Portal<" not in result.text
    assert "Unknown &lt;script&gt;" not in result.text
    result = client.get(f"/profile/{STEAMID}", params={"sort": "hours"})
    assert result.text.index(">Portal<") < result.text.index(">Alpha<")


def test_json_api_reuses_cache_without_exposing_key(setup):
    client, _, steam = setup
    first = client.get(f"/api/profile/{STEAMID}")
    second = client.get(f"/api/profile/{STEAMID}")
    assert first.json()["game_count"] == 3
    assert second.json()["cached"] is True
    assert second.headers["cache-control"] == "no-store"
    assert steam.owned_games.call_count == 1
    assert "secret-never-rendered" not in second.text


def test_refresh_replaces_snapshot_without_duplicates(setup):
    client, service, steam = setup
    client.get(f"/profile/{STEAMID}")
    steam.owned_games.return_value = [GAMES[1]]
    result = client.post(f"/profile/{STEAMID}/refresh")
    assert result.status_code == 200
    assert steam.owned_games.call_count == 2
    assert load_library(service.database, STEAMID)["game_count"] == 1
    assert ">Alpha<" not in result.text


def test_failed_refresh_preserves_saved_library(setup):
    client, service, steam = setup
    client.get(f"/profile/{STEAMID}")
    steam.owned_games.side_effect = SteamError("Biblioteca indisponível")
    result = client.post(f"/profile/{STEAMID}/refresh")
    assert result.status_code == 502
    assert "última biblioteca salva" in result.text
    assert load_library(service.database, STEAMID)["game_count"] == 3
    service.cache_seconds = 0
    result = client.get(f"/profile/{STEAMID}")
    assert result.status_code == 200
    assert "última biblioteca salva" in result.text
    assert ">Portal<" in result.text


def test_private_library_is_an_error_on_first_import(setup):
    client, service, steam = setup
    steam.owned_games.side_effect = SteamError("Detalhes dos jogos indisponíveis")
    assert client.get(f"/profile/{STEAMID}").status_code == 502
    assert load_library(service.database, STEAMID) is None
    assert "detail" in client.get(f"/api/profile/{STEAMID}").json()


def test_empty_library_is_rendered_as_success(setup):
    client, _, steam = setup
    steam.owned_games.return_value = []
    result = client.get(f"/profile/{STEAMID}")
    assert result.status_code == 200
    assert "Nenhum jogo retornado" in result.text


def test_no_search_results_is_distinct_from_empty_library(setup):
    client, _, _ = setup
    result = client.get(f"/profile/{STEAMID}", params={"q": "nonexistent"})
    assert "Nenhum jogo com esses filtros" in result.text


def test_invalid_id_does_not_call_steam(setup):
    client, _, steam = setup
    assert client.get("/profile/invalid").status_code == 422
    assert client.get("/api/profile/invalid").status_code == 422
    steam.owned_games.assert_not_called()


def test_missing_configuration_is_a_helpful_error(tmp_path):
    with TestClient(create_app(service=LibraryService("", tmp_path / "empty.db"))) as client:
        result = client.get(f"/profile/{STEAMID}")
        assert result.status_code == 503
        assert "STEAM_API_KEY" in result.text


def test_profiles_are_isolated_in_storage(setup):
    _, service, _ = setup
    service.get_library(STEAMID)
    save_library(service.database, OTHER_ID, [GAMES[0]], "2026-09-17T00:00:00+00:00")
    save_library(service.database, STEAMID, [], "2026-09-17T01:00:00+00:00")
    assert load_library(service.database, OTHER_ID)["game_count"] == 1
    assert load_library(service.database, STEAMID)["games"] == []


def test_game_selection_renders_only_requested_details(setup):
    client, _, steam = setup
    result = client.get(f"/profile/{STEAMID}", params={"game": 2})
    assert result.status_code == 200
    assert 'data-selected-game="2"' in result.text
    steam.player_achievements.assert_called_once_with(STEAMID, 2)
    result = client.get(f"/profile/{STEAMID}/games/1")
    assert result.status_code == 200
    assert "<html" not in result.text
    assert 'data-selected-game="1"' in result.text
    assert "header.jpg" in result.text
    assert steam.player_achievements.call_count == 2


def test_game_outside_library_is_not_queried(setup):
    client, _, steam = setup
    assert client.get(f"/profile/{STEAMID}/games/999").status_code == 404
    steam.player_achievements.assert_not_called()


def test_achievements_persist_across_service_restarts(setup):
    client, service, _ = setup
    client.get(f"/profile/{STEAMID}")
    offline_client = Mock()
    restarted = LibraryService("", service.database, client=offline_client)
    assert restarted.get_library(STEAMID)["game_count"] == 3
    assert restarted.achievements(STEAMID, 1)["unlocked"] == 1
    offline_client.owned_games.assert_not_called()
    offline_client.player_achievements.assert_not_called()


def test_unavailable_achievements_do_not_break_library(setup):
    client, _, steam = setup
    steam.player_achievements.side_effect = SteamError("Conquistas indisponíveis")
    result = client.get(f"/profile/{STEAMID}")
    assert result.status_code == 200
    assert "Conquistas indisponíveis" in result.text
    assert ">Portal<" in result.text


def test_percentage_sort_puts_unknown_last_in_both_directions(setup):
    import re
    from datetime import datetime, timezone

    from steam_analytics.storage import save_achievements

    client, service, steam = setup
    service.get_library(STEAMID)
    for appid, unlocked in [(1, False), (2, True)]:
        save_achievements(
            service.database,
            STEAMID,
            appid,
            {"items": [{"apiname": "A", "name": "Finish", "description": "", "unlocked": unlocked}]},
            datetime.now(timezone.utc).isoformat(),
        )
    for direction, order in [("percent_desc", [2, 1, 3]), ("percent_asc", [1, 2, 3])]:
        response = client.get(f"/profile/{STEAMID}", params={"sort": direction, "game": 2})
        assert response.status_code == 200
        assert [int(value) for value in re.findall(r'data-game="(\d+)"', response.text)] == order
        assert 'data-percent="0.0"' in response.text
        assert 'data-percent="100.0"' in response.text
        assert 'data-percent=""' in response.text
        assert "0/1 desbloqueadas" in response.text
        assert "1/1 desbloqueadas" in response.text
    steam.player_achievements.assert_not_called()


def test_progress_batches_are_bounded_and_saved(setup):
    client, service, steam = setup
    steam.owned_games.return_value = GAMES + [normalize_game({"appid": 4, "name": "Fourth"})]
    service.get_library(STEAMID)
    response = client.post(f"/api/profile/{STEAMID}/progress")
    assert response.status_code == 200
    assert steam.player_achievements.call_count == 3
    assert response.json()["pending"] == 1
    assert [game["percent"] for game in response.json()["games"]].count(50.0) == 3
    response = client.post(f"/api/profile/{STEAMID}/progress")
    assert response.json()["pending"] == 0
    assert steam.player_achievements.call_count == 4
    client.post(f"/api/profile/{STEAMID}/progress")
    client.get(f"/api/profile/{STEAMID}/progress")
    assert steam.player_achievements.call_count == 4


def test_unavailable_progress_is_cached_across_restart(setup):
    client, service, steam = setup
    service.get_library(STEAMID)
    steam.player_achievements.side_effect = SteamError("Sem estatísticas")
    result = client.post(f"/api/profile/{STEAMID}/progress").json()
    assert result["pending"] == 0
    assert all(game["percent"] is None and game["state"] == "unavailable" for game in result["games"])
    restarted = LibraryService("", service.database, client=Mock())
    assert restarted.progress(STEAMID, update=True)["pending"] == 0
    restarted.client.player_achievements.assert_not_called()


def test_empty_achievements_have_no_percentage(setup):
    client, service, steam = setup
    service.get_library(STEAMID)
    steam.player_achievements.return_value = {
        "available": True,
        "items": [],
        "total": 0,
        "unlocked": 0,
        "percent": None,
        "complete": False,
        "error": None,
    }
    result = client.post(f"/api/profile/{STEAMID}/progress").json()
    assert all(game["state"] == "empty" and game["percent"] is None for game in result["games"])
    response = client.get(f"/profile/{STEAMID}")
    assert "Sem conquistas" in response.text


def test_progress_requires_imported_profile(setup):
    client, _, steam = setup
    assert client.post(f"/api/profile/{OTHER_ID}/progress").status_code == 404
    assert client.get("/api/profile/bad/progress").status_code == 422
    steam.player_achievements.assert_not_called()


def test_filtering_and_game_selection_survive_percentage_sort(setup):
    client, service, _ = setup
    service.get_library(STEAMID)
    client.post(f"/api/profile/{STEAMID}/progress")
    response = client.get(f"/profile/{STEAMID}", params={"q": "port", "sort": "percent_desc", "game": 2})
    assert response.status_code == 200
    assert 'data-game="2"' in response.text and 'data-game="1"' not in response.text
    assert 'data-selected-game="2"' in response.text
    assert "q=port" in response.text and "sort=percent_desc" in response.text


def test_platinum_filters_use_saved_percentage(setup):
    client, service, _ = setup
    service.get_library(STEAMID)
    from datetime import datetime, timezone

    from steam_analytics.storage import save_achievements

    for appid, unlocked in [(1, 7), (2, 8), (3, 10)]:
        save_achievements(
            service.database,
            STEAMID,
            appid,
            {
                "items": [
                    {"apiname": str(n), "name": str(n), "description": "", "unlocked": n < unlocked} for n in range(10)
                ]
            },
            datetime.now(timezone.utc).isoformat(),
        )
    for value, expected in [("platinum", [3]), ("near_platinum", [2, 1])]:
        response = client.get(f"/profile/{STEAMID}", params={"played": value})
        assert response.status_code == 200
        import re

        assert [int(appid) for appid in re.findall(r'data-game="(\d+)"', response.text)] == expected


def test_filter_form_contains_auto_update_controls(setup):
    client, _, _ = setup
    response = client.get(f"/profile/{STEAMID}")
    assert 'id="played"' in response.text
    assert 'id="sort"' in response.text
    assert 'class="card-filters"' in response.text


def test_complete_game_card_uses_gold_highlight(setup):
    client, service, _ = setup
    service.get_library(STEAMID)
    from datetime import datetime, timezone

    from steam_analytics.storage import save_achievements

    save_achievements(
        service.database,
        STEAMID,
        1,
        {"items": [{"apiname": "A", "name": "100%", "description": "", "unlocked": True}]},
        datetime.now(timezone.utc).isoformat(),
    )
    response = client.get(f"/profile/{STEAMID}")
    assert 'is-complete"' in response.text
    assert 'data-percent="100.0"' in response.text


def test_hltb_sort_and_card_value_use_saved_completionist(setup):
    client, service, _ = setup
    service.get_library(STEAMID)
    from datetime import datetime, timezone

    from steam_analytics.storage import save_hltb

    save_hltb(
        service.database,
        1,
        {
            "hltb_id": 10,
            "name": "Alpha",
            "similarity": 1,
            "main_story": 1,
            "main_extra": 2,
            "completionist": 40,
            "url": "https://howlongtobeat.com/game/10",
            "imported_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    save_hltb(
        service.database,
        2,
        {
            "hltb_id": 20,
            "name": "Portal",
            "similarity": 1,
            "main_story": 1,
            "main_extra": 2,
            "completionist": 10,
            "url": "https://howlongtobeat.com/game/20",
            "imported_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    response = client.get(f"/profile/{STEAMID}", params={"sort": "hltb_asc"})
    assert response.status_code == 200
    assert response.text.index(">Portal<") < response.text.index(">Alpha<")
    assert "Completionist 40.0 h" in response.text
