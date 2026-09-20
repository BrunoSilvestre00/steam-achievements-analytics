CREATE TABLE IF NOT EXISTS libraries (
    steamid TEXT PRIMARY KEY,
    personaname TEXT,
    imported_at TEXT NOT NULL,
    game_count INTEGER NOT NULL CHECK (game_count >= 0)
);

CREATE TABLE IF NOT EXISTS games (
    appid INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS library_games (
    steamid TEXT NOT NULL REFERENCES libraries(steamid),
    appid INTEGER NOT NULL REFERENCES games(appid),
    playtime_forever INTEGER,
    playtime_2weeks INTEGER,
    rtime_last_played INTEGER,
    source TEXT NOT NULL DEFAULT 'steam',
    PRIMARY KEY (steamid, appid)
);

CREATE TABLE IF NOT EXISTS achievement_definitions (
    appid INTEGER NOT NULL REFERENCES games(appid),
    apiname TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    icon TEXT,
    icon_gray TEXT,
    is_online INTEGER NOT NULL DEFAULT 0,
    is_hidden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (appid, apiname)
);

CREATE TABLE IF NOT EXISTS player_achievements (
    steamid TEXT NOT NULL REFERENCES libraries(steamid),
    appid INTEGER NOT NULL,
    apiname TEXT NOT NULL,
    unlocked INTEGER NOT NULL CHECK (unlocked IN (0, 1)),
    PRIMARY KEY (steamid, appid, apiname),
    FOREIGN KEY (appid, apiname) REFERENCES achievement_definitions(appid, apiname)
);

CREATE TABLE IF NOT EXISTS achievement_sync (
    steamid TEXT NOT NULL REFERENCES libraries(steamid),
    appid INTEGER NOT NULL REFERENCES games(appid),
    imported_at TEXT NOT NULL,
    refresh_required INTEGER NOT NULL DEFAULT 0 CHECK (refresh_required IN (0, 1)),
    PRIMARY KEY (steamid, appid)
);

CREATE TABLE IF NOT EXISTS achievement_attempts (
    steamid TEXT NOT NULL REFERENCES libraries(steamid),
    appid INTEGER NOT NULL REFERENCES games(appid),
    checked_at TEXT NOT NULL,
    error TEXT,
    PRIMARY KEY (steamid, appid)
);

CREATE TABLE IF NOT EXISTS hltb_data (
    appid INTEGER PRIMARY KEY REFERENCES games(appid),
    hltb_id INTEGER NOT NULL,
    matched_name TEXT NOT NULL,
    similarity REAL NOT NULL CHECK (similarity >= 0 AND similarity <= 1),
    main_story REAL,
    main_extra REAL,
    completionist REAL,
    url TEXT,
    imported_at TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS game_favorites (
    steamid TEXT NOT NULL REFERENCES libraries(steamid),
    appid INTEGER NOT NULL REFERENCES games(appid),
    PRIMARY KEY (steamid, appid)
);

CREATE TABLE IF NOT EXISTS trophy_guides (
    appid INTEGER PRIMARY KEY REFERENCES games(appid),
    url TEXT NOT NULL,
    difficulty REAL,
    playthroughs INTEGER,
    hours REAL,
    hours_text TEXT,
    trophy_count INTEGER,
    imported_at TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS game_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid),
    body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS game_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid),
    label TEXT NOT NULL, checked INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)), position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    steamid TEXT NOT NULL REFERENCES libraries(steamid), appid INTEGER NOT NULL REFERENCES games(appid),
    label TEXT NOT NULL, url TEXT NOT NULL, created_at TEXT NOT NULL
);
