"""
Travel brief generator — weather forecast + carry-on packing list.
Uses Claude Haiku + web_search, called 7 days before each trip departure.
"""

import json
import re

import anthropic


async def generate_travel_brief(trip: dict, recs_content: str | None = None) -> dict:
    """
    Generate a pre-trip brief with weather, packing list, and restaurant highlights.
    Returns dict with keys: weather, restaurant_highlights, html_email.
    """
    client = anthropic.AsyncAnthropic()
    city       = trip["city"]
    country    = trip["country"]
    start_date = trip["start_date"]
    end_date   = trip["end_date"]

    prompt = f"""You are preparing a pre-trip family travel brief.

Trip: {city}, {country} · {start_date} to {end_date}

Search for the weather forecast for {city} around {start_date}, then create a carry-on-only packing list for an adult and young child traveling together.

Return ONLY valid JSON in this exact structure:
{{
  "weather_summary": "2-3 sentence forecast description",
  "temperature_range": "e.g. 18-26C / 64-79F",
  "weather_conditions": "e.g. Sunny with afternoon showers",
  "packing_list": {{
    "clothing": ["item1", "item2"],
    "toiletries": ["item1"],
    "electronics": ["item1"],
    "documents": ["item1"],
    "kids_items": ["item1"],
    "misc": ["item1"]
  }},
  "travel_tips": ["tip1", "tip2", "tip3"]
}}"""

    messages: list = [{"role": "user", "content": prompt}]
    result_text = ""

    while True:
        async with client.messages.stream(
            model="claude-haiku-4-5",
            max_tokens=1800,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                result_text += text
            final = await stream.get_final_message()

        if final.stop_reason != "pause_turn":
            break
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final.content},
        ]

    raw = result_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        brief = json.loads(raw)
    except json.JSONDecodeError:
        brief = {
            "weather_summary": f"Check local forecast for {city} around {start_date}.",
            "temperature_range": "See local weather app",
            "weather_conditions": "Variable",
            "packing_list": {
                "clothing": ["Comfortable walking shoes", "Layers for variable weather", "Light jacket", "1 outfit per day + 1 spare"],
                "toiletries": ["Toothbrush & paste", "Travel toiletries (100ml each)", "Sunscreen", "Hand sanitizer"],
                "electronics": ["Phone + charger", "Universal adapter", "Portable battery"],
                "documents": ["Passport/ID", "Travel insurance", "Hotel confirmation", "Boarding passes"],
                "kids_items": ["Snacks", "Small toys / entertainment", "Change of clothes in carry-on"],
                "misc": ["Reusable water bottle", "Day pack", "Neck pillow for flight"],
            },
            "travel_tips": [
                f"Research local transit options in {city}",
                "Keep copies of all important documents in email/cloud",
                "Download offline maps before leaving",
            ],
        }

    restaurant_highlights = _extract_highlights(recs_content)
    html_email = _build_html(trip, brief, restaurant_highlights)

    return {
        "weather": brief,
        "restaurant_highlights": restaurant_highlights,
        "html_email": html_email,
    }


def _extract_highlights(recs_content: str | None) -> str:
    if not recs_content:
        return ""
    lines = recs_content.split("\n")
    out, count = [], 0
    for line in lines:
        if line.startswith("### "):
            if count >= 4:
                break
            out.append(line)
            count += 1
        elif count and line.strip():
            out.append(line)
    return "\n".join(out[:50])


def _li(items: list) -> str:
    if not items:
        return ""
    return "<ul style='margin:4px 0 8px;padding-left:18px;'>" + "".join(
        f"<li style='font-size:13px;margin:2px 0;color:#444;'>{i}</li>" for i in items
    ) + "</ul>"


