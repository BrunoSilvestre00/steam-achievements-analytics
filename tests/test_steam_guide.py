import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from steam_analytics.service import LibraryService
from steam_analytics.storage import load_game_workspace, save_library
from steam_analytics.web import create_app


@pytest.fixture
def guide_app(tmp_path):
    database = tmp_path / "steam.sqlite3"
    sid = "76561198339084663"
    save_library(database, sid, [{"appid": 374320, "name": "DARK SOULS III", "playtime_forever": 0, "playtime_2weeks": 0, "rtime_last_played": None}], "2026-10-06T00:00:00+00:00")
    app = create_app(service=LibraryService("", database))
    return app, database, sid


def test_context_and_note_publication(guide_app):
    app, database, sid = guide_app
    markdown = "# Guia de platina\n\n> Atenção aos perdíveis\n\n- [ ] Conquista oculta\n"
    path = f"/api/profile/{sid}/games/374320/workspace/note"
    with TestClient(app) as client:
        context = client.get("/api/local/guide-context").json()
        assert context["active_steamid"] == sid
        assert context["games"][0]["appid"] == 374320
        first = client.post(path, json={"body": markdown}).json()
        repeat = client.post(path, json={"body": markdown}).json()
        assert first["created"]
        assert not repeat["created"]
        assert first["note_id"] == repeat["note_id"]
        assert client.post(path, json={"body": " "}).status_code == 400
        assert client.post(path.replace("374320", "123"), json={"body": markdown}).status_code == 404
        assert client.post(path.replace(sid, "76561199019746259"), json={"body": markdown}).status_code == 404
    notes = load_game_workspace(database, sid, 374320)["notes"]
    assert len(notes) == 1
    assert notes[0]["body"] == markdown


def test_context_does_not_guess_between_profiles(guide_app):
    app, database, sid = guide_app
    save_library(database, "76561199019746259", [], "2026-10-06T00:00:00+00:00")
    with TestClient(app) as client:
        assert client.get("/api/local/guide-context").json()["active_steamid"] is None
        app.state.active_steamid = sid
        assert client.get("/api/local/guide-context").json()["active_steamid"] == sid


def test_client_reads_utf8_file_and_uses_api(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("steam_guide_client", Path("scripts/steam_guide_client.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sid = "76561198339084663"
    monkeypatch.setattr(module, "discover", lambda _: ("http://127.0.0.1:80", {"active_steamid": sid, "profiles": [{"steamid": sid}]}))
    requests = []

    def publish(url, payload):
        requests.append((url, payload))
        return {"ok": True, "note_id": 1, "workspace_url": f"/profile/{sid}/games/374320/workspace"}

    monkeypatch.setattr(module, "request_json", publish)
    file = tmp_path / "guia.md"
    body = '# Guia\n\n- [ ] Atenção: "perdível"\n'
    file.write_text(body, encoding="utf-8")
    monkeypatch.setattr(module.sys, "argv", ["client", "publish", "--appid", "374320", "--file", str(file)])
    assert module.main() == 0
    assert requests[0][1]["body"] == body
    assert "workspace_url" in capsys.readouterr().out
