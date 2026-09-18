from types import SimpleNamespace

from steam_analytics.hltb import HLTBClient, HLTBError


def test_hltb_selects_best_match():
    searcher = SimpleNamespace(
        search=lambda *args, **kwargs: [
            SimpleNamespace(
                game_id=1,
                game_name="Other",
                similarity=0.7,
                main_story=2,
                main_extra=3,
                completionist=4,
                game_web_link="x",
            ),
            SimpleNamespace(
                game_id=2,
                game_name="Portal 2",
                similarity=0.99,
                main_story=8.5,
                main_extra=11,
                completionist=16,
                game_web_link="y",
            ),
        ]
    )
    result = HLTBClient(searcher=searcher).search("Portal 2")
    assert result["hltb_id"] == 2 and result["completionist"] == 16


def test_hltb_rejects_weak_match():
    searcher = SimpleNamespace(
        search=lambda *args, **kwargs: [SimpleNamespace(game_id=1, game_name="Other", similarity=0.2)]
    )
    try:
        HLTBClient(searcher=searcher).search("Portal")
    except HLTBError:
        pass
    else:
        raise AssertionError("weak result should be rejected")
