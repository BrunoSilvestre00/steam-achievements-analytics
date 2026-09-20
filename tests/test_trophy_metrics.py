"""Regression tests for independent PSNProfiles overview metrics."""

import unittest

from steam_analytics.trophy import parse_trophy_guide, trophy_count_difference

GUIDE_URL = "https://psnprofiles.com/guide/20561-epic-mickey-rebrushed-trophy-guide"


def overview(runs, hours, *, runs_label="Playthroughs", hours_label="Hours"):
    # Structure from the saved PSNProfiles guide; one run uses a singular label.
    return f"""
    <div class="trophy-count"><span class="small-info">{(runs + 49) if isinstance(runs, int) else 50} trophies</span></div>
    <div class="overview-info">
      <span class="tag"><span class="typo-top">2/10</span><br>
        <span class="typo-bottom">Difficulty</span></span>
      <span class="tag"><span class="typo-top">{runs}</span><br>
        <span class="typo-bottom">{runs_label}</span></span>
      <span class="tag"><span class="typo-top">{hours}</span><br>
        <span class="typo-bottom">{hours_label}</span></span>
    </div>
    """


class TrophyMetricsTests(unittest.TestCase):
    def test_singular_playthrough_does_not_read_the_following_hours(self):
        result = parse_trophy_guide(GUIDE_URL, overview(1, 100, runs_label="Playthrough"))
        self.assertEqual(result["playthroughs"], 1)
        self.assertEqual(result["hours"], 100)
        self.assertEqual(result["difficulty"], 2)

    def test_plural_metrics_and_singular_hour(self):
        for runs, hours, label in [(2, 20, "Hours"), (1, 1, "Hour")]:
            with self.subTest(runs=runs, hours=hours):
                result = parse_trophy_guide(GUIDE_URL, overview(runs, hours, hours_label=label))
                self.assertEqual(result["playthroughs"], runs)
                self.assertEqual(result["hours"], hours)

    def test_missing_run_value_does_not_borrow_hours_or_prose(self):
        html = overview("N/A", 100) + "<p>Minimum Playthroughs: 3</p>"
        result = parse_trophy_guide(GUIDE_URL, html)
        self.assertIsNone(result["playthroughs"])
        self.assertEqual(result["hours"], 100)

    def test_text_fallback_does_not_cross_metric_boundaries(self):
        for text in ["<div>1 Playthrough 100 Hours</div>", "<div>Playthrough</div><div>100 Hours</div>"]:
            with self.subTest(text=text):
                result = parse_trophy_guide(GUIDE_URL, "<p>Difficulty: 2/10</p>" + text)
                self.assertIsNone(result["playthroughs"])

    def test_legacy_labeled_rows(self):
        html = """
          <p>Estimated difficulty: <b>3/10</b></p>
          <table><tr><td>Minimum Playthroughs:</td><td>2</td></tr></table>
          <p>Estimated time to platinum: 20 hours</p>
        """
        result = parse_trophy_guide(GUIDE_URL, html)
        self.assertEqual(result["difficulty"], 3)
        self.assertEqual(result["playthroughs"], 2)
        self.assertEqual(result["hours"], 20)

    def test_playstation_trophy_count_is_extracted_and_compared(self):
        result = parse_trophy_guide(GUIDE_URL, overview(1, 20))
        self.assertEqual(result["trophy_count"], 50)
        difference = trophy_count_difference(result, {"available": True, "total": 42})
        self.assertEqual(difference["more"], "PlayStation")
        self.assertEqual(difference["difference"], 8)
        self.assertIsNone(trophy_count_difference(result, {"available": True, "total": 50}))
        self.assertIsNone(trophy_count_difference(None, {"available": True, "total": 42}))

    def test_one_extra_playstation_trophy_is_the_platinum_case(self):
        result = trophy_count_difference({"trophy_count": 43}, {"available": True, "total": 42})
        self.assertTrue(result["platinum_only"])
        result = trophy_count_difference({"trophy_count": 44}, {"available": True, "total": 42})
        self.assertFalse(result["platinum_only"])


if __name__ == "__main__":
    unittest.main()