def _build_html(trip: dict, brief: dict, restaurant_highlights: str) -> str:
    city       = trip["city"]
    country    = trip["country"]
    start_date = trip["start_date"]
    end_date   = trip["end_date"]
    pk         = brief.get("packing_list", {})

    rest_html = ""
    if restaurant_highlights:
        lines = restaurant_highlights.split("\n")
        parts = []
        for line in lines:
            if line.startswith("### "):
                parts.append(f"<h4 style='color:#1565c0;margin:10px 0 3px;font-size:14px;'>{line[4:]}</h4>")
            elif line.startswith("- **") or line.startswith("- "):
                parts.append(f"<p style='margin:1px 0;font-size:12px;color:#444;'>{line[2:]}</p>")
            elif line.strip():
                parts.append(f"<p style='margin:1px 0;font-size:12px;color:#555;'>{line}</p>")
        rest_html = f"""
    <div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:16px;border-radius:8px;margin-bottom:18px;">
      <h2 style="margin:0 0 10px;font-size:17px;color:#333;">🍽 Restaurant Highlights</h2>
      {"".join(parts)}
    </div>"""

    tips_html = "".join(
        f"<li style='font-size:13px;margin:3px 0;color:#444;'>{t}</li>"
        for t in brief.get("travel_tips", [])
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;padding:20px;color:#333;background:#f5f5f5;">

<div style="background:linear-gradient(135deg,#1565c0,#6a1b9a);color:white;padding:30px;border-radius:14px;margin-bottom:20px;">
  <h1 style="margin:0 0 6px;font-size:26px;">✈️ {city} Trip Brief</h1>
  <p style="margin:0;opacity:.85;font-size:15px;">{start_date} → {end_date} &nbsp;·&nbsp; {country}</p>
  <p style="margin:8px 0 0;opacity:.7;font-size:13px;">Your personal travel agent has prepared this briefing — carry-on only!</p>
</div>

<div style="background:#e8f5e9;border-left:4px solid #43a047;padding:16px;border-radius:8px;margin-bottom:16px;">
  <h2 style="margin:0 0 8px;font-size:17px;color:#333;">🌤 Weather Forecast</h2>
  <p style="margin:0 0 5px;font-size:14px;"><strong>{brief.get("temperature_range","")}</strong> &nbsp;·&nbsp; {brief.get("weather_conditions","")}</p>
  <p style="margin:0;font-size:13px;color:#555;">{brief.get("weather_summary","")}</p>
</div>

<div style="background:#fff8e1;border-left:4px solid #fb8c00;padding:16px;border-radius:8px;margin-bottom:16px;">
  <h2 style="margin:0 0 12px;font-size:17px;color:#333;">🎒 Carry-On Packing List</h2>
  <table style="width:100%;border-collapse:collapse;"><tr>
    <td style="vertical-align:top;padding-right:14px;width:50%;">
      <strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.5px;">Clothing</strong>
      {_li(pk.get("clothing", []))}
      <strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.5px;">Toiletries</strong>
      {_li(pk.get("toiletries", []))}
    </td>
    <td style="vertical-align:top;width:50%;">
      <strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.5px;">Electronics</strong>
      {_li(pk.get("electronics", []))}
      <strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.5px;">Documents</strong>
      {_li(pk.get("documents", []))}
      <strong style="font-size:11px;text-transform:uppercase;color:#888;letter-spacing:.5px;">For the Kids</strong>
      {_li(pk.get("kids_items", []))}
    </td>
  </tr></table>
</div>

{rest_html}

<div style="background:#f3e5f5;border-left:4px solid #8e24aa;padding:16px;border-radius:8px;margin-bottom:16px;">
  <h2 style="margin:0 0 8px;font-size:17px;color:#333;">💡 Travel Tips</h2>
  <ul style="margin:0;padding-left:18px;">{tips_html}</ul>
</div>

<div style="text-align:center;color:#aaa;font-size:11px;margin-top:18px;padding-top:14px;border-top:1px solid #e0e0e0;">
  <p style="margin:0;">Have an amazing trip to {city}! 🌍</p>
  <p style="margin:4px 0 0;">Sent by your Travel Intelligence Dashboard</p>
</div>

</body></html>"""
