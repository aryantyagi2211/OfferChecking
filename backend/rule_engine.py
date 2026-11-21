from models import Evidence, ExtractedOffer


def build_findings(offer: ExtractedOffer, evidence: list[Evidence]) -> tuple[list[dict], list[str], str]:
    findings: list[dict] = []
    flags: list[str] = []

    if offer.fee_asked:
        flags.append("asks_fee")
        findings.append({
            "claim_id": "c1",
            "status": "CONTRADICTED" if any(item.source_type == "official" for item in evidence) else "UNVERIFIED",
            "evidence_ids": [item.id for item in evidence if item.source_type == "official"][:2],
            "reason": "The offer asks the candidate for an upfront fee.",
        })

    if offer.payment_channel in {"UPI", "crypto", "gift_card", "cash"}:
        flags.append("personal_payment_channel")

    if offer.email_domain:
        if offer.email_domain.lower() in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}:
            flags.append("free_email_recruiter")
            findings.append({
                "claim_id": "c2",
                "status": "CONTRADICTED" if offer.company else "UNVERIFIED",
                "evidence_ids": [item.id for item in evidence if item.source_type == "official"][:1],
                "reason": "The recruiter uses a free-mail address.",
            })

    if offer.company:
        findings.append({
            "claim_id": "c_company",
            "status": "SUPPORTED" if evidence else "UNVERIFIED",
            "evidence_ids": [item.id for item in evidence][:1],
            "reason": "The company has public search evidence." if evidence else "No public evidence was found.",
        })
    if offer.role:
        findings.append({
            "claim_id": "c_role",
            "status": "UNVERIFIED",
            "evidence_ids": [item.id for item in evidence if item.source_type == "official"][:1],
            "reason": "No matching role was confirmed.",
        })

    if "asks_fee" in flags or "personal_payment_channel" in flags or "free_email_recruiter" in flags:
        verdict = "HIGH_RISK"
    elif (
        offer.company
        and offer.role
        and not offer.fee_asked
        and evidence
        and any(item.source_type == "official" for item in evidence)
    ):
        verdict = "NO_RED_FLAGS_FOUND"
    else:
        verdict = "UNVERIFIED"

    return findings, flags, verdict
