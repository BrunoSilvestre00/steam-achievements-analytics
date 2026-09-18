import sqlite3
from unittest.mock import Mock

import pytest

from steam_analytics.service import LibraryService
from steam_analytics.steam import SteamError, normalize_game
from steam_analytics.storage import connect, expire_achievements, load_achievements, load_library, save_library

STEAMID = "76561198000000001"


def test_legacy_database_is_migrated_without_losing_games(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE libraries (steamid TEXT PRIMARY KEY, imported_at TEXT, game_count INTEGER);
            CREATE TABLE games (steamid TEXT, appid INTEGER, name TEXT, playtime_forever INTEGER,
              playtime_2weeks INTEGER, rtime_last_played INTEGER, PRIMARY KEY (steamid, appid));
        """)
        db.execute("INSERT INTO libraries VALUES (?, ?, ?)", (STEAMID, "2026-09-17T00:00:00+00:00", 1))
        db.execute("INSERT INTO games VALUES (?, ?, ?, ?, ?, ?)", (STEAMID, 1, "Portal", 120, None, None))
    result = load_library(path, STEAMID)
    assert result["games"][0]["name"] == "Portal"
    assert result["games"][0]["playtime_forever"] == 120
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_failed_write_rolls_back_previous_library(tmp_path):
    path = tmp_path / "atomic.db"
    game = normalize_game({"appid": 1, "name": "Portal", "playtime_forever": 120})
    save_library(path, STEAMID, [game], "2026-09-17T00:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        save_library(path, STEAMID, [game, game], "2026-09-18T00:00:00+00:00")
    assert load_library(path, STEAMID)["game_count"] == 1
    assert load_library(path, STEAMID)["imported_at"] == "2026-09-17T00:00:00+00:00"


def test_game_catalog_is_shared_but_playtime_is_per_profile(tmp_path):
    path = tmp_path / "shared.db"
    for steamid, minutes in [(STEAMID, 100), ("76561198000000002", 200)]:
        save_library(
            path,
            steamid,
            [normalize_game({"appid": 1, "name": "Portal", "playtime_forever": minutes})],
            "2026-09-17T00:00:00+00:00",
        )
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM games").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM library_games").fetchone()[0] == 2
    assert load_library(path, STEAMID)["games"][0]["playtime_forever"] == 100


def test_achievement_failure_preserves_last_success_after_restart(tmp_path):
    path = tmp_path / "achievements.db"
    save_library(path, STEAMID, [normalize_game({"appid": 1, "name": "Portal"})], "2026-09-17T00:00:00+00:00")
    client = Mock()
    client.player_achievements.return_value = {
        "available": True,
        "items": [{"apiname": "A", "name": "First", "description": "", "unlocked": True}],
        "total": 1,
        "unlocked": 1,
        "percent": 100.0,
        "complete": True,
        "error": None,
    }
    service = LibraryService("secret", path, client=client)
    service.achievements(STEAMID, 1)
    original_time = load_achievements(path, STEAMID, 1)["imported_at"]
    expire_achievements(path, STEAMID)
    client.player_achievements.side_effect = SteamError("Offline")
    restarted = LibraryService("secret", path, client=client)
    result = restarted.achievements(STEAMID, 1)
    assert result["unlocked"] == 1
    assert "salvas" in result["error"]
    assert load_achievements(path, STEAMID, 1)["unlocked"] == 1
    assert load_achievements(path, STEAMID, 1)["imported_at"] == original_time


def test_version_one_upgrades_without_losing_library(tmp_path):
    path = tmp_path / "v1.db"
    game = normalize_game({"appid": 1, "name": "Portal"})
    save_library(path, STEAMID, [game], "2026-09-17T00:00:00+00:00")
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE achievement_attempts")
        db.execute("PRAGMA user_version = 1")
    assert load_library(path, STEAMID)["game_count"] == 1
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 5
        assert db.execute("SELECT count(*) FROM achievement_attempts").fetchone()[0] == 0
