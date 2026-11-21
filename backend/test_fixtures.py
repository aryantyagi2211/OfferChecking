import json
from pathlib import Path

from models import Evidence, ExtractedOffer
from rule_engine import build_findings


fixtures = json.loads((Path(__file__).parent / "fixtures.json").read_text(encoding="utf-8"))
evidence = [
    Evidence(
        id="e1",
        claim_id="",
        url="https://northgate.com/fraud-alert",
        title="Northgate fraud alert",
        snippet="Northgate never asks candidates for money.",
        source_type="official",
        retrieved_at="2026-11-21T10:42:00+05:30",
        domain="northgate.com",
    )
]
riverbend_evidence = [
    Evidence(
        id="e2",
        claim_id="",
        url="https://riverbend.example/careers",
        title="Riverbend careers",
        snippet="Riverbend lists the Data Intern role.",
        source_type="official",
        retrieved_at="2026-11-21T10:42:00+05:30",
        domain="riverbend.example",
    )
]

for fixture in fixtures:
    offer = ExtractedOffer.model_validate(fixture["extracted"])
    findings, flags, verdict = build_findings(
        offer,
        evidence if fixture["name"] == "scam_on_real_company"
        else riverbend_evidence if fixture["name"] == "legit_offer"
        else [],
    )
    print(f"{fixture['name']}: {verdict}")
