import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, RLock
from time import monotonic

from .hltb import HLTBClient
from .steam import SteamClient, SteamError, valid_steamid
from .storage import (
    expire_achievements,
    load_achievements,
    load_hltb,
    load_hltb_summary,
    load_library,
    load_progress,
    load_trophy_guide,
    save_achievement_failure,
    save_achievements,
    save_external_games,
    save_hltb,
    save_hltb_error,
    save_library,
    save_trophy_guide,
    save_trophy_guide_error,
    update_game_playtime,
    update_game_source,
    update_personaname,
)
from .trophy import fetch_trophy_guide, parse_trophy_guide

ONLINE_ACHIEVEMENT_HINTS = re.compile(
    r"\b(?:online|multiplayer|co-?op|cooperative|pvp|versus|matchmaking|ranked|leaderboard)\b"
    r"|\b(?:with|against)\s+(?:a\s+)?(?:friend|friends|player|players|opponent)\b",
    re.IGNORECASE,
)


def mark_online_achievements(data):
    return {
        **data,
        "items": [
            {
                **item,
                "is_online": bool(
                    ONLINE_ACHIEVEMENT_HINTS.search(
                        f"{item.get('name', '')} {item.get('description', '')}"
                    )
                ),
            }
            for item in data.get("items", [])
        ],
    }


