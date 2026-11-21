import re
from urllib.parse import urlparse

if __package__:
    from .models import Evidence, ExtractedOffer
else:
    from models import Evidence, ExtractedOffer


FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}
NO_FEE_PHRASES = (
    "never asks candidates to pay",
    "never asks candidates for money",
    "never charges candidates",
    "does not charge candidates",
    "does not ask candidates for money",
    "no recruitment fees",
    "no fees are charged",
)


def _text(evidence: Evidence) -> str:
    return f"{evidence.title} {evidence.snippet}".lower()


def _query_sources(evidence: list[Evidence], *query_types: str) -> list[Evidence]:
    return [item for item in evidence if any(query_type in item.query_types for query_type in query_types)]


def _highlight(value: str | None, offer_text: str) -> str | None:
    if not value:
        return None
    match = re.search(re.escape(value), offer_text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _finding(
    claim_id: str,
    text: str,
    status: str,
    reason: str,
    evidence: list[Evidence] | None = None,
    highlight: str | None = None,
) -> dict:
    evidence = evidence or []
    return {
        "claim_id": claim_id,
        "text": text,
        "status": status,
        "reason": reason,
        "evidence_ids": [item.id for item in evidence],
        "highlight": highlight,
    }


def build_findings(
    offer: ExtractedOffer,
    evidence: list[Evidence],
    offer_text: str = "",
) -> tuple[list[dict], list[str], str]:
    findings: list[dict] = []
    flags: list[str] = []
    official = [item for item in evidence if item.source_type == "official"]
    company_domain_url = offer.company_domain or ""
    company_domain_url = company_domain_url if "://" in company_domain_url else f"//{company_domain_url}"
    company_domain = (urlparse(company_domain_url).hostname or "").lower().removeprefix("www.")

    company_tokens = [
        token.lower()
        for token in (offer.company or "").split()
        if len(token) > 3
    ]
    company_matches = [
        item for item in official
        if offer.company and (
            offer.company.lower() in _text(item)
            or any(token in _text(item) for token in company_tokens)
            or (
                company_domain
                and (
                    item.domain == company_domain
                    or item.domain.endswith(f".{company_domain}")
                )
            )
        )
    ]
    company_context = company_matches or _query_sources(
        evidence, "official", "registration_news"
    )[:2]
    findings.append(_finding(
        "company",
        f"Company: {offer.company}" if offer.company else "Company not named",
        "SUPPORTED" if company_matches else "UNVERIFIED",
        "An official result names this company." if company_matches
        else "Related company searches are linked, but did not confirm an official presence."
        if company_context
        else "We could not confirm the company from official sources.",
        company_context[:2],
        _highlight(offer.company, offer_text),
    ))

    findings.append(_finding(
        "recruiter",
        f"Recruiter: {offer.recruiter}" if offer.recruiter else "Recruiter not named",
        "UNVERIFIED",
        "Official and careers search results are linked for checking, but cannot confirm this person."
        if _query_sources(evidence, "official", "careers")
        else "Search results cannot confirm this person's identity.",
        _query_sources(evidence, "official", "careers")[:1],
        highlight=_highlight(offer.recruiter, offer_text),
    ))

    domain_sources: list[Evidence] = []
    email_domain = (offer.email_domain or "").lower()
    if email_domain and company_domain:
        if email_domain == company_domain or email_domain.endswith(f".{company_domain}"):
            domain_sources = [item for item in official if item.domain == company_domain or item.domain.endswith(f".{company_domain}")]
            domain_status = "SUPPORTED" if domain_sources else "UNVERIFIED"
            domain_reason = "The offer's email domain matches the supplied company domain." if domain_sources else "The matching domain could not be confirmed by an official result."
        else:
            domain_sources = [
                item for item in official
                if f"@{company_domain}" in _text(item)
            ]
            domain_status = "CONTRADICTED" if domain_sources else "UNVERIFIED"
            domain_reason = (
                "An official result lists a different recruiter email domain."
                if domain_sources else "We could not confirm this sender's company domain."
            )
    else:
        domain_status = "UNVERIFIED"
        domain_reason = "We could not confirm this sender's company domain."
        if email_domain in FREE_EMAIL_DOMAINS and offer.company:
            flags.append("free_email_recruiter")

    findings.append(_finding(
        "email_or_domain",
        f"Sender domain: {email_domain or company_domain}" if email_domain or company_domain else "Sender domain not provided",
        domain_status,
        domain_reason if domain_sources else (
            "Official company pages are linked, but do not confirm this sender's address."
            if company_domain and official else domain_reason
        ),
        (domain_sources or official[:1])[:2],
        _highlight(email_domain, offer_text) or _highlight(company_domain, offer_text),
    ))

    role_matches = [
        item for item in official
        if offer.role and offer.role.lower() in _text(item)
    ]
    role_context = role_matches or _query_sources(evidence, "careers")[:2]
    findings.append(_finding(
        "role",
        f"Role: {offer.role}" if offer.role else "Role not named",
        "SUPPORTED" if role_matches else "UNVERIFIED",
        "An official result lists this role." if role_matches
        else "Careers search results are linked, but did not confirm this role."
        if role_context
        else "We could not confirm this role on official results.",
        role_context[:2],
        _highlight(offer.role, offer_text),
    ))

    pay_matches = [
        item for item in official
        if offer.pay and offer.pay.lower() in _text(item)
    ]
    pay_context = pay_matches or _query_sources(evidence, "careers")[:2]
    findings.append(_finding(
        "pay",
        f"Pay: {offer.pay}" if offer.pay else "Pay not mentioned",
        "SUPPORTED" if pay_matches else "UNVERIFIED",
        "An official result includes these pay details." if pay_matches
        else "Related careers results are linked, but do not confirm this amount."
        if pay_context
        else "We could not confirm these pay details.",
        pay_context[:2],
        _highlight(offer.pay, offer_text),
    ))

    fee_evidence = [
        item for item in official
        if any(phrase in _text(item) for phrase in NO_FEE_PHRASES)
    ]
    fee_context = fee_evidence or _query_sources(evidence, "fraud_notice")[:2]
    if offer.fee_asked is True:
        flags.append("asks_fee")
        fee_status = "CONTRADICTED" if fee_evidence else "SUPPORTED"
        fee_reason = (
            "The company's own result says it does not charge candidates."
            if fee_evidence else "The pasted offer asks the candidate to pay a fee."
        )
    elif offer.fee_asked is False:
        fee_status = "SUPPORTED"
        fee_reason = "No candidate fee was found in the offer."
    else:
        fee_status = "UNVERIFIED"
        fee_reason = "We could not determine whether the offer asks for a fee."
    findings.append(_finding(
        "fee_asked",
        f"Fee requested: {offer.fee_amount or 'yes'}" if offer.fee_asked is True
        else "No fee request found" if offer.fee_asked is False
        else "Fee request not confirmed",
        fee_status,
        fee_reason,
        fee_context[:2],
        _highlight(offer.fee_amount, offer_text),
    ))

    payment_channel = offer.payment_channel
    payment_context = []
    if payment_channel in {"UPI", "crypto", "gift_card", "cash"}:
        flags.append("personal_payment_channel")
        payment_terms = {
            "gift_card": ("gift card", "gift-card"),
            "crypto": ("crypto", "cryptocurrency"),
        }.get(payment_channel, (payment_channel.lower(),))
        payment_context = [
            item for item in _query_sources(evidence, "scam_reports")
            if any(term in _text(item) for term in payment_terms)
        ][:2]
    findings.append(_finding(
        "payment_channel",
        f"Payment channel: {payment_channel}" if payment_channel else "Payment channel not mentioned",
        "SUPPORTED" if payment_channel else "UNVERIFIED",
        "The offer names this payment channel." if payment_channel else "No payment channel was identified.",
        payment_context,
        highlight=_highlight(payment_channel, offer_text),
    ))

    findings.append(_finding(
        "urgency",
        f"Urgency: {offer.urgency}" if offer.urgency else "No urgency wording found",
        "SUPPORTED" if offer.urgency else "UNVERIFIED",
        "The offer uses time pressure." if offer.urgency else "No clear time pressure was identified.",
        highlight=_highlight(offer.urgency, offer_text),
    ))

    sensitive_request = re.search(
        r"\b(otp|one[- ]time password|bank login|card details|cvv)\b",
        offer_text,
        flags=re.IGNORECASE,
    )
    if sensitive_request:
        flags.append("sensitive_info_requested")

    if any(flag in flags for flag in ("asks_fee", "personal_payment_channel", "free_email_recruiter", "sensitive_info_requested")):
        verdict = "HIGH_RISK"
    elif (
        findings[0]["status"] == "SUPPORTED"
        and findings[3]["status"] == "SUPPORTED"
        and offer.fee_asked is False
        and not flags
    ):
        verdict = "NO_RED_FLAGS_FOUND"
    else:
        verdict = "UNVERIFIED"

    return findings, flags, verdict
