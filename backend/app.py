import asyncio
import email
import email.policy
import json
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel
from pypdf import PdfReader

from evidence import process_evidence
from extractor import extract_offer
from investigator import investigate
from llm import (
    extract_offer_text_from_document,
    gemini_extract_image,
    validate_offer_text,
)
from report import compose_report
from rule_engine import build_findings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)

app = FastAPI(title="OfferCheck")
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class AnalyzeResponse(BaseModel):
    job_id: str


jobs: dict[str, dict] = {}


def supported_upload(content_type: str, filename: str) -> bool:
    filename = filename.lower()
    return (
        content_type in {"image/png", "image/jpeg", "image/webp", "application/pdf", "message/rfc822"}
        or filename.endswith((".pdf", ".eml"))
    )


async def normalize_upload_data(
    data: bytes,
    filename: str,
    content_type: str,
) -> tuple[str, list[str]]:
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB")

    filename = filename.lower()
    if content_type in {"image/png", "image/jpeg", "image/webp"}:
        model = os.getenv("EXTRACT_MODEL")
        if not model:
            raise HTTPException(status_code=500, detail="EXTRACT_MODEL is not configured")
        text = await gemini_extract_image(data, content_type, model)
        return validate_offer_text(text), []

    if content_type == "application/pdf" or filename.endswith(".pdf"):
        try:
            reader = PdfReader(BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as error:
            raise HTTPException(status_code=400, detail="Could not read PDF") from error
        if len(text) < 40:
            model = os.getenv("EXTRACT_MODEL")
            if not model:
                raise HTTPException(status_code=500, detail="EXTRACT_MODEL is not configured")
            text = await gemini_extract_image(data, "application/pdf", model)
            return validate_offer_text(text), []
        model = os.getenv("EXTRACT_MODEL")
        if not model:
            raise HTTPException(status_code=500, detail="EXTRACT_MODEL is not configured")
        return await extract_offer_text_from_document(text, model), []

    if filename.endswith(".eml") or content_type == "message/rfc822":
        message = email.message_from_bytes(data, policy=email.policy.default)
        body = message.get_body(preferencelist=("plain", "html"))
        body_text = body.get_content() if body else ""
        model = os.getenv("EXTRACT_MODEL")
        if not model:
            raise HTTPException(status_code=500, detail="EXTRACT_MODEL is not configured")
        offer_text = await extract_offer_text_from_document(body_text, model)
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
        return (
            f"{offer_text}\nEmail headers: From: {from_address}\nReply-To: {reply_to}",
            flags,
        )

    raise HTTPException(status_code=415, detail="File must be PNG, JPEG, WebP, PDF or .eml")


@app.post("/analyze", response_model=AnalyzeResponse, status_code=202)
async def analyze(
    text: str = Form(default=""),
    company: str | None = Form(default=None),
    recruiter: str | None = Form(default=None),
    role: str | None = Form(default=None),
    url: str | None = Form(default=None),
    domain: str | None = Form(default=None),
    language: Literal["simple_english", "hinglish"] = Form(default="simple_english"),
    file: UploadFile | None = File(default=None),
):
    file_payload = None
    if file is not None:
        filename = file.filename or ""
        content_type = file.content_type or ""
        if not supported_upload(content_type, filename):
            raise HTTPException(status_code=415, detail="File must be PNG, JPEG, WebP, PDF or .eml")
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File exceeds 10 MB")
        file_payload = {
            "data": data,
            "filename": filename,
            "content_type": content_type,
        }
    if not text.strip() and file_payload is None:
        raise HTTPException(status_code=422, detail="Offer text is required")

    job_id = uuid.uuid4().hex
    jobs[job_id] = {
        "text": text,
        "hints": {
            "company": company,
            "recruiter": recruiter,
            "role": role,
            "url": url,
            "domain": domain,
        },
        "file": file_payload,
        "language": language,
    }
    return AnalyzeResponse(job_id=job_id)


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        async def unknown_job():
            yield 'data: {"type":"error","message":"Unknown or expired analysis"}\n\n'
        return StreamingResponse(unknown_job(), media_type="text/event-stream")

    async def events():
        def encode(event: dict) -> str:
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        try:
            has_file = job["file"] is not None
            yield encode({
                "type": "step",
                "id": "reading",
                "label": "Extracting text from attachment" if has_file else "Reading the offer",
                "status": "running",
                "query": "",
            })
            offer_text = job["text"]
            file_flags: list[str] = []
            if has_file:
                upload = job["file"]
                offer_text, file_flags = await normalize_upload_data(
                    upload["data"],
                    upload["filename"],
                    upload["content_type"],
                )
            if not offer_text.strip():
                raise HTTPException(status_code=422, detail="Offer text is required")
            offer, used_demo_fallback = await extract_offer(offer_text, job["hints"])
            yield encode({
                "type": "step",
                "id": "reading",
                "label": (
                    "Using cached demo details"
                    if used_demo_fallback
                    else "Text extracted from attachment" if has_file
                    else "Reading the offer"
                ),
                "status": "done",
                "query": "",
            })

            progress_queue: asyncio.Queue[dict] = asyncio.Queue()

            async def report_progress(event: dict) -> None:
                await progress_queue.put(event)

            investigation = asyncio.create_task(investigate(
                offer.company,
                offer.role,
                offer.website_url,
                offer.company_domain,
                report_progress,
            ))
            while not investigation.done() or not progress_queue.empty():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=0.25)
                    yield encode(event)
                except asyncio.TimeoutError:
                    continue
            groups = await investigation

            evidence = process_evidence(groups, offer)
            findings, flags, verdict = build_findings(offer, evidence, offer_text)
            flags.extend(file_flags)
            yield encode({
                "type": "step",
                "id": "writing",
                "label": "Writing your result",
                "status": "running",
                "query": "",
            })
            report = await compose_report(
                offer,
                evidence,
                findings,
                flags,
                verdict,
                job["language"],
                offer_text,
            )
            report["evidence_mode"] = "live"
            report["demo_fallback"] = used_demo_fallback
            yield encode({
                "type": "step",
                "id": "writing",
                "label": "Writing your result",
                "status": "done",
                "query": "",
            })
            yield encode({"type": "report", **report, "offer_text": offer_text})
        except (HTTPException, RuntimeError, ValueError, httpx.HTTPError) as error:
            if isinstance(error, HTTPException):
                message = error.detail
            elif isinstance(error, httpx.HTTPStatusError):
                provider = {
                    "ydc-index.io": "You.com",
                    "api.groq.com": "Groq",
                }.get(error.request.url.host, "Gemini")
                message = f"{provider} returned HTTP {error.response.status_code}."
            elif isinstance(error, httpx.HTTPError):
                message = "A search or model service could not be reached. Please try again."
            else:
                message = str(error)
            yield encode({"type": "error", "message": message})
        finally:
            jobs.pop(job_id, None)

    return StreamingResponse(events(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
