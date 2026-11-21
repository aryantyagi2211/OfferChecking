from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str
    type: str
    text: str
    value: str | None = None
    highlight: str | None = None


class ExtractedOffer(BaseModel):
    company: str | None = None
    recruiter: str | None = None
    email_domain: str | None = None
    company_domain: str | None = None
    website_url: str | None = None
    role: str | None = None
    pay: str | None = None
    fee_asked: bool | None = None
    fee_amount: str | None = None
    payment_channel: Literal["UPI", "bank", "crypto", "gift_card", "cash"] | None = None
    urgency: str | None = None


class Evidence(BaseModel):
    id: str
    claim_id: str
    url: str
    title: str
    snippet: str
    source_type: Literal["official", "news", "forum", "unknown"]
    retrieved_at: str
    domain: str
    query_types: list[
        Literal["official", "careers", "fraud_notice", "scam_reports", "registration_news"]
    ] = Field(default_factory=list)


class Finding(BaseModel):
    claim_id: str
    status: Literal["SUPPORTED", "CONTRADICTED", "UNVERIFIED"]
    evidence_ids: list[str]
    reason: str
