from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.core.database import init_db
from app.api import auth, player, staff, capture, revive, mini_game, ranking


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="躲猫猫大挑战", version="1.0.0", lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include API routers
app.include_router(auth.router)
app.include_router(player.router)
app.include_router(staff.router)
app.include_router(capture.router)
app.include_router(revive.router)
app.include_router(mini_game.router)
app.include_router(ranking.router)


# ============ Page Routes ============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/player/login", response_class=HTMLResponse)
async def player_login_page(request: Request):
    return templates.TemplateResponse("player/login.html", {"request": request})


@app.get("/player", response_class=HTMLResponse)
async def player_index_page(request: Request):
    return templates.TemplateResponse("player/index.html", {"request": request})


@app.get("/player/team", response_class=HTMLResponse)
async def player_team_page(request: Request):
    return templates.TemplateResponse("player/team.html", {"request": request})


@app.get("/player/profile", response_class=HTMLResponse)
async def player_profile_page(request: Request):
    return templates.TemplateResponse("player/profile.html", {"request": request})


@app.get("/player/ranking", response_class=HTMLResponse)
async def player_ranking_page(request: Request):
    return templates.TemplateResponse("player/ranking.html", {"request": request})


@app.get("/player/capture", response_class=HTMLResponse)
async def player_capture_page(request: Request):
    return templates.TemplateResponse("player/capture.html", {"request": request})


@app.get("/player/history", response_class=HTMLResponse)
async def player_history_page(request: Request):
    return templates.TemplateResponse("player/history.html", {"request": request})


@app.get("/staff/login", response_class=HTMLResponse)
async def staff_login_page(request: Request):
    return templates.TemplateResponse("staff/login.html", {"request": request})


@app.get("/staff", response_class=HTMLResponse)
async def staff_index_page(request: Request):
    return templates.TemplateResponse("staff/index.html", {"request": request})


@app.get("/staff/players", response_class=HTMLResponse)
async def staff_players_page(request: Request):
    return templates.TemplateResponse("staff/players.html", {"request": request})


@app.get("/staff/roles", response_class=HTMLResponse)
async def staff_roles_page(request: Request):
    return templates.TemplateResponse("staff/roles.html", {"request": request})


@app.get("/staff/teams", response_class=HTMLResponse)
async def staff_teams_page(request: Request):
    return templates.TemplateResponse("staff/teams.html", {"request": request})


@app.get("/staff/scan", response_class=HTMLResponse)
async def staff_scan_page(request: Request):
    return templates.TemplateResponse("staff/scan.html", {"request": request})


@app.get("/staff/revive", response_class=HTMLResponse)
async def staff_revive_page(request: Request):
    return templates.TemplateResponse("staff/revive.html", {"request": request})


@app.get("/staff/mini-games", response_class=HTMLResponse)
async def staff_mini_games_page(request: Request):
    return templates.TemplateResponse("staff/mini_games.html", {"request": request})


@app.get("/staff/ranking", response_class=HTMLResponse)
async def staff_ranking_page(request: Request):
    return templates.TemplateResponse("staff/ranking.html", {"request": request})


@app.get("/staff/settings", response_class=HTMLResponse)
async def staff_settings_page(request: Request):
    return templates.TemplateResponse("staff/settings.html", {"request": request})


@app.get("/staff/history", response_class=HTMLResponse)
async def staff_history_page(request: Request):
    return templates.TemplateResponse("staff/history.html", {"request": request})


@app.get("/staff/teammates", response_class=HTMLResponse)
async def staff_teammates_page(request: Request):
    return templates.TemplateResponse("staff/teammates.html", {"request": request})


@app.get("/staff/config", response_class=HTMLResponse)
async def staff_config_page(request: Request):
    return templates.TemplateResponse("staff/config.html", {"request": request})
