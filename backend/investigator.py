import asyncio
import os
from urllib.parse import urlparse

import httpx


SEARCH_URL = "https://ydc-index.io/v1/search"


async def search_one(client: httpx.AsyncClient, query: str) -> list[dict]:
    api_key = os.getenv("YOU_API_KEY")
    if not api_key:
        raise RuntimeError("YOU_API_KEY is not configured")

    response = await client.post(
        SEARCH_URL,
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "count": 5,
            "country": "IN",
            "language": "EN",
            "extraction": {"extraction_mode": "highlights"},
        },
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    if not isinstance(results, list):
        return []
    return results


def build_queries(company: str | None, role: str | None) -> dict[str, str]:
    company_name = company or "unknown company"
    role_name = role or "job role"
    return {
        "official": f"{company_name} official website careers",
        "careers": f"{company_name} careers official {role_name}",
        "fraud_notice": f"{company_name} recruitment fraud warning never charge candidates",
        "scam_reports": f"{company_name} scam fake job internship",
    }


async def investigate(company: str | None, role: str | None) -> dict[str, list[dict]]:
    queries = build_queries(company, role)
    async with httpx.AsyncClient(timeout=30) as client:
        groups = await asyncio.gather(
            *(search_one(client, query) for query in queries.values())
        )
    return dict(zip(queries.keys(), groups))
