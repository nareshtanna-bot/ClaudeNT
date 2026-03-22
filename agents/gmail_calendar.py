"""
Google Gmail + Calendar integration.

Reads travel confirmation emails from Gmail and upcoming travel events
from Google Calendar, then uses Claude to extract structured trip data.

All functions are synchronous (called via run_in_executor from async FastAPI
handlers so they don't block the event loop).
"""

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

TOKEN_FILE = Path("data/google_token.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


# ── Google credentials ────────────────────────────────────────────────────

def _load_creds():
    """Load stored OAuth credentials, refreshing if expired."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not TOKEN_FILE.exists():
        raise RuntimeError("Google not connected — token file missing")

    creds = Credentials.from_authorized_user_info(
        json.loads(TOKEN_FILE.read_text()), SCOPES
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return creds


# ── Email helpers ─────────────────────────────────────────────────────────

def _decode_b64url(data: str) -> str:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_text_from_payload(payload: dict) -> str:
    """Recursively walk MIME parts and return plain-text content."""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/plain" and body_data:
        return _decode_b64url(body_data)

    text = ""
    for part in payload.get("parts", []):
        text += _extract_text_from_payload(part)
    return text


# ── Claude email parser ───────────────────────────────────────────────────

def _parse_trip_from_email(subject: str, body: str) -> dict | None:
    """
    Use Claude to extract trip details from an email.
    Returns a dict with city/country/start_date/end_date/notes or None.
    """
    client = anthropic.Anthropic()

    prompt = f"""You are extracting travel booking details from an email.

Email subject: {subject}

Email body (first 2000 chars):
{body[:2000]}

If this email contains a confirmed travel booking (flight, hotel, car rental, etc.),
extract the trip details and return JSON in this exact format:
{{
  "is_travel": true,
  "city": "destination city name",
  "country": "destination country name",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "notes": "brief note e.g. Flight BA123 / Hotel Marriott"
}}

If the email does NOT contain a travel booking, return:
{{"is_travel": false}}

Return ONLY the JSON object, no other text."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = next((b.text for b in response.content if b.type == "text"), "")
    raw = raw.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not data.get("is_travel"):
        return None

    required = ("city", "country", "start_date", "end_date")
    if not all(data.get(k) for k in required):
        return None

    return {
        "city": data["city"],
        "country": data["country"],
        "start_date": data["start_date"],
        "end_date": data["end_date"],
        "notes": data.get("notes", "Imported from Gmail"),
    }


# ── Gmail integration ─────────────────────────────────────────────────────

def fetch_travel_trips_from_gmail() -> list[dict]:
    """
    Search Gmail for travel confirmation emails from the last 180 days.
    Returns a list of extracted trip dicts (not yet added to schedule).
    """
    from googleapiclient.discovery import build

    creds   = _load_creds()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    query = (
        "subject:(confirmation OR booking OR reservation OR itinerary OR e-ticket) "
        "newer_than:180d"
    )
    result   = service.users().messages().list(userId="me", q=query, maxResults=25).execute()
    messages = result.get("messages", [])

    trips = []
    seen_keys: set[str] = set()  # deduplicate by city+start

    for msg_ref in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()
        except Exception:
            continue

        subject = next(
            (h["value"] for h in msg.get("payload", {}).get("headers", [])
             if h["name"].lower() == "subject"),
            "",
        )
        body  = _extract_text_from_payload(msg.get("payload", {}))
        if not body.strip():
            continue

        trip = _parse_trip_from_email(subject, body)
        if not trip:
            continue

        key = f"{trip['city'].lower()}|{trip['start_date']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        trips.append(trip)

    return trips


# ── Google Calendar integration ───────────────────────────────────────────

def fetch_travel_events_from_calendar() -> list[dict]:
    """
    Pull upcoming Google Calendar events that look like travel (multi-day
    all-day events, or events with a city-like location).
    Returns a list of suggested trip dicts.
    """
    from googleapiclient.discovery import build

    creds   = _load_creds()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now     = datetime.now(timezone.utc).isoformat()
    future  = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

    events_result = service.events().list(
        calendarId="primary",
        timeMin=now,
        timeMax=future,
        maxResults=50,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    raw_events = events_result.get("items", [])
    suggestions = []

    travel_keywords = re.compile(
        r"\b(trip|travel|vacation|holiday|conference|summit|visit|flight|hotel|airbnb)\b",
        re.IGNORECASE,
    )

    for ev in raw_events:
        start = ev.get("start", {})
        end   = ev.get("end", {})

        # All-day events have "date", timed events have "dateTime"
        start_date = start.get("date") or (start.get("dateTime", "")[:10])
        end_date   = end.get("date")   or (end.get("dateTime", "")[:10])

        if not start_date or not end_date:
            continue

        # Must span at least 2 days to be a "trip"
        try:
            span = (
                datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.strptime(start_date, "%Y-%m-%d")
            ).days
        except ValueError:
            continue

        title    = ev.get("summary", "")
        location = ev.get("location", "")
        desc     = ev.get("description", "")

        is_multi_day_allday = "date" in start and span >= 2
        has_travel_keyword  = bool(travel_keywords.search(title + " " + desc))
        has_location        = bool(location.strip())

        if not (is_multi_day_allday or has_travel_keyword) or not has_location:
            continue

        # Use Claude to extract city/country from the location string
        extracted = _extract_city_from_location(location)
        if not extracted:
            continue

        suggestions.append({
            "city": extracted["city"],
            "country": extracted["country"],
            "start_date": start_date,
            "end_date": end_date,
            "notes": f"From Calendar: {title}",
            "calendar_event_id": ev.get("id"),
        })

    return suggestions


def _extract_city_from_location(location: str) -> dict | None:
    """Use Claude to parse a location string into city + country."""
    if not location.strip():
        return None

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=128,
        messages=[{
            "role": "user",
            "content": (
                f'Parse this location string into city and country. '
                f'Location: "{location}"\n'
                f'Return JSON only: {{"city": "...", "country": "..."}} '
                f'or {{"city": null}} if it\'s not a real city.'
            ),
        }],
    )
    raw = next((b.text for b in response.content if b.type == "text"), "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if data.get("city"):
            return {"city": data["city"], "country": data.get("country", "")}
    except (json.JSONDecodeError, AttributeError):
        pass
    return None
