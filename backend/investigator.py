import asyncio
import os
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import httpx


SEARCH_URL = "https://ydc-index.io/v1/search"
ProgressCallback = Callable[[dict], Awaitable[None]]


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
    if isinstance(results, dict):
        results = results.get("web", [])
    return results if isinstance(results, list) else []


def build_queries(
    company: str | None,
    role: str | None,
    website_url: str | None = None,
    company_domain: str | None = None,
) -> dict[str, str]:
    company_name = company or "unknown company"
    role_name = role or "job role"
    domain_url = company_domain if company_domain and "://" in company_domain else f"//{company_domain or ''}"
    domain_host = urlparse(domain_url).hostname if company_domain else None
    site = f"site:{domain_host}" if domain_host else ""
    url = website_url or ""
    return {
        "official": f"{company_name} official website {url} {site}".strip(),
        "careers": f"{company_name} careers {role_name} {site}".strip(),
        "fraud_notice": f"{company_name} official recruitment fraud notice candidate fee",
        "scam_reports": f"{company_name} fake job scam registration fee complaints",
        "registration_news": f"{company_name} company registration business news",
    }


async def investigate(
    company: str | None,
    role: str | None,
    website_url: str | None = None,
    company_domain: str | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, list[dict]]:
    queries = build_queries(company, role, website_url, company_domain)
    labels = {
        "official": "Finding the company's official site",
        "careers": "Checking the careers page and role",
        "fraud_notice": "Looking for the company's recruitment-fraud notice",
        "scam_reports": "Searching reports about fake offers",
        "registration_news": "Checking company registration and news",
    }

    async def run_search(key: str, query: str, client: httpx.AsyncClient) -> tuple[str, list[dict]]:
        if progress:
            await progress({
                "type": "step",
                "id": f"search_{key}",
                "label": labels[key],
                "status": "running",
                "query": query,
            })
        results = await search_one(client, query)
        if progress:
            await progress({
                "type": "step",
                "id": f"search_{key}",
                "label": labels[key],
                "status": "done",
                "query": query,
            })
        return key, results

    async with httpx.AsyncClient(timeout=30) as client:
        results = await asyncio.gather(
            *(run_search(key, query, client) for key, query in queries.items())
        )
    return dict(results)
