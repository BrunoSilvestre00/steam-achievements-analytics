from steam_analytics.markdown_notes import render_markdown, update_markdown_task
from steam_analytics.version import VERSION


def test_markdown_syntax_and_safe_html():
    rendered = render_markdown("# Título\n\n> Citação\n\n-----\n\n\\| escape\n\n- [ ] Item\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))")
    assert "<blockquote>" in rendered
    assert "<hr/>" in rendered
    assert "| escape" in rendered
    assert 'data-note-task="0"' in rendered
    assert "<script>" not in rendered
    assert 'href="javascript:' not in rendered


def test_tasks_update_markdown_and_skip_fenced_code():
    body = "```\n- [ ] Código\n```\n\n- [ ] Real\n  - [x] Aninhada\n\n> - [ ] Citada\n"
    changed = update_markdown_task(body, 0, True)
    assert changed == body.replace("- [ ] Real", "- [x] Real")
    assert update_markdown_task(changed, 1, False) == changed.replace("- [x] Aninhada", "- [ ] Aninhada")
    assert update_markdown_task(body, 2, True) == body.replace("> - [ ] Citada", "> - [x] Citada")


def test_release_version():
    assert VERSION == "1.0.1"


def test_task_api_persists_markdown_and_scopes_note(tmp_path):
    from fastapi.testclient import TestClient

    from steam_analytics.service import LibraryService
    from steam_analytics.storage import add_game_note, load_game_workspace, save_library
    from steam_analytics.web import create_app

    database = tmp_path / "steam.sqlite3"
    sid = "76561198339084663"
    save_library(database, sid, [{"appid": 1, "name": "Test", "playtime_forever": 0, "playtime_2weeks": 0, "rtime_last_played": None}], "2026-10-05T00:00:00+00:00")
    add_game_note(database, sid, 1, "- [ ] Objetivo")
    note = load_game_workspace(database, sid, 1)["notes"][0]
    with TestClient(create_app(service=LibraryService("", database))) as client:
        path = f"/api/profile/{sid}/games/1/workspace/note/{note['id']}"
        response = client.patch(path + "/task/0", json={"checked": True})
        assert response.status_code == 200
        assert response.json()["body"] == "- [x] Objetivo"
        assert load_game_workspace(database, sid, 1)["notes"][0]["body"] == "- [x] Objetivo"
        assert client.patch(path.replace("games/1/", "games/2/") + "/task/0", json={"checked": False}).status_code == 404
