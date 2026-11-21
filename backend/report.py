import json
import logging
import os

import httpx

if __package__:
    from .evidence import Evidence
    from .llm import PROMPTS, gemini_json
    from .models import ExtractedOffer
else:
    from evidence import Evidence
    from llm import PROMPTS, gemini_json
    from models import ExtractedOffer


BANNED_WORDS = ("safe", "100%", "guaranteed", "definitely a scam")
logger = logging.getLogger(__name__)


def standard_actions(offer: ExtractedOffer, verdict: str) -> list[str]:
    actions = ["Do not share Aadhaar, PAN, bank details or OTP yet."]
    if offer.fee_asked:
        actions.append("Do not pay any fee, deposit or kit money.")
    if offer.recruiter:
        actions.append("Email the company using the address on its official domain.")
    if offer.role:
        actions.append("Ask for the job ID and check the official careers page.")
    if verdict == "HIGH_RISK":
        actions.append("Block the number and report it at cybercrime.gov.in or call 1930.")
    return actions[:3]


def standard_questions(offer: ExtractedOffer) -> list[str]:
    questions = [
        "Can you email me from an official company address?",
        "What is the job ID on the careers page?",
    ]
    if offer.fee_asked:
        questions.append("Why is a fee needed?")
    return questions[:3]


def validate_output(output: dict, evidence: list[Evidence], findings: list[dict], verdict: str) -> dict:
    text = json.dumps(output).lower()
    if any(word in text for word in BANNED_WORDS):
        raise ValueError("Banned wording found")
    if len(output.get("headline", "").split()) > 8:
        raise ValueError("Report headline exceeds the word limit")
    if len(output.get("summary", "").split()) > 20:
        raise ValueError("Report summary exceeds the word limit")

    valid_ids = {item.id for item in evidence}
    for claim in output.get("claims", []):
        claim["evidence_ids"] = [
            evidence_id
            for evidence_id in claim.get("evidence_ids", [])
            if evidence_id in valid_ids
        ]
        if not claim["evidence_ids"]:
            claim["status"] = "UNVERIFIED"

    generated_claims = {claim.get("claim_id"): claim for claim in output.get("claims", [])}
    output["claims"] = []
    for finding in findings:
        claim = generated_claims.get(finding["claim_id"], {})
        generated_evidence_ids = [
            evidence_id
            for evidence_id in claim.get("evidence_ids", [])
            if evidence_id in valid_ids
        ]
        evidence_ids = generated_evidence_ids or [
            evidence_id for evidence_id in finding["evidence_ids"] if evidence_id in valid_ids
        ]
        output["claims"].append({
            "claim_id": finding["claim_id"],
            "status": finding["status"] if evidence_ids or not finding["evidence_ids"] else "UNVERIFIED",
            "text": finding["text"],
            "reason": claim.get("reason") or finding["reason"],
            "evidence_ids": evidence_ids,
            "highlight": finding.get("highlight"),
        })
    if any(len(claim["text"].split()) > 10 or len(claim["reason"].split()) > 14 for claim in output["claims"]):
        raise ValueError("Report claim exceeds a word limit")
    for field, limit in (("cant_verify", 12), ("do_this", 12), ("ask_them", 15)):
        if any(len(item.split()) > limit for item in output.get(field, [])):
            raise ValueError(f"Report {field} item exceeds the word limit")

    output["verdict_level"] = verdict
    return output


async def compose_report(
    offer: ExtractedOffer,
    evidence: list[Evidence],
    findings: list[dict],
    flags: list[str],
    verdict: str,
    language: str,
    offer_text: str,
) -> dict:
    prompt = (PROMPTS / "report_system.txt").read_text(encoding="utf-8")
    model = os.getenv("ANALYZE_MODEL")
    if not model:
        raise RuntimeError("ANALYZE_MODEL is not configured")

    actions = standard_actions(offer, verdict)
    questions = standard_questions(offer)
    used_rule_based_report = False
    payload = {
        "verdict_level": verdict,
        "language": language,
        "claims": findings,
        "evidence": [item.model_dump() for item in evidence],
        "flags": flags,
        "standard_actions": actions,
        "standard_questions": questions,
        "offer_text": offer_text,
    }

    try:
        output = await gemini_json(prompt, payload, model)
        output = validate_output(output, evidence, findings, verdict)
    except (httpx.HTTPError, RuntimeError, ValueError):
        logger.exception("Report generation failed; returning rule-based report")
        used_rule_based_report = True
        output = {
            "headline": "We could not confirm this offer.",
            "summary": "The available evidence was limited. Review the checks below.",
            "claims": [
                {
                    "claim_id": finding["claim_id"],
                    "status": finding["status"],
                    "text": finding["text"],
                    "reason": finding["reason"],
                    "evidence_ids": finding["evidence_ids"],
                    "highlight": finding.get("highlight"),
                }
                for finding in findings
            ],
            "cant_verify": ["The recruiter identity", "The role details", "The pay terms"],
            "do_this": actions,
            "ask_them": questions,
        }
        output = validate_output(output, evidence, findings, verdict)

    output["language"] = language
    output["do_this"] = actions
    output["ask_them"] = questions
    output["sources"] = [item.model_dump() for item in evidence]
    output["used_rule_based_report"] = used_rule_based_report
    return output
