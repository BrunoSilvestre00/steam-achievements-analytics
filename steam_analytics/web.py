"""Frontend renderizado em Python e API JSON para consultas futuras."""

import base64
import difflib
import json
import os
import re
import sqlite3
import unicodedata
import zlib
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .cache import RedisCache
from .config import ROOT, load_env
from .service import LibraryService
from .steam import SteamClient, SteamError, valid_steamid
from .storage import (
    add_checklist_item,
    add_game_link,
    add_game_note,
    connect,
    load_game_workspace,
    load_hltb_summary,
    load_progress,
    load_trophy_guide,
    load_trophy_guide_summary,
    toggle_checklist_item,
)

PACKAGE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PACKAGE / "templates"))
templates.env.filters["hours"] = lambda value: (
    f"{value / 60:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".") if value is not None else "—"
)
templates.env.filters["timestamp"] = lambda value: datetime.fromisoformat(value).strftime("%d/%m/%Y às %H:%M UTC")
templates.env.filters["percentage"] = lambda value: f"{value:g}".replace(".", ",")


def sort_by_progress(games, direction):
    return sorted(
        games,
        key=lambda g: (
            g["progress"]["percent"] is None,
            (g["progress"]["percent"] or 0) * (-1 if direction == "percent_desc" else 1),
            g["name"].casefold(),
            g["appid"],
        ),
    )


