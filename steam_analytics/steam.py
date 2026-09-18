"""Cliente da Steam Web API, sem dependências externas."""

import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class SteamError(Exception):
    """Erro que pode ser apresentado sem expor a chave da API."""

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def valid_steamid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{17}", value) is not None


class SteamClient:
    def __init__(self, api_key, *, opener=None, sleep=time.sleep):
        if not api_key or not api_key.strip():
            raise SteamError("Configure STEAM_API_KEY no arquivo .env do servidor para consultar a biblioteca.", 503)
        self._api_key = api_key.strip()
        if opener is None:
            proxy = os.environ.get("STEAM_PROXY", "").strip()
            self._open = build_opener(ProxyHandler({"http": proxy, "https": proxy} if proxy else {})).open
        else:
            self._open = opener
        self._sleep = sleep

    def _get(self, endpoint, params, *, root="response"):
        query = urlencode({"key": self._api_key, "format": "json", **params})
        request = Request(
            f"https://api.steampowered.com/{endpoint}/?{query}",
            headers={"User-Agent": "SteamAnalytics/0.1", "Accept": "application/json"},
        )
        for attempt in range(3):
            try:
                with self._open(request, timeout=30) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or not isinstance(payload.get(root), dict):
                    raise SteamError("A Steam retornou uma resposta inesperada.")
                return payload[root]
            except HTTPError as error:
                status = error.code
                error.close()
                if status in (401, 403):
                    raise SteamError("A Steam recusou o acesso. Confira sua STEAM_API_KEY.") from None
                if status == 429 or 500 <= status <= 599:
                    if attempt < 2:
                        self._sleep(2**attempt)
                        continue
                    raise SteamError("Steam indisponível ou limite de consultas atingido. Tente mais tarde.") from None
                raise SteamError(f"A consulta à Steam falhou (HTTP {status}).") from None
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    self._sleep(2**attempt)
                    continue
                raise SteamError("Não foi possível conectar à Steam. Confira a conexão e tente novamente.") from None
            except (ValueError, UnicodeError):
                raise SteamError("A Steam retornou uma resposta JSON inválida.") from None

    def resolve_profile(self, profile):
        value = profile.strip()
        if valid_steamid(value):
            return value
        if value.startswith(("steamcommunity.com/", "www.steamcommunity.com/")):
            value = "https://" + value
        if "://" in value:
            try:
                parsed = urlsplit(value)
            except ValueError:
                raise SteamError("Link de perfil Steam inválido.", 422) from None
            parts = parsed.path.strip("/").split("/")
            if (
                parsed.scheme not in ("http", "https")
                or parsed.netloc.lower() not in ("steamcommunity.com", "www.steamcommunity.com")
                or len(parts) != 2
                or parts[0] not in ("id", "profiles")
            ):
                raise SteamError("Informe um link Steam /id/... ou /profiles/..., ou um SteamID64.", 422)
            value = parts[1]
            if parts[0] == "profiles":
                if not valid_steamid(value):
                    raise SteamError("SteamID64 inválido: use os 17 dígitos do perfil.", 422)
                return value
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise SteamError("Informe um SteamID64 ou um link de perfil Steam válido.", 422)
        response = self._get("ISteamUser/ResolveVanityURL/v1", {"vanityurl": value, "url_type": 1})
        steamid = response.get("steamid")
        if response.get("success") != 1 or not valid_steamid(steamid):
            raise SteamError("Perfil personalizado não encontrado na Steam. Confira o link informado.", 404)
        return steamid

    def owned_games(self, steamid):
        response = self._get(
            "IPlayerService/GetOwnedGames/v1",
            {
                "input_json": json.dumps(
                    {
                        "steamid": steamid,
                        "include_appinfo": True,
                        "include_played_free_games": True,
                    }
                ),
            },
        )
        if "game_count" not in response:
            raise SteamError(
                "A Steam não disponibilizou a biblioteca. Confira o perfil e a privacidade de "
                "'Detalhes dos jogos'. Nenhum dado salvo foi alterado."
            )
        count = response["game_count"]
        games = response.get("games", [] if count == 0 else None)
        if type(count) is not int or count < 0 or not isinstance(games, list) or len(games) != count:
            raise SteamError("A Steam retornou uma biblioteca incompleta ou inválida; importação cancelada.")
        normalized = [normalize_game(game) for game in games]
        if len({game["appid"] for game in normalized}) != count:
            raise SteamError("A Steam retornou jogos duplicados; importação cancelada.")
        return sorted(normalized, key=lambda game: (game["name"].casefold(), game["appid"]))

    def profile_summary(self, steamid):
        response = self._get("ISteamUser/GetPlayerSummaries/v2", {"steamids": steamid})
        players = response.get("players")
        if not isinstance(players, list) or not players:
            raise SteamError("A Steam não disponibilizou o nome deste perfil.")
        player = next((item for item in players if isinstance(item, dict) and item.get("steamid") == steamid), None)
        name = player.get("personaname") if player else None
        if not isinstance(name, str) or not name.strip():
            raise SteamError("A Steam não disponibilizou o nome deste perfil.")
        return {"steamid": steamid, "personaname": name.strip()}

    def player_achievements(self, steamid, appid):
        stats = self._get(
            "ISteamUserStats/GetPlayerAchievements/v1",
            {
                "steamid": steamid,
                "appid": appid,
                "l": "brazilian",
            },
            root="playerstats",
        )
        if stats.get("success") is not True:
            raise SteamError(
                "A Steam não disponibilizou as conquistas deste jogo. Ele pode não ter conquistas ou os dados podem estar privados."
            )
        achievements = stats.get("achievements")
        if not isinstance(achievements, list):
            raise SteamError("A Steam não informou a lista de conquistas deste jogo.")
        items = []
        for item in achievements:
            if (
                not isinstance(item, dict)
                or type(item.get("achieved")) is not int
                or item["achieved"] not in (0, 1)
                or not isinstance(item.get("apiname"), str)
            ):
                raise SteamError("A Steam retornou conquistas em um formato inesperado.")
            name = item.get("name") or item["apiname"]
            description = item.get("description") or ""
            if not isinstance(name, str) or not isinstance(description, str):
                raise SteamError("A Steam retornou conquistas em um formato inesperado.")
            items.append(
                {
                    "apiname": item["apiname"],
                    "name": name,
                    "description": description,
                    "unlocked": item["achieved"] == 1,
                }
            )
        if len({item["apiname"] for item in items}) != len(items):
            raise SteamError("A Steam retornou conquistas duplicadas.")
        total = len(items)
        unlocked = sum(item["unlocked"] for item in items)
        return {
            "available": True,
            "total": total,
            "unlocked": unlocked,
            "percent": round(unlocked / total * 100, 1) if total else None,
            "complete": total > 0 and unlocked == total,
            "items": items,
            "error": None,
        }

    def achievement_schema(self, appid):
        game = self._get("ISteamUserStats/GetSchemaForGame/v2", {"appid": appid, "l": "brazilian"}, root="game")
        achievements = game.get("availableGameStats", {}).get("achievements")
        if not isinstance(achievements, list):
            raise SteamError("A Steam não disponibilizou os ícones deste jogo.")
        result = {}
        for item in achievements:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            result[item["name"]] = {
                "icon": item.get("icon") if isinstance(item.get("icon"), str) else None,
                "icon_gray": item.get("icongray") if isinstance(item.get("icongray"), str) else None,
            }
        return result


def normalize_game(game):
    if not isinstance(game, dict) or type(game.get("appid")) is not int or game["appid"] <= 0:
        raise SteamError("Jogo sem appid válido na resposta da Steam; importação cancelada.")
    appid = game["appid"]
    name = game.get("name") or f"App {appid}"
    if not isinstance(name, str):
        raise SteamError("Nome de jogo inválido na resposta da Steam.")
    result = {"appid": appid, "name": name}
    for field in ("playtime_forever", "playtime_2weeks", "rtime_last_played"):
        value = game.get(field)
        if value is not None and (type(value) is not int or value < 0):
            raise SteamError("Tempo de jogo inválido na resposta da Steam.")
        result[field] = value
    minutes = result["playtime_forever"]
    result["playtime_hours"] = round(minutes / 60, 2) if minutes is not None else None
    result["store_url"] = f"https://store.steampowered.com/app/{appid}/"
    return result
