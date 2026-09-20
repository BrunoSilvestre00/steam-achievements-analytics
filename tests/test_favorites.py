"""Favorites survive imports, remain per profile, and render on all game views."""

import asyncio
import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from bs4 import BeautifulSoup

from steam_analytics.service import LibraryService
from steam_analytics.steam import normalize_game
from steam_analytics.storage import connect, load_library, save_library, set_game_favorite
from steam_analytics.web import create_app

SID = "76561198000000001"
FRIEND = "76561198000000002"
STAMP = "2026-09-19T00:00:00+00:00"


async def request(app, method, path, payload=None, query=b""):
    body = json.dumps(payload).encode() if payload is not None else b""
    messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.Event().wait()

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
        "root_path": "",
    }
    await app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    return status, b"".join(message.get("body", b"") for message in messages).decode()


class FavoritesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "favorites.sqlite3"
        self.games = [normalize_game({"appid": appid, "name": f"Game {appid}"}) for appid in (1, 2)]
        for sid in (SID, FRIEND):
            save_library(self.database, sid, self.games, STAMP, personaname="Test")

    def favorite(self, sid=SID):
        return load_library(self.database, sid)["games"][0]["is_favorite"]

    def test_idempotent_per_profile_and_survives_library_refresh(self):
        set_game_favorite(self.database, SID, 1, True)
        set_game_favorite(self.database, SID, 1, True)
        save_library(self.database, SID, self.games, STAMP)
        self.assertTrue(self.favorite())
        self.assertFalse(self.favorite(FRIEND))
        with connect(self.database) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM game_favorites").fetchone()[0], 1)
        set_game_favorite(self.database, SID, 1, False)
        set_game_favorite(self.database, SID, 1, False)
        self.assertFalse(self.favorite())

    def test_version_13_migration_keeps_existing_data(self):
        with sqlite3.connect(self.database) as db:
            db.execute("DROP TABLE game_favorites")
            db.execute("PRAGMA user_version = 13")
        self.assertFalse(self.favorite())
        self.assertEqual(load_library(self.database, SID)["game_count"], 2)
        with connect(self.database) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 14)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_api_validation_filter_and_all_three_surfaces(self):
        service = LibraryService("test", self.database, client=Mock())
        service.achievements = Mock(return_value={"available": True, "total": 0, "unlocked": 0, "items": []})
        service.hltb = Mock(return_value=None)
        app = create_app(service=service)
        app.state.cache = Mock()

        def call(method, path, payload=None, query=b""):
            return asyncio.run(request(app, method, path, payload, query))

        url = f"/api/profile/{SID}/games/1/favorite"
        status, body = call("PUT", url, {"favorite": True})
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["is_favorite"])
        app.state.cache.invalidate.assert_called_with(f"profile:{SID}")
        self.assertEqual(call("PUT", url, {"favorite": "false"})[0], 422)
        self.assertEqual(call("PUT", f"/api/profile/{SID}/games/999/favorite", {"favorite": True})[0], 404)

        status, html = call("GET", f"/profile/{SID}", query=b"played=favorites")
        self.assertEqual(status, 200, html)
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".game-card")
        self.assertEqual([card["data-game"] for card in cards], ["1"])
        self.assertEqual(cards[0].select_one("[data-favorite-button]")["aria-pressed"], "true")
        self.assertIsNone(cards[0].select_one("a button"))
        self.assertTrue(cards[0].select_one("a.game-card-link[href]"))

        for total, unlocked in [(0, 0), (2, 0), (2, 2)]:
            service.achievements.return_value = {
                "available": True,
                "total": total,
                "unlocked": unlocked,
                "items": [],
            }
            status, html = call("GET", f"/profile/{SID}/games/1/workspace")
            self.assertEqual(status, 200, html)
            button = BeautifulSoup(html, "html.parser").select_one("[data-favorite-button]")
            self.assertEqual(button["aria-pressed"], "true")

        service.achievements.return_value = {"available": True, "total": 0, "unlocked": 0, "items": []}
        status, html = call("GET", f"/profile/{SID}/games/1")
        self.assertEqual(status, 200, html)
        soup = BeautifulSoup(html, "html.parser")
        self.assertFalse(soup.select_one(".detail-art-label [data-favorite-tag]").has_attr("hidden"))
        self.assertTrue(soup.select_one(".detail-art [data-favorite-button]"))

        self.assertEqual(call("PUT", url, {"favorite": False})[0], 200)
        status, html = call("GET", f"/profile/{SID}", query=b"played=favorites")
        self.assertEqual(status, 200, html)
        self.assertFalse(BeautifulSoup(html, "html.parser").select(".game-card"))
        self.assertFalse(self.favorite())
        service.client.owned_games.assert_not_called()


if __name__ == "__main__":
    unittest.main()
