import json
import os
from datetime import datetime

from evidence import Evidence
from llm import PROMPTS, gemini_json
from models import ExtractedOffer


BANNED_WORDS = ("safe", "100%", "guaranteed", "definitely a scam")


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

    valid_ids = {item.id for item in evidence}
    for claim in output.get("claims", []):
        claim["evidence_ids"] = [
            evidence_id
            for evidence_id in claim.get("evidence_ids", [])
            if evidence_id in valid_ids
        ]
        if not claim["evidence_ids"]:
            claim["status"] = "UNVERIFIED"

    finding_by_id = {finding["claim_id"]: finding for finding in findings}
    for claim in output.get("claims", []):
        finding = finding_by_id.get(claim.get("claim_id"))
        if finding:
            claim["status"] = finding["status"]

    output["verdict_level"] = verdict
    return output


async def compose_report(
    offer: ExtractedOffer,
    evidence: list[Evidence],
    findings: list[dict],
    flags: list[str],
    verdict: str,
    language: str,
) -> dict:
    prompt = (PROMPTS.parent / "report_system.txt").read_text(encoding="utf-8")
    model = os.getenv("ANALYZE_MODEL")
    if not model:
        raise RuntimeError("ANALYZE_MODEL is not configured")

    actions = standard_actions(offer, verdict)
    questions = standard_questions(offer)
    payload = {
        "verdict_level": verdict,
        "language": language,
        "claims": findings,
        "evidence": [item.model_dump() for item in evidence],
        "flags": flags,
        "standard_actions": actions,
        "standard_questions": questions,
        "offer_text": "<available in pipeline context>",
    }

    try:
        output = await gemini_json(prompt, payload, model)
        output = validate_output(output, evidence, findings, verdict)
    except Exception:
        output = {
            "headline": "We could not confirm this offer.",
            "summary": "The available evidence was limited. Review the checks below.",
            "claims": [
                {
                    "claim_id": finding["claim_id"],
                    "status": finding["status"],
                    "text": finding["reason"][:10],
                    "reason": finding["reason"],
                    "evidence_ids": [
                        evidence_id
                        for evidence_id in finding["evidence_ids"]
                        if evidence_id in {item.id for item in evidence}
                    ],
                }
                for finding in findings
            ],
            "cant_verify": ["The recruiter identity", "The role details", "The pay terms"],
            "do_this": actions,
            "ask_them": questions,
        }
        output = validate_output(output, evidence, findings, verdict)

    output["language"] = language
    output["sources"] = [item.model_dump() for item in evidence]
    return output
