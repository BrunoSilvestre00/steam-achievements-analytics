"""Frontend renderizado em Python e API JSON para consultas futuras."""

import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Form, Query, Request
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
            "name", "hours", "recent", "percent_desc", "percent_asc", "hltb_desc", "hltb_asc"
        ] = "percent_desc",
        played: Literal["all", "played", "unplayed", "platinum", "not_platinum", "near_platinum"] = "all",
        game: int | None = Query(default=None, gt=0),
        updated: str = Query(default="", max_length=20),
    ):
        library = app.state.library.get_library(steamid)
        all_games = library["games"]
        if sort in ("hltb_desc", "hltb_asc"):
            # Preenche alguns valores ausentes antes de ordenar, para que a opção
            # continue útil mesmo quando a biblioteca ainda não foi consultada.
            app.state.library.hltb_progress(steamid, update=True)
        progress = {item["appid"]: item for item in load_progress(app.state.library.database, steamid)}
        hltb_summary = load_hltb_summary(app.state.library.database, [item["appid"] for item in all_games])
        for rank, item in enumerate(sorted(all_games, key=lambda g: (g["name"].casefold(), g["appid"]))):
            item["progress"] = progress[item["appid"]]
            item["hltb"] = hltb_summary.get(item["appid"])
            item["name_order"] = rank
        games = [g for g in all_games if q.casefold() in g["name"].casefold()]
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
        selected = next((g for g in games if g["appid"] == game), games[0] if games else None)
        achievements = app.state.library.achievements(steamid, selected["appid"]) if selected else None
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
        return render(
            request,
            "game_detail.html",
            {
                "selected": selected,
                "library": library,
                "achievements": app.state.library.achievements(steamid, appid),
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
        return render(
            request,
            "game_workspace.html",
            {
                "selected": selected,
                "library": library,
                "workspace": load_game_workspace(app.state.library.database, steamid, appid),
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
    def workspace_link(steamid: str, appid: int, label: str = Form(...), url: str = Form(...)):
        add_game_link(app.state.library.database, steamid, appid, label.strip(), url.strip())
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

    @app.post("/profile/{steamid}/refresh", response_class=HTMLResponse)
    def refresh_profile(
        request: Request,
        steamid: str,
        mode: Literal["all", "steam", "hltb"] = Form("all"),
    ):
        if mode in ("all", "steam"):
            library = app.state.library.get_library(steamid, refresh=True)
            if library["warning"]:
                return render(request, "error.html", {"error": library["warning"], "steamid": steamid}, 502)
        if mode == "all":
            app.state.library.hltb_progress(steamid, update=True, limit=5)
        elif mode == "hltb":
            app.state.library.hltb_progress(steamid, update=True, limit=20)
        app.state.cache.invalidate(f"profile:{steamid}", f"progress:{steamid}", f"hltb:{steamid}")
        return RedirectResponse(f"/profile/{steamid}", status_code=303)

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
