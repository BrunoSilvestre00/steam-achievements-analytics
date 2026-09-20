"""Última biblioteca válida por perfil; atualização em uma única transação."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .steam import normalize_game


@contextmanager
def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 17:
            raise sqlite3.DatabaseError("Versão do banco não suportada")
        if version == 0:
            with db:
                db.execute("BEGIN IMMEDIATE")
                # Migra o formato do primeiro importador sem perder dados existentes.
                legacy = any(row["name"] == "steamid" for row in db.execute("PRAGMA table_info(games)"))
                if legacy:
                    db.execute("ALTER TABLE games RENAME TO legacy_owned_games")
                schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
                for statement in schema.split(";"):
                    if statement.strip():
                        db.execute(statement)
                if legacy:
                    db.execute("INSERT OR REPLACE INTO games SELECT appid, name FROM legacy_owned_games")
                    db.execute("""INSERT INTO library_games
                        SELECT steamid, appid, playtime_forever, playtime_2weeks, rtime_last_played, 'steam'
                        FROM legacy_owned_games""")
                    db.execute("DROP TABLE legacy_owned_games")
                db.execute("PRAGMA user_version = 1")
        if version < 2:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS achievement_attempts (
                    steamid TEXT NOT NULL REFERENCES libraries(steamid),
                    appid INTEGER NOT NULL REFERENCES games(appid),
                    checked_at TEXT NOT NULL, error TEXT,
                    PRIMARY KEY (steamid, appid)
                )""")
                db.execute("PRAGMA user_version = 2")
                version = 2
        if version < 3:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS hltb_data (
                    appid INTEGER PRIMARY KEY REFERENCES games(appid), hltb_id INTEGER NOT NULL,
                    matched_name TEXT NOT NULL, similarity REAL NOT NULL,
                    main_story REAL, main_extra REAL, completionist REAL, url TEXT,
                    imported_at TEXT NOT NULL, error TEXT
                )""")
                db.execute("PRAGMA user_version = 3")
                version = 3
        if version < 4:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS trophy_guides (
                    appid INTEGER PRIMARY KEY REFERENCES games(appid), url TEXT NOT NULL,
                    difficulty REAL, playthroughs INTEGER, hours REAL, hours_text TEXT,
                    imported_at TEXT NOT NULL, error TEXT
                )""")
                db.execute("PRAGMA user_version = 4")
                version = 4
        if version < 5:
            with db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS game_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid), body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS game_checklist (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid), label TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)), position INTEGER NOT NULL DEFAULT 0)"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS game_links (id INTEGER PRIMARY KEY AUTOINCREMENT, steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid), label TEXT NOT NULL, url TEXT NOT NULL, created_at TEXT NOT NULL)"
                )
                db.execute("PRAGMA user_version = 5")
                version = 5
        if version < 6:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(libraries)")}
                if "personaname" not in columns:
                    db.execute("ALTER TABLE libraries ADD COLUMN personaname TEXT")
                db.execute("PRAGMA user_version = 6")
                version = 6
        if version < 7:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(achievement_definitions)")}
                if "icon" not in columns:
                    db.execute("ALTER TABLE achievement_definitions ADD COLUMN icon TEXT")
                if "icon_gray" not in columns:
                    db.execute("ALTER TABLE achievement_definitions ADD COLUMN icon_gray TEXT")
                db.execute("PRAGMA user_version = 7")
        if version < 8:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(achievement_definitions)")}
                if "is_online" not in columns:
                    db.execute("ALTER TABLE achievement_definitions ADD COLUMN is_online INTEGER NOT NULL DEFAULT 0")
                db.execute("PRAGMA user_version = 8")
        if version < 9:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(achievement_definitions)")}
                if "is_hidden" not in columns:
                    db.execute("ALTER TABLE achievement_definitions ADD COLUMN is_hidden INTEGER NOT NULL DEFAULT 0")
                db.execute("PRAGMA user_version = 9")
        if version < 10:
            with db:
                # Corrige registros criados quando o campo hidden vinha como texto
                # e era interpretado incorretamente como True.
                db.execute(
                    "UPDATE achievement_definitions SET is_hidden=0 WHERE is_hidden=1 AND COALESCE(description, '') = ''"
                )
                db.execute("PRAGMA user_version = 10")
        if version < 11:
            with db:
                db.execute("UPDATE achievement_sync SET refresh_required=1")
                db.execute("PRAGMA user_version = 11")
                version = 11
        if version < 12:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(library_games)")}
                if "source" not in columns:
                    db.execute("ALTER TABLE library_games ADD COLUMN source TEXT NOT NULL DEFAULT 'steam'")
                db.execute("PRAGMA user_version = 12")
                version = 12
        if version < 13:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(trophy_guides)")}
                for name in ("tags_json", "roadmap_json", "trophies_json"):
                    if name not in columns:
                        db.execute(f"ALTER TABLE trophy_guides ADD COLUMN {name} TEXT")
                db.execute("PRAGMA user_version = 13")
                version = 13
        if version < 14:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS game_favorites (
                    steamid TEXT NOT NULL REFERENCES libraries(steamid),
                    appid INTEGER NOT NULL REFERENCES games(appid),
                    PRIMARY KEY (steamid, appid)
                )""")
                db.execute("PRAGMA user_version = 14")
                version = 14
        if version < 15:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(trophy_guides)")}
                if "trophy_count" not in columns:
                    db.execute("ALTER TABLE trophy_guides ADD COLUMN trophy_count INTEGER")
                db.execute("PRAGMA user_version = 15")
        if version < 16:
            with db:
                columns = {row["name"] for row in db.execute("PRAGMA table_info(game_checklist)")}
                if "checklist_name" not in columns:
                    db.execute("ALTER TABLE game_checklist ADD COLUMN checklist_name TEXT NOT NULL DEFAULT 'Checklist geral'")
                db.execute("PRAGMA user_version = 16")
                version = 16
        if version < 17:
            with db:
                db.execute("""CREATE TABLE IF NOT EXISTS game_checklist_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid),
                    name TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (steamid, appid, name)
                )""")
                db.execute("INSERT OR IGNORE INTO game_checklist_groups (steamid,appid,name,position) SELECT steamid,appid,checklist_name,MIN(position) FROM game_checklist GROUP BY steamid,appid,checklist_name")
                db.execute("PRAGMA user_version = 17")
                version = 17
        yield db
    finally:
        db.close()


def load_library(path, steamid):
    path = Path(path)
    if not path.exists():
        return None
    with connect(path) as db:
        library = db.execute("SELECT * FROM libraries WHERE steamid = ?", (steamid,)).fetchone()
        if library is None:
            return None
        games = [
            {**normalize_game(dict(row)), "source": row["source"] or "steam", "is_favorite": bool(row["is_favorite"])}
            for row in db.execute(
                """SELECT g.appid, g.name, lg.playtime_forever, lg.playtime_2weeks, lg.rtime_last_played, lg.source,
                EXISTS(SELECT 1 FROM game_favorites f WHERE f.steamid = lg.steamid AND f.appid = lg.appid) AS is_favorite
               FROM library_games lg JOIN games g ON g.appid = lg.appid
               WHERE lg.steamid = ? ORDER BY g.name COLLATE NOCASE, g.appid""",
                (steamid,),
            )
        ]
        return {**dict(library), "games": games}


def set_game_favorite(path, steamid, appid, favorite):
    with connect(path) as db, db:
        if not db.execute("SELECT 1 FROM library_games WHERE steamid = ? AND appid = ?", (steamid, appid)).fetchone():
            raise ValueError("Esse jogo não está na biblioteca importada.")
        if favorite:
            db.execute("INSERT OR IGNORE INTO game_favorites (steamid, appid) VALUES (?, ?)", (steamid, appid))
        else:
            db.execute("DELETE FROM game_favorites WHERE steamid = ? AND appid = ?", (steamid, appid))


def save_library(path, steamid, games, imported_at, personaname=None):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO libraries (steamid, personaname, imported_at, game_count) VALUES (?, ?, ?, ?)
            ON CONFLICT(steamid) DO UPDATE SET personaname=COALESCE(excluded.personaname, libraries.personaname),
            imported_at=excluded.imported_at, game_count=excluded.game_count""",
            (steamid, personaname, imported_at, len(games)),
        )
        db.executemany(
            """INSERT INTO games VALUES (?, ?)
            ON CONFLICT(appid) DO UPDATE SET name=excluded.name""",
            [(g["appid"], g["name"]) for g in games],
        )
        db.execute("DELETE FROM library_games WHERE steamid = ? AND source = 'steam'", (steamid,))
        appids = [g["appid"] for g in games]
        if appids:
            marks = ",".join("?" for _ in appids)
            db.execute(
                f"DELETE FROM library_games WHERE steamid = ? AND source <> 'steam' AND appid IN ({marks})",
                (steamid, *appids),
            )
        db.executemany(
            """INSERT INTO library_games
                (steamid, appid, playtime_forever, playtime_2weeks, rtime_last_played, source)
                VALUES (?, ?, ?, ?, ?, 'steam')
                """,
            [(steamid, g["appid"], g["playtime_forever"], g["playtime_2weeks"], g["rtime_last_played"]) for g in games],
        )
        total = db.execute("SELECT count(*) FROM library_games WHERE steamid = ?", (steamid,)).fetchone()[0]
        db.execute("UPDATE libraries SET game_count = ? WHERE steamid = ?", (total, steamid))


