"""
Travel Intelligence Dashboard — FastAPI backend
"""

import asyncio
import json
import os
import secrets
import uuid
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_DIR       = Path("data")
SCHEDULE_FILE  = DATA_DIR / "schedule.json"
PROJECTS_FILE  = DATA_DIR / "projects.json"
RECS_DIR       = DATA_DIR / "recs"
TOKEN_FILE     = DATA_DIR / "google_token.json"
CREDS_FILE     = Path("credentials.json")

# ── OAuth state store (in-memory, single-user local app) ──────────────────
_oauth_states: dict[str, datetime] = {}

# ── Data helpers — schedule ───────────────────────────────────────────────
def load_schedule() -> list:
    return json.loads(SCHEDULE_FILE.read_text()) if SCHEDULE_FILE.exists() else []

def save_schedule(s: list) -> None:
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(s, indent=2))

# ── Data helpers — projects ───────────────────────────────────────────────
def load_projects() -> list:
    return json.loads(PROJECTS_FILE.read_text()) if PROJECTS_FILE.exists() else []

def save_projects(p: list) -> None:
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_FILE.write_text(json.dumps(p, indent=2))

# ── Data helpers — recommendation cache ──────────────────────────────────
def load_rec(trip_id: str) -> dict | None:
    path = RECS_DIR / f"{trip_id}.json"
    return json.loads(path.read_text()) if path.exists() else None

def save_rec(trip_id: str, content: str) -> None:
    RECS_DIR.mkdir(parents=True, exist_ok=True)
    (RECS_DIR / f"{trip_id}.json").write_text(json.dumps({
        "trip_id": trip_id,
        "content": content,
        "refreshed_at": datetime.now().isoformat(),
    }, indent=2))

def rec_is_stale(rec: dict) -> bool:
    age = datetime.now() - datetime.fromisoformat(rec["refreshed_at"])
    return age > timedelta(days=7)

# ── Background weekly-refresh task ────────────────────────────────────────
async def weekly_refresh_checker():
    """Every hour, silently refresh any trip whose cached recs are > 7 days old."""
    await asyncio.sleep(60)          # short initial delay on startup
    while True:
        try:
            from agents.restaurant import get_restaurant_recommendations
            for trip in load_schedule():
                rec = load_rec(trip["id"])
                if rec is None or rec_is_stale(rec):
                    asyncio.create_task(_refresh_silent(trip))
        except Exception as e:
            print(f"[refresh-checker] {e}")
        await asyncio.sleep(3600)    # check hourly


async def _refresh_silent(trip: dict) -> None:
    from agents.restaurant import get_restaurant_recommendations
    chunks: list[str] = []
    try:
        async for chunk in get_restaurant_recommendations(
            city=trip["city"],
            country=trip["country"],
            start_date=trip["start_date"],
            end_date=trip["end_date"],
        ):
            chunks.append(chunk)
        save_rec(trip["id"], "".join(chunks))
        print(f"[refresh] Refreshed recs for {trip['city']}")
    except Exception as e:
        print(f"[refresh] Failed for {trip['city']}: {e}")


# ── Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(exist_ok=True)
    RECS_DIR.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(weekly_refresh_checker())
    yield
    task.cancel()


app = FastAPI(title="Travel Intelligence Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Models ────────────────────────────────────────────────────────────────
class TripCreate(BaseModel):
    city: str
    country: str
    start_date: str
    end_date: str
    notes: Optional[str] = ""


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    priority: str = "medium"          # high / medium / low
    status: str = "planning"          # planning / in_progress / completed
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
    notes: Optional[str] = ""


class ProjectUpdate(ProjectCreate):
    pass


# ── Root ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    return Path("static/index.html").read_text()


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "google_connected": TOKEN_FILE.exists(),
        "google_credentials_present": CREDS_FILE.exists(),
    }


# ── Schedule ──────────────────────────────────────────────────────────────
@app.get("/api/schedule")
async def get_schedule():
    return load_schedule()


@app.post("/api/schedule", status_code=201)
async def add_trip(trip: TripCreate):
    schedule = load_schedule()
    entry = {
        "id": str(uuid.uuid4()),
        "city": trip.city,
        "country": trip.country,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "notes": trip.notes or "",
        "created_at": datetime.now().isoformat(),
    }
    schedule.append(entry)
    save_schedule(schedule)
    return entry


@app.delete("/api/schedule/{trip_id}")
async def delete_trip(trip_id: str):
    schedule = load_schedule()
    updated = [t for t in schedule if t["id"] != trip_id]
    if len(updated) == len(schedule):
        raise HTTPException(404, "Trip not found")
    save_schedule(updated)
    # Also remove cached recs
    rec_path = RECS_DIR / f"{trip_id}.json"
    if rec_path.exists():
        rec_path.unlink()
    return {"status": "deleted"}


# ── Recommendation cache status ───────────────────────────────────────────
@app.get("/api/recommendations/{trip_id}/status")
async def rec_status(trip_id: str):
    rec = load_rec(trip_id)
    if not rec:
        return {"has_cache": False, "needs_refresh": True}
    stale = rec_is_stale(rec)
    age   = datetime.now() - datetime.fromisoformat(rec["refreshed_at"])
    return {
        "has_cache": True,
        "needs_refresh": stale,
        "refreshed_at": rec["refreshed_at"],
        "age_days": age.days,
    }


