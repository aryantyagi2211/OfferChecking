from datetime import datetime, timezone
from urllib.parse import urlparse

from models import Evidence


def source_type(url: str, title: str = "") -> str:
    domain = urlparse(url).netloc.lower()
    if "reddit" in domain or "quora" in domain or "forum" in domain:
        return "forum"
    if "news" in domain or "timesofindia" in domain or "hindustan" in domain:
        return "news"
    if domain:
        return "official" if any(token in domain for token in ("careers", "official")) else "unknown"
    return "unknown"


def process_evidence(groups: dict[str, list[dict]]) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[str] = set()
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for group_name, results in groups.items():
        for position, result in enumerate(results):
            url = result.get("url") or result.get("href")
            if not url or url in seen:
                continue
            seen.add(url)
            title = result.get("title") or result.get("name") or "Search result"
            snippets = result.get("snippets") or result.get("contents", {}).get("highlights") or []
            if isinstance(snippets, list):
                snippet = " ".join(str(item) for item in snippets[:2])
            else:
                snippet = str(snippets)
            if not snippet:
                snippet = str(result.get("description") or "")
            domain = urlparse(url).netloc.removeprefix("www.")
            evidence.append(
                Evidence(
                    id=f"e{len(evidence) + 1}",
                    claim_id="",
                    url=url,
                    title=title,
                    snippet=snippet,
                    source_type=source_type(url, title),
                    retrieved_at=retrieved_at,
                    domain=domain,
                )
            )
    return evidence
