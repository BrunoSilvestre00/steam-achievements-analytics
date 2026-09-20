"""Render workspace variants without Steam requests or a persistent database."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from bs4 import BeautifulSoup

from steam_analytics.service import LibraryService
from steam_analytics.steam import SteamClient, SteamError, normalize_game
from steam_analytics.storage import load_progress, save_library
from steam_analytics.web import templates


def render(template, **context):
    defaults = {
        "request": SimpleNamespace(url_for=lambda name, **kwargs: f"/static/{kwargs['path']}"),
        "library": {
            "steamid": "76561198339084663",
            "personaname": "Test",
            "game_count": 1,
            "imported_at": "2026-09-19T00:00:00+00:00",
        },
        "selected": {"appid": 1, "name": "Example", "playtime_forever": 120},
        "workspace": {"notes": [{"body": "Saved note"}], "checklist": [], "links": []},
        "hltb": {"main_story": 5, "completionist": 10},
        "trophy_guide": None,
        "guide_pairing": None,
        "progress_pending": 0,
    }
    return BeautifulSoup(templates.env.get_template(template).render(**(defaults | context)), "html.parser")


class WorkspaceStatesTest(unittest.TestCase):
    def test_failed_player_query_only_becomes_empty_with_store_confirmation(self):
        for data, expected in [
            ({"categories": [{"id": 2}]}, "empty"),
            ({"categories": [{"id": 22}]}, "unavailable"),
            ({"categories": []}, "unavailable"),
            ({}, "unavailable"),
            ({"categories": [{"id": 2}], "achievements": {"total": 3}}, "unavailable"),
        ]:
            with self.subTest(data=data), TemporaryDirectory() as directory:
                database = Path(directory) / "test.sqlite3"
                sid = "76561198339084663"
                save_library(database, sid, [normalize_game({"appid": 1, "name": "Test"})], "2026-09-19T00:00:00+00:00")
                client = SteamClient("test")
                client.player_achievements = Mock(side_effect=SteamError("Unavailable"))
                client._get_external_json = Mock(return_value={"1": {"success": True, "data": data}})
                service = LibraryService("test", database, client=client)
                result = service.achievements(sid, 1)
                self.assertEqual(result["available"], expected == "empty")
                self.assertEqual(load_progress(database, sid)[0]["state"], expected)

    def test_only_confirmed_empty_games_use_the_freeplay_workspace(self):
        for available, total, unlocked in [(True, 0, 0), (False, 0, 0), (True, 3, 0), (True, 3, 3)]:
            with self.subTest(available=available, total=total, unlocked=unlocked):
                soup = render(
                    "game_workspace.html",
                    achievements={
                        "available": available,
                        "total": total,
                        "unlocked": unlocked,
                        "items": [],
                    },
                )
                empty = available and total == 0
                self.assertEqual(bool(soup.select_one(".freeplay-hero")), empty)
                self.assertEqual("no-achievements-workspace" in soup.body["class"], empty)
                self.assertEqual(len(soup.select("#personal-planning")), 1)
                self.assertIn("Saved note", soup.get_text())
                if empty:
                    self.assertFalse(soup.select(".progress-overview-card, .completion-emblem"))
                    self.assertTrue(soup.select_one(".hltb-overview-card"))
                    self.assertTrue(soup.select_one(".playtime-overview-card"))
                    self.assertFalse(soup.select_one("#personal-planning").find_parent("details"))

    def test_library_marks_empty_but_not_unknown_or_locked_games(self):
        states = [("empty", None, 0), ("pending", None, None), ("unavailable", None, None), ("ready", 0, 3)]
        games = [
            {
                "appid": index,
                "name": f"Game {index}",
                "source": "external",
                "playtime_forever": 0,
                "rtime_last_played": None,
                "hltb": None,
                "trophy_guide": None,
                "name_order": index,
                "progress": {"state": state, "percent": percent, "total": total, "unlocked": 0, "stale": False},
            }
            for index, (state, percent, total) in enumerate(states, 1)
        ]
        soup = render(
            "profile.html",
            games=games,
            selected=None,
            achievements=None,
            sort="percent_desc",
            played="all",
            q="",
            total_minutes=0,
            played_count=0,
            unplayed_count=4,
            unknown_count=0,
            platinum_count=0,
            recent_platinums=[],
            platinums_by_year=[],
        )
        cards = soup.select(".game-card")
        self.assertEqual(len(cards), 4)
        for card in cards:
            empty = card["data-game"] == "1"
            self.assertEqual("has-no-achievements" in card["class"], empty)
            self.assertEqual(not card.select_one("[data-no-achievements]").has_attr("hidden"), empty)
            self.assertTrue(card.select_one(".game-source-tag.external"))


if __name__ == "__main__":
    unittest.main()