class LibraryService:
    def __init__(self, api_key, database, *, client=None, cache_seconds=900):
        self.api_key = api_key
        self.database = Path(database)
        self.client = client
        self.cache_seconds = cache_seconds
        self._lock = Lock()
        self._achievement_lock = Lock()
        self._achievements = OrderedDict()
        self._progress_lock = Lock()
        self._hltb_lock = RLock()
        self._refresh_state_lock = Lock()
        self._refresh_cancelled = set()
        self.hltb_client = None

    def begin_refresh(self, steamid):
        with self._refresh_state_lock:
            self._refresh_cancelled.discard(steamid)

    def cancel_refresh(self, steamid):
        with self._refresh_state_lock:
            self._refresh_cancelled.add(steamid)

    def finish_refresh(self, steamid):
        with self._refresh_state_lock:
            self._refresh_cancelled.discard(steamid)

    def refresh_cancelled(self, steamid):
        with self._refresh_state_lock:
            return steamid in self._refresh_cancelled

    def hltb(self, appid, title, *, refresh=False):
        cached = load_hltb(self.database, appid)
        if cached and not refresh:
            return cached
        with self._hltb_lock:
            cached = load_hltb(self.database, appid)
            if cached and not refresh:
                return cached
            try:
                result = (self.hltb_client or HLTBClient()).search(title)
                result["imported_at"] = datetime.now(timezone.utc).isoformat()
                save_hltb(self.database, appid, result)
                return result
            except Exception as error:
                result = {"name": title, "error": str(error), "imported_at": datetime.now(timezone.utc).isoformat()}
                save_hltb_error(self.database, appid, result)
                return result

    def hltb_progress(self, steamid, *, update=False, limit=20):
        library = load_library(self.database, steamid)
        if library is None:
            raise SteamError("Importe a biblioteca antes de consultar os tempos.", 404)
        appids = [game["appid"] for game in library["games"]]
        saved = load_hltb_summary(self.database, appids)
        missing = [game for game in library["games"] if game["appid"] not in saved]
        if update:
            with self._hltb_lock:
                # Mantemos as consultas sequenciais para reduzir a chance de bloqueio,
                # mas aproveitamos cada clique para preencher um lote útil.
                for game in missing[:limit]:
                    if self.refresh_cancelled(steamid):
                        break
                    self.hltb(game["appid"], game["name"])
            saved = load_hltb_summary(self.database, appids)
        return {
            "games": [
                {"appid": appid, "completionist": row.get("completionist"), "error": row.get("error")}
                for appid, row in saved.items()
            ],
            "pending": len([appid for appid in appids if appid not in saved]),
        }

    def trophy_guide(self, appid, url, *, refresh=False):
        cached = load_trophy_guide(self.database, appid)
        if cached and not refresh and cached.get("url") == url:
            return cached
        try:
            result = fetch_trophy_guide(url)
            save_trophy_guide(self.database, appid, result)
            return {**result, "appid": appid, "error": None}
        except Exception as error:
            result = {"url": url, "error": str(error), "imported_at": datetime.now(timezone.utc).isoformat()}
            save_trophy_guide_error(self.database, appid, result)
            return {**result, "appid": appid}

    def trophy_guide_html(self, appid, url, html):
        try:
            result = parse_trophy_guide(url, html, translate=True)
            save_trophy_guide(self.database, appid, result)
            return {**result, "appid": appid, "error": None}
        except Exception as error:
            result = {"url": url, "error": str(error), "imported_at": datetime.now(timezone.utc).isoformat()}
            save_trophy_guide_error(self.database, appid, result)
            return {**result, "appid": appid}

    def progress(self, steamid, *, update=False):
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido.", 422)
        if load_library(self.database, steamid) is None:
            raise SteamError("Importe a biblioteca antes de consultar os percentuais.", 404)
        if update and self._progress_lock.acquire(blocking=False):
            try:
                pending = [
                    item
                    for item in load_progress(self.database, steamid)
                    if item["needs_update"] and item.get("source") != "external"
                ]
                for item in pending[:3]:
                    self.achievements(steamid, item["appid"])
            finally:
                self._progress_lock.release()
        games = load_progress(self.database, steamid)
        return {
            "games": games,
            "pending": sum(item["needs_update"] and item.get("source") != "external" for item in games),
        }

    def achievements(self, steamid, appid):
        key = (steamid, appid)
        with self._achievement_lock:
            entry = self._achievements.get(key)
            if entry and monotonic() - entry[0] < 300:
                return entry[1]
        cached = load_achievements(self.database, steamid, appid)
        now = datetime.now(timezone.utc)
        if (
            cached
            and not cached["refresh_required"]
            and (now - datetime.fromisoformat(cached["imported_at"])).total_seconds() < 300
        ):
            return cached
        try:
            client = self.client or SteamClient(self.api_key)
            result = client.player_achievements(steamid, appid)
            if isinstance(client, SteamClient):
                try:
                    assets = client.achievement_schema(appid)
                    result["items"] = [
                        {
                            **item,
                            **{key: value for key, value in assets.get(item["apiname"], {}).items() if value},
                        }
                        for item in result["items"]
                    ]
                except SteamError:
                    pass
            result = mark_online_achievements(result)
            save_achievements(self.database, steamid, appid, result, now.isoformat())
            result = {**result, "imported_at": now.isoformat()}
        except SteamError as error:
            save_achievement_failure(self.database, steamid, appid, str(error))
            result = (
                {**cached, "error": f"Exibindo conquistas salvas; não foi possível atualizar. {error}"}
                if cached
                else {"available": False, "error": str(error)}
            )
        with self._achievement_lock:
            self._achievements[key] = (monotonic(), result)
            self._achievements.move_to_end(key)
            while len(self._achievements) > 256:
                self._achievements.popitem(last=False)
        return result

    def get_library(self, steamid, *, refresh=False):
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido. Use os 17 dígitos do seu SteamID64.", 422)
        # Serializa consultas para evitar chamadas e gravações concorrentes no uso local.
        with self._lock:
            cached = load_library(self.database, steamid)
            if cached and not refresh and self.cache_seconds > 0:
                if not cached.get("personaname") and (self.client is None or isinstance(self.client, SteamClient)):
                    try:
                        profile_client = self.client or SteamClient(self.api_key)
                        cached["personaname"] = profile_client.profile_summary(steamid)["personaname"]
                        update_personaname(self.database, steamid, cached["personaname"])
                    except SteamError:
                        pass
                # A biblioteca só é atualizada por uma ação explícita do usuário.
                # A entrada na listagem não deve consultar a Steam novamente.
                return {**cached, "cached": True, "warning": None}
            try:
                client = self.client or SteamClient(self.api_key)
                games = client.owned_games(steamid)
            except SteamError as error:
                if cached:
                    return {
                        **cached,
                        "cached": True,
                        "warning": f"Não foi possível atualizar. Exibindo a última biblioteca salva. {error}",
                    }
                raise
            imported_at = datetime.now(timezone.utc).isoformat()
            personaname = None
            if isinstance(client, SteamClient):
                try:
                    personaname = client.profile_summary(steamid)["personaname"]
                except SteamError:
                    personaname = cached.get("personaname") if cached else None
            save_library(self.database, steamid, games, imported_at, personaname)
            if refresh:
                expire_achievements(self.database, steamid)
                with self._achievement_lock:
                    for key in list(self._achievements):
                        if key[0] == steamid:
                            del self._achievements[key]
            saved = load_library(self.database, steamid)
            return {
                "steamid": steamid,
                "personaname": personaname or (cached or {}).get("personaname"),
                "imported_at": imported_at,
                "game_count": saved["game_count"] if saved else len(games),
                "games": saved["games"] if saved else games,
                "cached": False,
                "warning": None,
            }

    def import_perfect_games(self, steamid):
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido.", 422)
        if load_library(self.database, steamid) is None:
            raise SteamError("Importe a biblioteca antes de buscar platinas públicas.", 404)
        client = self.client or SteamClient(self.api_key)
        perfect = client.perfect_games(steamid)
        current = load_library(self.database, steamid)
        known = {game["appid"] for game in current["games"]}
        missing = [game for game in perfect if game["appid"] not in known]
        save_external_games(self.database, steamid, missing, "family")
        return {"found": len(perfect), "added": len(missing), "games": missing}

    def add_external_game(self, steamid, appid):
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido.", 422)
        if load_library(self.database, steamid) is None:
            raise SteamError("Importe a biblioteca antes de adicionar um jogo.", 404)
        if not isinstance(appid, int) or appid <= 0:
            raise SteamError("Informe um AppID Steam válido.", 422)
        client = self.client or SteamClient(self.api_key)
        game = client.store_game(appid)
        current = load_library(self.database, steamid)
        exists = any(item["appid"] == appid for item in current["games"])
        if not exists:
            save_external_games(self.database, steamid, [game], "external")
        return {"added": not exists, "game": game}

    def import_browser_games(self, steamid, games):
        """Importa jogos encontrados pelo navegador na página autenticada da Steam."""
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido.", 422)
        current = load_library(self.database, steamid)
        if current is None:
            raise SteamError("Carregue a biblioteca antes de importar dados da Steam.", 404)
        known = {game["appid"] for game in current["games"]}
        existing_sources = {game["appid"]: game.get("source") for game in current["games"]}
        clean = {}
        family_updates = []
        for item in games if isinstance(games, list) else []:
            try:
                appid = int(item.get("appid"))
            except (AttributeError, TypeError, ValueError):
                continue
            name = str(item.get("name") or f"Steam App {appid}").strip()[:200]
            if appid > 0 and appid not in known:
                clean[appid] = {"appid": appid, "name": name}
            elif appid > 0 and item.get("source") == "perfect" and existing_sources.get(appid) == "external":
                family_updates.append({"appid": appid, "name": name})
        missing = list(clean.values())
        save_external_games(self.database, steamid, missing, "family")
        for game in family_updates:
            update_game_source(self.database, steamid, game["appid"], "family")
        # Consulta as conquistas apenas dos jogos novos para que a porcentagem
        # e o contador de platinas sejam atualizados imediatamente.
        for game in [*missing, *family_updates]:
            try:
                self.achievements(steamid, game["appid"])
            except SteamError:
                pass
        return {
            "found": len(games) if isinstance(games, list) else 0,
            "added": len(missing),
            "updated": len(family_updates),
        }

    def update_playtime(self, steamid, appid):
        client = self.client or SteamClient(self.api_key)
        if not isinstance(client, SteamClient):
            return None
        result = client.single_game_playtime(steamid, appid)
        if result.get("playtime_forever") is not None:
            update_game_playtime(
                self.database,
                steamid,
                appid,
                result["playtime_forever"],
                result.get("playtime_2weeks"),
            )
        return result