def save_external_games(path, steamid, games, source):
    """Adiciona jogos externos sem apagar os jogos oficiais do perfil."""
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as db, db:
        db.executemany(
            "INSERT INTO games (appid, name) VALUES (?, ?) ON CONFLICT(appid) DO UPDATE SET name=excluded.name",
            [(game["appid"], game["name"]) for game in games],
        )
        db.executemany(
            """INSERT INTO library_games
                (steamid, appid, playtime_forever, playtime_2weeks, rtime_last_played, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(steamid, appid) DO UPDATE SET source=excluded.source""",
            [
                (
                    steamid,
                    game["appid"],
                    game.get("playtime_forever"),
                    game.get("playtime_2weeks"),
                    game.get("rtime_last_played"),
                    source,
                )
                for game in games
            ],
        )
        db.execute(
            "UPDATE libraries SET game_count=(SELECT count(*) FROM library_games WHERE steamid=?), imported_at=? WHERE steamid=?",
            (steamid, now, steamid),
        )


def update_game_source(path, steamid, appid, source):
    with connect(path) as db, db:
        db.execute(
            "UPDATE library_games SET source=? WHERE steamid=? AND appid=?",
            (source, steamid, appid),
        )


def update_personaname(path, steamid, personaname):
    with connect(path) as db:
        db.execute("UPDATE libraries SET personaname=? WHERE steamid=?", (personaname, steamid))


