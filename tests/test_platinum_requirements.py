"""Guide precedence and Steam fallback for the modal's planning badges."""

import unittest
from types import SimpleNamespace

from bs4 import BeautifulSoup

from steam_analytics.trophy import platinum_requirements
from steam_analytics.web import templates


def steam(*online, available=True):
    return {
        "available": available,
        "total": len(online),
        "unlocked": 0,
        "percent": 0,
        "items": [{"name": "Example", "unlocked": False, "is_online": value} for value in online],
    }


class PlatinumRequirementsTests(unittest.TestCase):
    def test_guide_overrides_both_positive_and_negative_steam_detection(self):
        result = platinum_requirements({"tags": ["Unmissable", "Story"]}, steam(True))
        self.assertTrue(result["no_online"])
        self.assertTrue(result["no_missable"])
        self.assertEqual(result["source"], "Trophy Guide")
        result = platinum_requirements({"tags": ["Online", "Missable"]}, steam(False))
        self.assertFalse(result["no_online"])
        self.assertFalse(result["no_missable"])

    def test_individual_trophy_tags_are_also_considered(self):
        guide = {"tags": [], "trophies": [{"tags": [" ONLINE ", "Missable"]}]}
        result = platinum_requirements(guide, steam(False))
        self.assertFalse(result["no_online"])
        self.assertFalse(result["no_missable"])

    def test_online_required_is_an_online_requirement(self):
        result = platinum_requirements({"tags": ["Online Required"]}, steam(False))
        self.assertFalse(result["no_online"])
        self.assertTrue(result["no_missable"])

    def test_steam_fallback_never_asserts_absence_of_missables(self):
        for guide in [None, {"error": "HTTP 403", "tags": []}]:
            with self.subTest(guide=guide):
                result = platinum_requirements(guide, steam(False, False))
                self.assertTrue(result["no_online"])
                self.assertFalse(result["no_missable"])
                self.assertEqual(result["source"], "An\u00e1lise Steam")
                self.assertFalse(platinum_requirements(guide, steam(False, True))["no_online"])

    def test_unknown_or_incomplete_steam_data_has_no_badges(self):
        for data in [None, steam(), steam(False, available=False), steam(None), {**steam(False), "total": 2}]:
            with self.subTest(data=data):
                result = platinum_requirements(None, data)
                self.assertFalse(result["no_online"])
                self.assertFalse(result["no_missable"])

    def test_rendered_badges_precede_planning_section(self):
        guide = {
            "tags": [],
            "trophies": [],
            "difficulty": 2,
            "hours": 100,
            "playthroughs": 1,
            "url": "https://psnprofiles.com/guide/example",
        }
        html = templates.get_template("game_detail.html").render(
            request=SimpleNamespace(url_for=lambda name, **kwargs: "/static/" + kwargs["path"]),
            selected={"appid": 1, "name": "Example", "source": "steam", "playtime_forever": 60},
            library={"steamid": "76561198339084663"},
            achievements=steam(True),
            hltb=None,
            trophy_guide=guide,
        )
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(len(soup.select("[data-no-online]")), 1)
        self.assertEqual(len(soup.select("[data-no-missable]")), 1)
        self.assertIn("N\u00e3o possui online", soup.select_one("[data-no-online]").get_text())
        self.assertLess(html.index("data-no-missable"), html.index('id="planning-title"'))


if __name__ == "__main__":
    unittest.main()
