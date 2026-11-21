import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from extractor import extract_offer


load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.WARNING, format="%(message)s")


async def main() -> None:
    you_key = os.getenv("YOU_API_KEY")
    if not you_key:
        raise RuntimeError("YOU_API_KEY is not configured")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://ydc-index.io/v1/search",
            headers={"X-API-Key": you_key, "Content-Type": "application/json"},
            json={
                "query": "Northgate Technologies job offer registration fee scam",
                "count": 5,
                "country": "IN",
                "language": "EN",
            },
        )
        response.raise_for_status()
    result_data = response.json().get("results", {})
    web_results = result_data.get("web", []) if isinstance(result_data, dict) else []
    print("you_search_results.web:")
    for item in web_results:
        print({
            "url": item.get("url"),
            "title": item.get("title"),
            "snippets": item.get("snippets", []),
        })

    print("extract_model:", os.getenv("EXTRACT_MODEL"))
    print("analyze_model:", os.getenv("ANALYZE_MODEL"))
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            probe = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('EXTRACT_MODEL')}:generateContent",
                headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY"), "Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": "Reply with exactly OK"}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 8},
                },
            )
            print("extract_model_probe:", probe.status_code)
    except httpx.TimeoutException:
        print("extract_model_probe: timeout")

    try:
        offer = await extract_offer(
            "Northgate Technologies internship. Pay Rs 1,999 registration fee today. "
            "Contact HR Rohit at northgate.hr.careers@gmail.com."
        )
        print("gemini_extraction_ok:", bool(offer.company or offer.role or offer.fee_asked))
        print("extracted_claims:", offer.model_dump(exclude_none=True))
    except (httpx.HTTPStatusError, httpx.TimeoutException, RuntimeError) as error:
        status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else type(error).__name__
        print("gemini_extraction_failed:", status, str(error)[:200])


asyncio.run(main())