def update_game_playtime(path, steamid, appid, playtime_forever, playtime_2weeks=None):
    with connect(path) as db, db:
        db.execute(
            "UPDATE library_games SET playtime_forever=?, playtime_2weeks=? WHERE steamid=? AND appid=?",
            (playtime_forever, playtime_2weeks, steamid, appid),
        )


def save_achievements(path, steamid, appid, result, imported_at):
    with connect(path) as db, db:
        db.executemany(
            """INSERT INTO achievement_definitions (appid, apiname, name, description, icon, icon_gray, is_online, is_hidden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(appid, apiname) DO UPDATE SET name=excluded.name, description=excluded.description,
            icon=COALESCE(excluded.icon, achievement_definitions.icon),
            icon_gray=COALESCE(excluded.icon_gray, achievement_definitions.icon_gray),
            is_online=excluded.is_online, is_hidden=excluded.is_hidden""",
            [
                (
                    appid,
                    item["apiname"],
                    item["name"],
                    item["description"],
                    item.get("icon"),
                    item.get("icon_gray"),
                    int(item.get("is_online", False)),
                    int(item.get("is_hidden", False)),
                )
                for item in result["items"]
            ],
        )
        db.execute("DELETE FROM player_achievements WHERE steamid = ? AND appid = ?", (steamid, appid))
        db.executemany(
            "INSERT INTO player_achievements VALUES (?, ?, ?, ?)",
            [(steamid, appid, item["apiname"], int(item["unlocked"])) for item in result["items"]],
        )
        db.execute(
            """INSERT INTO achievement_sync (steamid, appid, imported_at) VALUES (?, ?, ?)
            ON CONFLICT(steamid, appid) DO UPDATE SET imported_at=excluded.imported_at,
            refresh_required=0""",
            (steamid, appid, imported_at),
        )
        db.execute(
            """INSERT INTO achievement_attempts VALUES (?, ?, ?, NULL)
            ON CONFLICT(steamid, appid) DO UPDATE SET checked_at=excluded.checked_at, error=NULL""",
            (steamid, appid, imported_at),
        )


