import json
import os
import email
import email.policy
from io import BytesIO
import uuid
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from extractor import extract_offer
from investigator import investigate
from evidence import process_evidence
from rule_engine import build_findings
from report import compose_report
from llm import gemini_extract_image
from pypdf import PdfReader

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="OfferCheck")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class AnalyzeResponse(BaseModel):
    job_id: str


jobs: dict[str, dict] = {}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    text: str = Form(default=""),
    language: Literal["simple_english", "hinglish"] = Form(default="simple_english"),
    file: UploadFile | None = File(default=None),
):
    if file is not None:
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("File exceeds 10 MB")
        model = os.getenv("EXTRACT_MODEL")
        if not model:
            raise RuntimeError("EXTRACT_MODEL is not configured")
        if file.content_type in {"image/png", "image/jpeg", "image/webp"}:
            text = await gemini_extract_image(data, file.content_type, model)
        elif file.content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf"):
            try:
                reader = PdfReader(BytesIO(data))
                text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            except Exception as error:
                raise ValueError("Could not read PDF") from error
            if len(text) < 40:
                text = await gemini_extract_image(data, "application/pdf", model)
        elif (file.filename or "").lower().endswith(".eml") or file.content_type == "message/rfc822":
            message = email.message_from_bytes(data, policy=email.policy.default)
            body = message.get_body(preferencelist=("plain", "html"))
            body_text = body.get_content() if body else ""
            from_address = str(message.get("From", ""))
            reply_to = str(message.get("Reply-To", ""))
            received_spf = str(message.get("Received-SPF", ""))
            authentication = str(message.get("Authentication-Results", ""))
            flags = []
            if reply_to and reply_to != from_address:
                flags.append("Reply-To does not match From")
            if "fail" in received_spf.lower() or "spf=fail" in authentication.lower():
                flags.append("SPF failed")
            if "dkim=fail" in authentication.lower():
                flags.append("DKIM failed")
            text = f"{body_text}\nEmail headers: From: {from_address}\nReply-To: {reply_to}\n" + "\n".join(flags)
        else:
            raise ValueError("File must be PNG, JPEG, WebP, PDF or .eml")
    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "text": text,
        "language": language,
        "status": "queued",
    }
    return AnalyzeResponse(job_id=job_id)


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    if job_id not in jobs:
        return StreamingResponse(
            iter([b'event: error\ndata: {"type":"error","message":"Unknown job"}\n\n']),
            media_type="text/event-stream",
        )

    async def events():
        steps = [
            {"type": "step", "id": "reading", "label": "Reading the offer", "status": "running", "query": ""},
            {"type": "step", "id": "official", "label": "Finding the official site", "status": "waiting", "query": ""},
            {"type": "step", "id": "fraud_notice", "label": "Looking for the fraud warning page", "status": "waiting", "query": ""},
            {"type": "step", "id": "scam_reports", "label": "Searching scam reports", "status": "waiting", "query": ""},
            {"type": "step", "id": "writing", "label": "Writing your result", "status": "waiting", "query": ""},
        ]
        for index, step in enumerate(steps):
            if index > 0:
                steps[index - 1]["status"] = "done"
                yield f"data: {json.dumps(steps[index - 1])}\n\n"
            yield f"data: {json.dumps(step)}\n\n"

        try:
            offer = await extract_offer(jobs[job_id]["text"])
            steps[0]["status"] = "done"
            yield f"data: {json.dumps(steps[0])}\n\n"

            groups = await investigate(offer.company, offer.role)
            for step_id in ("official", "fraud_notice", "scam_reports"):
                match = next(step for step in steps if step["id"] == step_id)
                match["status"] = "done"
                match["query"] = next(
                    query
                    for key, query in {
                        "official": f"{offer.company or 'company'} official website careers",
                        "fraud_notice": f"{offer.company or 'company'} recruitment fraud warning",
                        "scam_reports": f"{offer.company or 'company'} scam fake job internship",
                    }.items()
                    if key == step_id
                )
                yield f"data: {json.dumps(match)}\n\n"

            evidence = process_evidence(groups)
            findings, flags, verdict = build_findings(offer, evidence)
            report = await compose_report(
                offer,
                evidence,
                findings,
                flags,
                verdict,
                jobs[job_id]["language"],
            )
        except Exception as error:
            yield f"data: {json.dumps({'type':'error','message':str(error)})}\n\n"
            return

        yield f"data: {json.dumps({'type':'report', **report})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
