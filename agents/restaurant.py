"""
Restaurant recommendation agent.

Uses Claude Opus 4.6 with the web_search_20260209 server-side tool.
Targets Yelp, Google Reviews, and OpenTable for top-rated results.
Prioritises healthy, genuinely nutritious options and strong vegetarian
menus — suitable for an adult + child dining together.
"""

from typing import AsyncGenerator

import anthropic


async def get_restaurant_recommendations(
    city: str,
    country: str,
    start_date: str,
    end_date: str,
) -> AsyncGenerator[str, None]:
    """
    Stream restaurant recommendations for a travel destination.
    Handles pause_turn (server-side tool iteration cap) automatically.
    """
    client = anthropic.AsyncAnthropic()

    prompt = f"""I'm travelling to {city}, {country} from {start_date} to {end_date} with my young son. We have specific priorities for restaurants:

**Our requirements:**
- Strong, creative **vegetarian options** — not just a token salad. We need restaurants where vegetarians are genuinely well-served.
- **Healthy, real-food cooking** — quality ingredients, fresh produce, nothing overly processed or "chain-restaurant healthy." Farm-to-table, market-driven menus, or cuisines naturally rich in vegetables are ideal.
- **Not cheesy or touristy** — skip the tourist-trap spots. We want places locals actually love.
- **Family-appropriate** — welcoming to a child, not necessarily a kids' menu, just a relaxed atmosphere.

**Your research method:**
1. Search **Yelp** for highly-rated restaurants in {city} that match these criteria
2. Cross-reference with **Google Reviews** to confirm quality and current status
3. Check **OpenTable** for top-rated reservable options — note which ones are bookable there
4. Look for any recent "best of {city}" or food critics' picks from the past 12 months

**Provide 7–8 restaurants** covering:
- At least 2–3 spots that are exceptional for vegetarians
- At least 1 upscale / special-occasion restaurant with great veggie options
- 2–3 beloved neighbourhood spots (excellent value, local feel)
- 1–2 trendy / buzzy spots worth experiencing

**For each restaurant include:**
### [Restaurant Name] — [Cuisine Type]
- 📍 **Neighbourhood:** [area]
- 💰 **Price:** [$ / $$ / $$$ / $$$$]
- ⭐ **Reviews:** [Yelp rating + Google rating if available]
- 🥦 **Vegetarian highlights:** [specific dishes]
- 🍽️ **Don't miss:** [top 2–3 dishes overall]
- 📅 **Reservations:** [OpenTable link or note if walk-in only; reservation recommended?]
- ✨ **Why go:** [1–2 sentences on what makes it special]

End with a short **"My picks for a first night"** section suggesting the single best choice for the first dinner in {city}."""

    messages: list = [{"role": "user", "content": prompt}]

    while True:
        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=5000,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()

        if final.stop_reason != "pause_turn":
            break

        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final.content},
        ]