# ── Recommendation streaming ──────────────────────────────────────────────
@app.get("/api/recommendations/stream")
async def stream_recommendations(trip_id: str, force: bool = False):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(500, "ANTHROPIC_API_KEY is not set")

    schedule = load_schedule()
    trip = next((t for t in schedule if t["id"] == trip_id), None)
    if not trip:
        raise HTTPException(404, "Trip not found")

    from agents.restaurant import get_restaurant_recommendations

    # Serve from cache if fresh and not forced
    rec = load_rec(trip_id)
    if rec and not force and not rec_is_stale(rec):
        async def stream_cached():
            cached_text = rec["content"]
            chunk_size = 200
            for i in range(0, len(cached_text), chunk_size):
                yield f"data: {json.dumps({'text': cached_text[i:i+chunk_size], 'cached': True})}\n\n"
                await asyncio.sleep(0.005)
            yield f"data: {json.dumps({'done': True, 'cached': True, 'refreshed_at': rec['refreshed_at']})}\n\n"

        return StreamingResponse(
            stream_cached(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Live stream and simultaneously cache
    accumulated: list[str] = []

    async def event_stream():
        try:
            async for chunk in get_restaurant_recommendations(
                city=trip["city"],
                country=trip["country"],
                start_date=trip["start_date"],
                end_date=trip["end_date"],
            ):
                accumulated.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if accumulated:
                save_rec(trip_id, "".join(accumulated))
            now = datetime.now().isoformat()
            yield f"data: {json.dumps({'done': True, 'refreshed_at': now})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ── Projects ──────────────────────────────────────────────────────────────
@app.get("/api/projects")
async def get_projects():
    return load_projects()


@app.post("/api/projects", status_code=201)
async def add_project(proj: ProjectCreate):
    projects = load_projects()
    entry = {
        "id": str(uuid.uuid4()),
        "name": proj.name,
        "description": proj.description or "",
        "priority": proj.priority,
        "status": proj.status,
        "estimated_cost": proj.estimated_cost,
        "actual_cost": proj.actual_cost,
        "notes": proj.notes or "",
        "created_at": datetime.now().isoformat(),
    }
    projects.append(entry)
    save_projects(projects)
    return entry


@app.put("/api/projects/{proj_id}")
async def update_project(proj_id: str, proj: ProjectUpdate):
    projects = load_projects()
    idx = next((i for i, p in enumerate(projects) if p["id"] == proj_id), None)
    if idx is None:
        raise HTTPException(404, "Project not found")
    projects[idx].update({
        "name": proj.name,
        "description": proj.description or "",
        "priority": proj.priority,
        "status": proj.status,
        "estimated_cost": proj.estimated_cost,
        "actual_cost": proj.actual_cost,
        "notes": proj.notes or "",
    })
    save_projects(projects)
    return projects[idx]


@app.delete("/api/projects/{proj_id}")
async def delete_project(proj_id: str):
    projects = load_projects()
    updated = [p for p in projects if p["id"] != proj_id]
    if len(updated) == len(projects):
        raise HTTPException(404, "Project not found")
    save_projects(updated)
    return {"status": "deleted"}


# ── Google OAuth ──────────────────────────────────────────────────────────
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _build_flow(state: str | None = None):
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        str(CREDS_FILE),
        scopes=GOOGLE_SCOPES,
        state=state,
    )
    flow.redirect_uri = "http://localhost:8000/auth/google/callback"
    return flow


@app.get("/auth/google")
def google_auth():
    if not CREDS_FILE.exists():
        return RedirectResponse("/?error=no_credentials")
    state = secrets.token_urlsafe(16)
    flow  = _build_flow()
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    _oauth_states[state] = datetime.now()
    return RedirectResponse(url)


@app.get("/auth/google/callback")
def google_callback(code: str, state: str):
    if state not in _oauth_states:
        raise HTTPException(400, "Invalid OAuth state")
    del _oauth_states[state]
    flow = _build_flow(state=state)
    flow.fetch_token(code=code)
    DATA_DIR.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(flow.credentials.to_json())
    return RedirectResponse("/?connected=google")


@app.delete("/auth/google")
async def google_disconnect():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    return {"status": "disconnected"}


# ── Gmail import ──────────────────────────────────────────────────────────
@app.post("/api/gmail/import")
async def gmail_import():
    if not TOKEN_FILE.exists():
        raise HTTPException(401, "Google not connected")
    from agents.gmail_calendar import fetch_travel_trips_from_gmail
    loop = asyncio.get_event_loop()
    trips = await loop.run_in_executor(None, fetch_travel_trips_from_gmail)
    return {"trips": trips}


# ── Calendar sync ─────────────────────────────────────────────────────────
@app.get("/api/calendar/events")
async def calendar_events():
    if not TOKEN_FILE.exists():
        raise HTTPException(401, "Google not connected")
    from agents.gmail_calendar import fetch_travel_events_from_calendar
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(None, fetch_travel_events_from_calendar)
    return {"events": events}


# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import threading
    import uvicorn

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    print("\n🌍  Travel Intelligence Dashboard starting…")
    print("   Open: http://localhost:8000\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
