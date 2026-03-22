"""
Restaurant recommendation agent.

Uses Claude Opus 4.6 with the web_search server-side tool to find
current, highly-rated restaurants for a given city and travel window.
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

    Yields text chunks as Claude searches the web and composes recommendations.
    Handles pause_turn (server-side tool iteration limit) automatically.
    """
    client = anthropic.AsyncAnthropic()

    prompt = f"""I'm traveling to {city}, {country} from {start_date} to {end_date}.

Please search the web for the best restaurants I should visit during my trip.
Provide 6–8 strong recommendations covering a range of experiences.

For each restaurant include:
- **Name** and cuisine type
- **Neighborhood / area** (so I can plan by location)
- **Price range** ($ / $$ / $$$ / $$$$)
- **What to order** — 2-3 signature dishes
- **Why it's worth visiting** — what makes it special
- **Practical tips** — reservation needed? Best meal (lunch/dinner/both)?

Aim for a mix of:
- Iconic local cuisine you cannot miss
- A special-occasion fine dining option
- A beloved neighbourhood gem
- A trendy spot that locals are excited about right now

Use current sources so the information is fresh. Format your answer with clear headings."""

    messages: list = [{"role": "user", "content": prompt}]

    while True:
        async with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

            final = await stream.get_final_message()

        if final.stop_reason != "pause_turn":
            break

        # Server-side tool loop hit its iteration cap — re-send to continue.
        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final.content},
        ]
