import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

SCHEDULE_FILE = Path("data/schedule.json")


def load_schedule() -> list:
    if SCHEDULE_FILE.exists():
        return json.loads(SCHEDULE_FILE.read_text())
    return []


def save_schedule(schedule: list) -> None:
    SCHEDULE_FILE.parent.mkdir(exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(schedule, indent=2))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure data dir exists on startup
    Path("data").mkdir(exist_ok=True)
    yield


app = FastAPI(title="Travel Intelligence Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class TripCreate(BaseModel):
    city: str
    country: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    notes: Optional[str] = ""


@app.get("/", response_class=HTMLResponse)
async def root():
    return Path("static/index.html").read_text()


@app.get("/api/health")
async def health():
    api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
    return {"status": "ok", "api_key_configured": api_key_set}


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
    }
    schedule.append(entry)
    save_schedule(schedule)
    return entry


@app.delete("/api/schedule/{trip_id}")
async def delete_trip(trip_id: str):
    schedule = load_schedule()
    updated = [t for t in schedule if t["id"] != trip_id]
    if len(updated) == len(schedule):
        raise HTTPException(status_code=404, detail="Trip not found")
    save_schedule(updated)
    return {"status": "deleted"}


@app.get("/api/recommendations/stream")
async def stream_recommendations(trip_id: str):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not configured")

    schedule = load_schedule()
    trip = next((t for t in schedule if t["id"] == trip_id), None)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    from agents.restaurant import get_restaurant_recommendations

    async def event_stream():
        try:
            async for chunk in get_restaurant_recommendations(
                city=trip["city"],
                country=trip["country"],
                start_date=trip["start_date"],
                end_date=trip["end_date"],
            ):
                payload = json.dumps({"text": chunk})
                yield f"data: {payload}\n\n"
        except Exception as e:
            error_payload = json.dumps({"error": str(e)})
            yield f"data: {error_payload}\n\n"
        finally:
            yield "data: {\"done\": true}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