def save_achievement_failure(path, steamid, appid, error):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO achievement_attempts VALUES (?, ?, ?, ?)
            ON CONFLICT(steamid, appid) DO UPDATE SET checked_at=excluded.checked_at, error=excluded.error""",
            (steamid, appid, datetime.now(timezone.utc).isoformat(), error),
        )


def load_progress(path, steamid):
    """Resumo de toda a biblioteca em uma consulta, sem acessar a Steam."""
    if not Path(path).exists():
        return []
    now = datetime.now(timezone.utc)
    with connect(path) as db:
        rows = db.execute(
            """
            SELECT lg.appid, lg.source, s.imported_at, s.refresh_required, a.checked_at, a.error,
                   count(p.apiname) AS total, coalesce(sum(p.unlocked), 0) AS unlocked
            FROM library_games lg
            LEFT JOIN achievement_sync s ON s.steamid=lg.steamid AND s.appid=lg.appid
            LEFT JOIN achievement_attempts a ON a.steamid=lg.steamid AND a.appid=lg.appid
            LEFT JOIN player_achievements p ON p.steamid=lg.steamid AND p.appid=lg.appid
            WHERE lg.steamid=? GROUP BY lg.appid
        """,
            (steamid,),
        ).fetchall()
    result = []
    for row in rows:
        checked = row["checked_at"] or (row["imported_at"] if not row["refresh_required"] else None)
        pending = not checked or (now - datetime.fromisoformat(checked)).total_seconds() >= 900
        known = row["imported_at"] is not None
        total = row["total"] if known else None
        percent = round(100 * row["unlocked"] / total, 1) if total else None
        state = ("ready" if total else "empty") if known else ("unavailable" if row["error"] else "pending")
        result.append(
            {
                "appid": row["appid"],
                "source": row["source"] or "steam",
                "percent": percent,
                "total": total,
                "unlocked": row["unlocked"] if known else None,
                "state": state,
                "needs_update": pending,
                "stale": bool(known and (pending or row["error"])),
            }
        )
    return result


def load_achievements(path, steamid, appid):
    if not Path(path).exists():
        return None
    with connect(path) as db:
        sync = db.execute(
            "SELECT imported_at, refresh_required FROM achievement_sync WHERE steamid = ? AND appid = ?",
            (steamid, appid),
        ).fetchone()
        if not sync:
            return None
        items = [
            {
                **dict(row),
                "unlocked": bool(row["unlocked"]),
                "is_online": bool(row["is_online"]),
                "is_hidden": bool(row["is_hidden"]),
            }
            for row in db.execute(
                """
            SELECT d.apiname, d.name, d.description, d.icon, d.icon_gray, d.is_online, d.is_hidden, p.unlocked
            FROM player_achievements p JOIN achievement_definitions d
              ON d.appid = p.appid AND d.apiname = p.apiname
            WHERE p.steamid = ? AND p.appid = ? ORDER BY d.apiname""",
                (steamid, appid),
            )
        ]
        total = len(items)
        unlocked = sum(item["unlocked"] for item in items)
        return {
            "available": True,
            "items": items,
            "total": total,
            "unlocked": unlocked,
            "percent": round(unlocked / total * 100, 1) if total else None,
            "complete": total > 0 and total == unlocked,
            "error": None,
            "imported_at": sync["imported_at"],
            "refresh_required": bool(sync["refresh_required"]),
        }


def expire_achievements(path, steamid):
    with connect(path) as db, db:
        db.execute("UPDATE achievement_sync SET refresh_required = 1 WHERE steamid = ?", (steamid,))
        db.execute("DELETE FROM achievement_attempts WHERE steamid = ?", (steamid,))


def load_hltb(path, appid):
    if not Path(path).exists():
        return None
    with connect(path) as db:
        row = db.execute("SELECT * FROM hltb_data WHERE appid = ?", (appid,)).fetchone()
        return dict(row) if row else None


def save_hltb(path, appid, data):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO hltb_data
            (appid, hltb_id, matched_name, similarity, main_story, main_extra, completionist, url, imported_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(appid) DO UPDATE SET hltb_id=excluded.hltb_id, matched_name=excluded.matched_name,
            similarity=excluded.similarity, main_story=excluded.main_story, main_extra=excluded.main_extra,
            completionist=excluded.completionist, url=excluded.url, imported_at=excluded.imported_at, error=NULL""",
            (
                appid,
                data["hltb_id"],
                data["name"],
                data["similarity"],
                data["main_story"],
                data["main_extra"],
                data["completionist"],
                data["url"],
                data["imported_at"],
            ),
        )