def _match_key(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", normalized.casefold()).strip()


def pair_trophy_guide(guide, achievements):
    trophies = (guide or {}).get("trophies") or []
    steam_items = (achievements or {}).get("items") or []
    remaining = {index: item for index, item in enumerate(steam_items)}
    paired = []
    unpaired_guide = []
    for trophy in trophies:
        trophy_key = _match_key(trophy.get("name_pt") or trophy.get("name"))
        best_index = None
        best_score = 0.0
        for index, achievement in remaining.items():
            achievement_key = _match_key(achievement.get("name"))
            score = difflib.SequenceMatcher(None, trophy_key, achievement_key).ratio()
            if trophy_key and (trophy_key in achievement_key or achievement_key in trophy_key):
                score = max(score, 0.92)
            if score > best_score:
                best_index, best_score = index, score
        if best_index is not None and best_score >= 0.72:
            paired.append({"trophy": trophy, "achievement": remaining.pop(best_index), "score": round(best_score, 2)})
        else:
            unpaired_guide.append(trophy)
    return {"paired": paired, "unpaired_guide": unpaired_guide, "unpaired_achievements": list(remaining.values())}


def create_app(*, service=None):
    load_env()

    @asynccontextmanager
    async def lifespan(app):
        with connect(app.state.library.database):
            pass
        yield

    app = FastAPI(
        title="Steam Achievement Analytics",
        description="Biblioteca Steam para planejar seus próximos 100%.",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://steamcommunity.com", "https://www.steamcommunity.com"],
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )
    app.state.library = service or LibraryService(os.environ.get("STEAM_API_KEY", ""), ROOT / "data" / "steam.sqlite3")
    app.state.cache = RedisCache(ttl=300)
    app.mount("/static", StaticFiles(directory=str(PACKAGE / "static")), name="static")

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self' https://cdn.akamai.steamstatic.com https://steamcdn-a.akamaihd.net; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if not request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def render(request, name, context=None, status_code=200):
        return templates.TemplateResponse(request=request, name=name, context=context or {}, status_code=status_code)

    @app.exception_handler(SteamError)
    async def steam_error(request, error):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": str(error)}, status_code=error.status_code)
        if request.url.path == "/profile":
            return render(
                request,
                "home.html",
                {
                    "profile_input": request.query_params.get("profile", ""),
                    "profile_error": str(error),
                },
                error.status_code,
            )
        return render(request, "error.html", {"error": str(error)}, error.status_code)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, error):
        message = "Não foi possível acessar a biblioteca salva. Confira as permissões da pasta data."
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": message}, status_code=500)
        return render(request, "error.html", {"error": message}, 500)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return render(request, "home.html", {"profile_input": os.environ.get("STEAM_PROFILE", "")})

    @app.get("/profile/{steamid}/collect", response_class=HTMLResponse, include_in_schema=False)
    def collect_page(
        request: Request,
        steamid: str,
        kind: Literal["steam", "trophy"] = "steam",
        game: int | None = Query(default=None, gt=0),
    ):
        return render(request, "collector.html", {"steamid": steamid, "kind": kind, "appid": game})

    @app.get("/profile", include_in_schema=False)
    def open_profile(profile: str = Query(min_length=1, max_length=250)):
        value = profile.strip()
        if valid_steamid(value):
            steamid = value
        else:
            steamid = SteamClient(app.state.library.api_key).resolve_profile(value)
        return RedirectResponse(f"/profile/{steamid}", status_code=303)

    @app.get("/profile/{steamid}", response_class=HTMLResponse)
    def profile_page(
        request: Request,
        steamid: str,
        q: str = Query(default="", max_length=200),
        sort: Literal[
            "name", "hours", "recent", "percent_desc", "percent_asc", "hltb_desc", "hltb_asc",
            "guide_difficulty_desc", "guide_difficulty_asc", "guide_hours_desc", "guide_hours_asc"
        ] = "percent_desc",
        played: Literal["all", "played", "unplayed", "platinum", "not_platinum", "near_platinum"] = "all",
        game: int | None = Query(default=None, gt=0),
        updated: str = Query(default="", max_length=20),
        notice: str = Query(default="", max_length=240),
        sync: bool = Query(default=False),
        steam_import: str = Query(default="", max_length=500000),
        trophy_guide_import: str = Query(default="", max_length=500000),
    ):
        steam_import_payload = ""
        if steam_import:
            try:
                padding = "=" * (-len(steam_import) % 4)
                steam_import_payload = base64.urlsafe_b64decode(steam_import + padding).decode("utf-8")
                parsed_import = json.loads(steam_import_payload)
                if not isinstance(parsed_import, dict) or not isinstance(parsed_import.get("games"), list):
                    steam_import_payload = ""
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                steam_import_payload = ""
        trophy_guide_import_payload = ""
        if trophy_guide_import:
            try:
                padding = "=" * (-len(trophy_guide_import) % 4)
                decoded = base64.urlsafe_b64decode(trophy_guide_import + padding).decode("utf-8")
                if json.loads(decoded).get("url") and json.loads(decoded).get("html_b64"):
                    trophy_guide_import_payload = decoded
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                trophy_guide_import_payload = ""
        library = app.state.library.get_library(steamid)
        all_games = library["games"]
        if sort in ("hltb_desc", "hltb_asc"):
            # Preenche alguns valores ausentes antes de ordenar, para que a opção
            # continue útil mesmo quando a biblioteca ainda não foi consultada.
            app.state.library.hltb_progress(steamid, update=True)
        progress = {item["appid"]: item for item in load_progress(app.state.library.database, steamid)}
        hltb_summary = load_hltb_summary(app.state.library.database, [item["appid"] for item in all_games])
        trophy_summary = load_trophy_guide_summary(app.state.library.database, [item["appid"] for item in all_games])
        for rank, item in enumerate(sorted(all_games, key=lambda g: (g["name"].casefold(), g["appid"]))):
            item["progress"] = progress[item["appid"]]
            item["hltb"] = hltb_summary.get(item["appid"])
            item["trophy_guide"] = trophy_summary.get(item["appid"])
            item["name_order"] = rank
        # A busca por nome acontece no navegador para evitar recarregar a página
        # e manter toda a biblioteca disponível para o filtro instantâneo.
        games = list(all_games)
        if played == "played":
            games = [g for g in games if (g["playtime_forever"] or 0) > 0]
        elif played == "unplayed":
            games = [g for g in games if g["playtime_forever"] == 0]
        elif played == "platinum":
            games = [g for g in games if g["progress"]["percent"] == 100]
        elif played == "not_platinum":
            games = [g for g in games if g["progress"]["percent"] != 100]
        elif played == "near_platinum":
            games = [g for g in games if g["progress"]["percent"] is not None and 70 <= g["progress"]["percent"] < 100]
        if sort in ("percent_desc", "percent_asc"):
            games = sort_by_progress(games, sort)
        elif sort in ("hltb_desc", "hltb_asc"):
            reverse = sort == "hltb_desc"
            games = sorted(
                games,
                key=lambda g: (
                    g["hltb"] is None or g["hltb"].get("completionist") is None,
                    -((g["hltb"] or {}).get("completionist") or 0)
                    if reverse
                    else ((g["hltb"] or {}).get("completionist") or 0),
                    g["name"].casefold(),
                ),
            )
        elif sort in ("guide_difficulty_desc", "guide_difficulty_asc", "guide_hours_desc", "guide_hours_asc"):
            guide_field = "difficulty" if "difficulty" in sort else "hours"
            reverse = sort.endswith("_desc")
            games = sorted(
                games,
                key=lambda g: (
                    (g.get("trophy_guide") or {}).get(guide_field) is None,
                    -((g.get("trophy_guide") or {}).get(guide_field) or 0)
                    if reverse
                    else ((g.get("trophy_guide") or {}).get(guide_field) or 0),
                    g["name"].casefold(),
                ),
            )
        elif sort == "hours":
            games = sorted(
                games,
                key=lambda g: (
                    -(g["playtime_forever"] if g["playtime_forever"] is not None else -1),
                    g["name"].casefold(),
                ),
            )
        elif sort == "recent":
            games = sorted(games, key=lambda g: (-(g["rtime_last_played"] or 0), g["name"].casefold()))
        else:
            games = sorted(games, key=lambda g: g["name"].casefold())
        known = [g["playtime_forever"] for g in all_games if g["playtime_forever"] is not None]
        platinum_games = sorted(
            (g for g in all_games if progress.get(g["appid"], {}).get("percent") == 100),
            key=lambda g: g.get("rtime_last_played") or 0,
            reverse=True,
        )
        platinum_years = {}
        for platinum in platinum_games:
            if platinum.get("rtime_last_played"):
                year = datetime.fromtimestamp(platinum["rtime_last_played"]).year
                platinum_years[year] = platinum_years.get(year, 0) + 1
        selected = next((g for g in all_games if g["appid"] == game), games[0] if games else None)
        if selected and selected.get("source") == "external" and selected.get("playtime_forever") is None:
            try:
                playtime = app.state.library.update_playtime(steamid, selected["appid"])
                if playtime and playtime.get("playtime_forever") is not None:
                    selected.update(playtime)
                    selected["playtime_hours"] = round(playtime["playtime_forever"] / 60, 2)
            except SteamError:
                pass
        achievements = app.state.library.achievements(steamid, selected["appid"]) if selected else None
        if selected:
            app.state.cache.invalidate(f"progress:{steamid}")
        hltb = app.state.library.hltb(selected["appid"], selected["name"]) if selected else None
        trophy_guide = load_trophy_guide(app.state.library.database, selected["appid"]) if selected else None
        if selected is not None:
            selected["hltb"] = hltb
        progress = {item["appid"]: item for item in load_progress(app.state.library.database, steamid)}
        for item in all_games:
            item["progress"] = progress[item["appid"]]
        if sort in ("percent_desc", "percent_asc"):
            games = sort_by_progress(games, sort)
        return render(
            request,
            "profile.html",
            {
                "library": library,
                "games": games,
                "q": q,
                "sort": sort,
                "played": played,
                "selected": selected,
                "achievements": achievements,
                "open_modal": game is not None,
                "hltb": hltb,
                "trophy_guide": trophy_guide,
                "progress_pending": sum(item["needs_update"] for item in progress.values()),
                "updated": updated,
                "notice": notice,
                "steam_import_payload": steam_import_payload,
                "trophy_guide_import_payload": trophy_guide_import_payload,
                "sync_now": sync,
                "hltb_pending": len([item for item in all_games if item["hltb"] is None]),
                "total_minutes": sum(known),
                "played_count": sum(v > 0 for v in known),
                "unplayed_count": sum(v == 0 for v in known),
                "unknown_count": len(all_games) - len(known),
                "platinum_count": len(platinum_games),
                "recent_platinums": platinum_games[:6],
                "platinums_by_year": sorted(platinum_years.items(), reverse=True)[:3],
            },
        )

    @app.get("/profile/{steamid}/games/{appid}", response_class=HTMLResponse, include_in_schema=False)
    def game_panel(request: Request, steamid: str, appid: int):
        library = app.state.library.get_library(steamid)
        selected = next((game for game in library["games"] if game["appid"] == appid), None)
        if selected is None:
            raise SteamError("Esse jogo não está na biblioteca importada.", 404)
        if selected.get("source") == "external" and selected.get("playtime_forever") is None:
            try:
                playtime = app.state.library.update_playtime(steamid, appid)
                if playtime and playtime.get("playtime_forever") is not None:
                    selected.update(playtime)
                    selected["playtime_hours"] = round(playtime["playtime_forever"] / 60, 2)
            except SteamError:
                pass
        achievements = app.state.library.achievements(steamid, appid)
        app.state.cache.invalidate(f"progress:{steamid}")
        return render(
            request,
            "game_detail.html",
            {
                "selected": selected,
                "library": library,
                "achievements": achievements,
                "hltb": app.state.library.hltb(appid, selected["name"]),
                "trophy_guide": load_trophy_guide(app.state.library.database, appid),
            },
        )

    @app.get("/profile/{steamid}/games/{appid}/workspace", response_class=HTMLResponse, include_in_schema=False)
    def game_workspace(request: Request, steamid: str, appid: int):
        library = app.state.library.get_library(steamid)
        selected = next((game for game in library["games"] if game["appid"] == appid), None)
        if selected is None:
            raise SteamError("Esse jogo não está na biblioteca importada.", 404)
        achievements = app.state.library.achievements(steamid, appid)
        trophy_guide = load_trophy_guide(app.state.library.database, appid)
        return render(
            request,
            "game_workspace.html",
            {
                "selected": selected,
                "library": library,
                "workspace": load_game_workspace(app.state.library.database, steamid, appid),
                "achievements": achievements,
                "hltb": app.state.library.hltb(appid, selected["name"]),
                "trophy_guide": trophy_guide,
                "guide_pairing": pair_trophy_guide(trophy_guide, achievements),
            },
        )

    @app.post("/profile/{steamid}/games/{appid}/workspace/note")
    def workspace_note(steamid: str, appid: int, body: str = Form(...)):
        add_game_note(app.state.library.database, steamid, appid, body.strip())
        return RedirectResponse(f"/profile/{steamid}/games/{appid}/workspace", status_code=303)

    @app.post("/profile/{steamid}/games/{appid}/workspace/checklist")
    def workspace_checklist(steamid: str, appid: int, label: str = Form(...)):
        add_checklist_item(app.state.library.database, steamid, appid, label.strip())
        return RedirectResponse(f"/profile/{steamid}/games/{appid}/workspace", status_code=303)

    @app.patch("/api/profile/{steamid}/games/{appid}/workspace/checklist/{item_id}")
    def workspace_checklist_toggle(steamid: str, appid: int, item_id: int, payload: dict):
        toggle_checklist_item(app.state.library.database, steamid, item_id, bool(payload.get("checked")))
        return {"ok": True}

    @app.post("/profile/{steamid}/games/{appid}/workspace/link")
    def workspace_link(steamid: str, appid: int, label: str = Form(""), url: str = Form(...)):
        clean_url = url.strip()
        clean_label = label.strip() or clean_url
        add_game_link(app.state.library.database, steamid, appid, clean_label, clean_url)
        return RedirectResponse(f"/profile/{steamid}/games/{appid}/workspace", status_code=303)

    @app.post("/api/profile/{steamid}/games/{appid}/trophy-guide")
    def trophy_guide_update(steamid: str, appid: int, url: str = ""):
        library = app.state.library.get_library(steamid)
        if not any(game["appid"] == appid for game in library["games"]):
            raise SteamError("Esse jogo não está na biblioteca importada.", 404)
        if not url.strip():
            return JSONResponse({"detail": "Informe a URL do guia."}, status_code=422)
        result = app.state.library.trophy_guide(appid, url.strip(), refresh=True)
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        return result

    @app.post("/api/profile/{steamid}/games/{appid}/trophy-guide/import")
    def trophy_guide_import(steamid: str, appid: int, payload: dict):
        library = app.state.library.get_library(steamid)
        if not any(game["appid"] == appid for game in library["games"]):
            raise SteamError("Esse jogo não está na biblioteca importada.", 404)
        try:
            encoded = str(payload.get("html_b64", ""))
            padding = "=" * (-len(encoded) % 4)
            raw_html = base64.urlsafe_b64decode(encoded + padding)
            try:
                html = zlib.decompress(raw_html, wbits=31).decode("utf-8")
            except zlib.error:
                html = raw_html.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as error:
            raise SteamError("O HTML recebido do guia é inválido.", 422) from error
        result = app.state.library.trophy_guide_html(appid, payload.get("url", ""), html)
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}")
        return result

    @app.post("/profile/{steamid}/refresh", response_class=HTMLResponse)
    def refresh_profile(
        request: Request,
        steamid: str,
        mode: Literal["all", "steam", "hltb", "perfect"] = Form("all"),
    ):
        app.state.library.begin_refresh(steamid)
        perfect_notice = ""
        if mode in ("all", "steam"):
            library = app.state.library.get_library(steamid, refresh=True)
            if library["warning"]:
                app.state.library.finish_refresh(steamid)
                return render(request, "error.html", {"error": library["warning"], "steamid": steamid}, 502)
            try:
                imported = app.state.library.import_perfect_games(steamid)
                if imported["added"]:
                    perfect_notice = f"{imported['added']} platinas encontradas fora da biblioteca oficial."
            except Exception:
                # A página pública pode estar indisponível; isso não deve invalidar a atualização oficial.
                perfect_notice = ""
        elif mode == "perfect":
            try:
                imported = app.state.library.import_perfect_games(steamid)
                if imported["added"]:
                    perfect_notice = f"{imported['added']} platinas encontradas fora da biblioteca oficial."
                else:
                    perfect_notice = "Nenhuma platina nova foi encontrada na aba pública da Steam."
            except Exception as error:
                perfect_notice = f"Não foi possível consultar as platinas públicas: {error}"
        if mode == "all":
            app.state.library.hltb_progress(steamid, update=True, limit=5)
        elif mode == "hltb":
            app.state.library.hltb_progress(steamid, update=True, limit=20)
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        target = f"/profile/{steamid}"
        params = []
        if mode in ("all", "steam"):
            params.extend(["updated=steam", "sync=1"])
        elif mode == "perfect":
            params.append("updated=perfect")
        if perfect_notice:
            params.append(f"notice={quote(perfect_notice)}")
        if params:
            target += "?" + "&".join(params)
        app.state.library.finish_refresh(steamid)
        return RedirectResponse(target, status_code=303)

    @app.post("/api/profile/{steamid}/cancel-refresh")
    def cancel_refresh(steamid: str):
        app.state.library.cancel_refresh(steamid)
        return {"ok": True}

    @app.post("/profile/{steamid}/import-perfect", response_class=HTMLResponse)
    def import_perfect_games(request: Request, steamid: str):
        result = app.state.library.import_perfect_games(steamid)
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        return RedirectResponse(
            f"/profile/{steamid}?notice={quote(str(result['added']) + ' jogos de platina importados da aba pública da Steam')}",
            status_code=303,
        )

    @app.post("/profile/{steamid}/games/add", response_class=HTMLResponse)
    def add_external_game(request: Request, steamid: str, appid_or_url: str = Form(...)):
        match = re.search(r"(?:/app/)?(\d{1,12})(?:/|$|[?#])", appid_or_url.strip())
        if not match:
            raise SteamError("Informe um AppID ou uma URL de jogo Steam válida.", 422)
        result = app.state.library.add_external_game(steamid, int(match.group(1)))
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        message = f"{result['game']['name']} {'adicionado' if result['added'] else 'já está'} na sua lista"
        return RedirectResponse(f"/profile/{steamid}?notice={quote(message)}", status_code=303)

    @app.post("/api/profile/{steamid}/steam-import")
    def steam_browser_import(steamid: str, payload: dict):
        result = app.state.library.import_browser_games(steamid, payload.get("games"))
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        return {"ok": True, **result}

    @app.post("/profile/{steamid}/steam-import-paste", response_class=HTMLResponse)
    def steam_browser_import_paste(request: Request, steamid: str, payload: str = Form(...)):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise SteamError("O resultado colado não é um JSON válido.", 422) from error
        if not isinstance(data, dict):
            raise SteamError("O resultado colado precisa ser um objeto JSON com a chave games.", 422)
        result = app.state.library.import_browser_games(steamid, data.get("games"))
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        message = f"{result['added']} jogos importados pelo navegador."
        if result.get("updated"):
            message += f" {result['updated']} jogos externos foram atualizados para FAMÍLIA."
        return RedirectResponse(f"/profile/{steamid}?notice={quote(message)}", status_code=303)

    @app.get("/api/profile/{steamid}")
    def profile_api(steamid: str):
        key = f"profile:{steamid}"
        cached = app.state.cache.get(key)
        if cached is not None:
            return cached
        result = app.state.library.get_library(steamid)
        app.state.cache.set(key, result)
        return result

    @app.get("/api/profile/{steamid}/progress")
    def progress_status(steamid: str):
        key = f"progress:{steamid}"
        cached = app.state.cache.get(key)
        if cached is not None:
            return cached
        result = app.state.library.progress(steamid)
        app.state.cache.set(key, result)
        return result

    @app.post("/api/profile/{steamid}/progress")
    def update_progress(steamid: str):
        result = app.state.library.progress(steamid, update=True)
        app.state.cache.invalidate(f"progress:{steamid}", f"profile:{steamid}")
        return result

    @app.get("/api/profile/{steamid}/hltb")
    def hltb_status(steamid: str):
        key = f"hltb:{steamid}"
        cached = app.state.cache.get(key)
        if cached is not None:
            return cached
        result = app.state.library.hltb_progress(steamid)
        app.state.cache.set(key, result)
        return result

    @app.post("/api/profile/{steamid}/hltb")
    def hltb_update(steamid: str, limit: int = Query(default=20, ge=1, le=20)):
        result = app.state.library.hltb_progress(steamid, update=True, limit=limit)
        app.state.cache.invalidate(f"hltb:{steamid}", f"profile:{steamid}")
        return result

    return app


app = create_app()
