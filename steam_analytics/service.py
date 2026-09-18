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
    save_hltb,
    save_hltb_error,
    save_library,
    save_trophy_guide,
    save_trophy_guide_error,
    update_personaname,
)
from .trophy import fetch_trophy_guide


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
        self.hltb_client = None

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

    def progress(self, steamid, *, update=False):
        if not valid_steamid(steamid):
            raise SteamError("SteamID inválido.", 422)
        if load_library(self.database, steamid) is None:
            raise SteamError("Importe a biblioteca antes de consultar os percentuais.", 404)
        if update and self._progress_lock.acquire(blocking=False):
            try:
                pending = [item for item in load_progress(self.database, steamid) if item["needs_update"]]
                for item in pending[:3]:
                    self.achievements(steamid, item["appid"])
            finally:
                self._progress_lock.release()
        games = load_progress(self.database, steamid)
        return {"games": games, "pending": sum(item["needs_update"] for item in games)}

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
                    result["items"] = [{**item, **assets.get(item["apiname"], {})} for item in result["items"]]
                except SteamError:
                    pass
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
            now = datetime.now(timezone.utc)
            if cached and not refresh:
                if not cached.get("personaname") and (self.client is None or isinstance(self.client, SteamClient)):
                    try:
                        profile_client = self.client or SteamClient(self.api_key)
                        cached["personaname"] = profile_client.profile_summary(steamid)["personaname"]
                        update_personaname(self.database, steamid, cached["personaname"])
                    except SteamError:
                        pass
                age = (now - datetime.fromisoformat(cached["imported_at"])).total_seconds()
                if age < self.cache_seconds:
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
            return {
                "steamid": steamid,
                "personaname": personaname or (cached or {}).get("personaname"),
                "imported_at": imported_at,
                "game_count": len(games),
                "games": games,
                "cached": False,
                "warning": None,
            }