def save_hltb_error(path, appid, data):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO hltb_data
            (appid, hltb_id, matched_name, similarity, main_story, main_extra, completionist, url, imported_at, error)
            VALUES (?, 0, ?, 0, NULL, NULL, NULL, NULL, ?, ?)
            ON CONFLICT(appid) DO UPDATE SET imported_at=excluded.imported_at, error=excluded.error""",
            (appid, data["name"], data["imported_at"], data["error"]),
        )


def load_hltb_summary(path, appids):
    if not Path(path).exists() or not appids:
        return {}
    marks = ",".join("?" for _ in appids)
    with connect(path) as db:
        return {
            row["appid"]: dict(row)
            for row in db.execute(f"SELECT * FROM hltb_data WHERE appid IN ({marks})", tuple(appids))
        }


def load_game_workspace(path, steamid, appid):
    with connect(path) as db:
        checklist_items = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM game_checklist WHERE steamid=? AND appid=? ORDER BY checklist_name COLLATE NOCASE, position,id",
                (steamid, appid),
            )
        ]
        groups = [dict(r) for r in db.execute("SELECT * FROM game_checklist_groups WHERE steamid=? AND appid=? ORDER BY position,id", (steamid, appid))]
        checklists = [{"id": group["id"], "name": group["name"], "items": []} for group in groups]
        for item in checklist_items:
            group = next((entry for entry in checklists if entry["name"] == item["checklist_name"]), None)
            if group is None:
                group = {"name": item["checklist_name"], "items": []}
                checklists.append(group)
            group["items"].append(item)
        return {
            "notes": [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM game_notes WHERE steamid=? AND appid=? ORDER BY updated_at DESC", (steamid, appid)
                )
            ],
            "checklist": checklist_items,
            "checklists": checklists,
            "links": [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM game_links WHERE steamid=? AND appid=? ORDER BY id DESC", (steamid, appid)
                )
            ],
        }


def add_game_note(path, steamid, appid, body):
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as db, db:
        db.execute(
            "INSERT INTO game_notes (steamid,appid,body,created_at,updated_at) VALUES (?,?,?,?,?)",
            (steamid, appid, body, now, now),
        )


def add_checklist_item(path, steamid, appid, label, checklist_name="Checklist geral"):
    checklist_name = checklist_name.strip() or "Checklist geral"
    with connect(path) as db, db:
        db.execute("INSERT OR IGNORE INTO game_checklist_groups (steamid,appid,name,position) VALUES (?,?,?,COALESCE((SELECT MAX(position)+1 FROM game_checklist_groups WHERE steamid=? AND appid=?),0))", (steamid, appid, checklist_name, steamid, appid))
        position = db.execute(
            "SELECT COALESCE(MAX(position),-1)+1 FROM game_checklist WHERE steamid=? AND appid=? AND checklist_name=?",
            (steamid, appid, checklist_name),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO game_checklist (steamid,appid,label,position,checklist_name) VALUES (?,?,?,?,?)",
            (steamid, appid, label, position, checklist_name),
        )


def create_checklist_group(path, steamid, appid, name):
    name = name.strip()
    if not name:
        return
    with connect(path) as db, db:
        position = db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM game_checklist_groups WHERE steamid=? AND appid=?", (steamid, appid)).fetchone()[0]
        db.execute("INSERT OR IGNORE INTO game_checklist_groups (steamid,appid,name,position) VALUES (?,?,?,?)", (steamid, appid, name, position))


def toggle_checklist_item(path, steamid, item_id, checked):
    with connect(path) as db, db:
        db.execute("UPDATE game_checklist SET checked=? WHERE id=? AND steamid=?", (int(checked), item_id, steamid))


def delete_checklist_item(path, steamid, appid, item_id):
    with connect(path) as db, db:
        cursor = db.execute(
            "DELETE FROM game_checklist WHERE id=? AND steamid=? AND appid=?",
            (item_id, steamid, appid),
        )
        return cursor.rowcount > 0


def delete_checklist_group(path, steamid, appid, group_id):
    with connect(path) as db, db:
        group = db.execute(
            "SELECT name FROM game_checklist_groups WHERE id=? AND steamid=? AND appid=?",
            (group_id, steamid, appid),
        ).fetchone()
        if group is None:
            return False
        db.execute(
            "DELETE FROM game_checklist WHERE steamid=? AND appid=? AND checklist_name=?",
            (steamid, appid, group["name"]),
        )
        db.execute(
            "DELETE FROM game_checklist_groups WHERE id=? AND steamid=? AND appid=?",
            (group_id, steamid, appid),
        )
        return True


def add_game_link(path, steamid, appid, label, url):
    with connect(path) as db, db:
        db.execute(
            "INSERT INTO game_links (steamid,appid,label,url,created_at) VALUES (?,?,?,?,?)",
            (steamid, appid, label, url, datetime.now(timezone.utc).isoformat()),
        )


def replace_game_workspace(path, steamid, appid, workspace):
    """Substitui notas, checklists e links por dados importados de Markdown."""
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as db, db:
        db.execute("DELETE FROM game_notes WHERE steamid=? AND appid=?", (steamid, appid))
        db.execute("DELETE FROM game_checklist WHERE steamid=? AND appid=?", (steamid, appid))
        db.execute("DELETE FROM game_checklist_groups WHERE steamid=? AND appid=?", (steamid, appid))
        db.execute("DELETE FROM game_links WHERE steamid=? AND appid=?", (steamid, appid))
        for body in workspace.get("notes", []):
            if str(body).strip():
                db.execute("INSERT INTO game_notes (steamid,appid,body,created_at,updated_at) VALUES (?,?,?,?,?)", (steamid, appid, str(body).strip(), now, now))
        for checklist in workspace.get("checklists", []):
            name = str(checklist.get("name", "Checklist geral")).strip() or "Checklist geral"
            position = db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM game_checklist_groups WHERE steamid=? AND appid=?", (steamid, appid)).fetchone()[0]
            db.execute("INSERT OR IGNORE INTO game_checklist_groups (steamid,appid,name,position) VALUES (?,?,?,?)", (steamid, appid, name, position))
            for position, item in enumerate(checklist.get("items", [])):
                label = str(item.get("label", "")).strip()
                if label:
                    db.execute("INSERT INTO game_checklist (steamid,appid,label,checked,position,checklist_name) VALUES (?,?,?,?,?,?)", (steamid, appid, label, int(bool(item.get("checked"))), position, name))
        for link in workspace.get("links", []):
            url = str(link.get("url", "")).strip()
            if url:
                db.execute("INSERT INTO game_links (steamid,appid,label,url,created_at) VALUES (?,?,?,?,?)", (steamid, appid, str(link.get("label") or url).strip(), url, now))


def load_trophy_guide(path, appid):
    if not Path(path).exists():
        return None
    with connect(path) as db:
        row = db.execute("SELECT * FROM trophy_guides WHERE appid = ?", (appid,)).fetchone()
        if not row:
            return None
        result = dict(row)
        for key in ("tags_json", "roadmap_json", "trophies_json"):
            raw = result.pop(key, None)
            result[key[:-5]] = json.loads(raw) if raw else []
        return result


def load_trophy_guide_summary(path, appids):
    if not Path(path).exists() or not appids:
        return {}
    marks = ",".join("?" for _ in appids)
    with connect(path) as db:
        return {
            row["appid"]: dict(row)
            for row in db.execute(
                f"SELECT appid, difficulty, playthroughs, hours, hours_text, trophy_count, error FROM trophy_guides WHERE appid IN ({marks})",
                tuple(appids),
            )
        }


def save_trophy_guide(path, appid, data):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO trophy_guides
            (appid, url, difficulty, playthroughs, hours, hours_text, trophy_count, tags_json, roadmap_json, trophies_json, imported_at, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(appid) DO UPDATE SET url=excluded.url, difficulty=excluded.difficulty,
            playthroughs=excluded.playthroughs, hours=excluded.hours, hours_text=excluded.hours_text,
            trophy_count=excluded.trophy_count,
            tags_json=excluded.tags_json, roadmap_json=excluded.roadmap_json, trophies_json=excluded.trophies_json,
            imported_at=excluded.imported_at, error=NULL""",
            (
                appid,
                data["url"],
                data.get("difficulty"),
                data.get("playthroughs"),
                data.get("hours"),
                data.get("hours_text"),
                data.get("trophy_count"),
                json.dumps(data.get("tags", []), ensure_ascii=False),
                json.dumps(data.get("roadmap", []), ensure_ascii=False),
                json.dumps(data.get("trophies", []), ensure_ascii=False),
                data["imported_at"],
            ),
        )


def save_trophy_guide_error(path, appid, data):
    with connect(path) as db, db:
        db.execute(
            """INSERT INTO trophy_guides
            (appid, url, difficulty, playthroughs, hours, hours_text, trophy_count, tags_json, roadmap_json, trophies_json, imported_at, error)
            VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, '[]', '[]', '[]', ?, ?)
            ON CONFLICT(appid) DO UPDATE SET url=excluded.url, imported_at=excluded.imported_at,
            error=excluded.error""",
            (appid, data["url"], data["imported_at"], data["error"]),
        )
