from datetime import datetime, timezone
from urllib.parse import urlparse

from models import Evidence, ExtractedOffer


def source_type(url: str, company_domain: str | None) -> str:
    domain = urlparse(url).netloc.lower()
    if any(name in domain for name in ("reddit.", "quora.", "forum.")):
        return "forum"
    if any(name in domain for name in ("news.", "timesofindia.", "hindustantimes.")):
        return "news"
    host = domain.removeprefix("www.")
    if company_domain:
        domain_url = company_domain if "://" in company_domain else f"//{company_domain}"
        expected = (urlparse(domain_url).hostname or company_domain).lower().removeprefix("www.")
        if host == expected or host.endswith(f".{expected}"):
            return "official"
    return "unknown"


def process_evidence(groups: dict[str, list[dict]], offer: ExtractedOffer) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: dict[str, Evidence] = {}
    retrieved_at = datetime.now(timezone.utc).isoformat()
    company_domain = offer.company_domain
    if not company_domain and offer.website_url:
        company_domain = urlparse(offer.website_url).netloc

    for group_name, results in groups.items():
        for position, result in enumerate(results):
            url = result.get("url") or result.get("href")
            if not url:
                continue
            parsed_url = urlparse(url)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                continue
            query_type = group_name if group_name in {
                "official", "careers", "fraud_notice", "scam_reports", "registration_news"
            } else None
            if url in seen:
                if query_type and query_type not in seen[url].query_types:
                    seen[url].query_types.append(query_type)
                continue
            title = result.get("title") or result.get("name") or "Search result"
            contents = result.get("contents") or {}
            snippets = (
                result.get("snippet")
                or result.get("snippets")
                or contents.get("highlights")
                or []
            )
            if isinstance(snippets, list):
                snippet = " ".join(
                    item if isinstance(item, str) else str(
                        item.get("snippet") or item.get("text") or item.get("content") or ""
                    )
                    for item in snippets[:2]
                )
            else:
                snippet = str(snippets)
            if not snippet:
                snippet = str(result.get("description") or "")
            domain = parsed_url.netloc.removeprefix("www.")
            item = Evidence(
                id=f"e{len(evidence) + 1}",
                claim_id="",
                url=url,
                title=title,
                snippet=snippet,
                source_type=source_type(url, company_domain),
                retrieved_at=retrieved_at,
                domain=domain,
                query_types=[query_type] if query_type else [],
            )
            evidence.append(item)
            seen[url] = item
    return evidence
