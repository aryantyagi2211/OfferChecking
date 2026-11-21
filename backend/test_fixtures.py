import asyncio
import json
import os
from pathlib import Path

import httpx

import app as app_module
import extractor
import llm as llm_module
import report as report_module
from evidence import process_evidence
from investigator import SEARCH_URL, search_one
from models import Evidence, ExtractedOffer
from report import validate_output
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
        fixture["offer"],
    )
    if fixture["name"] == "scam_on_real_company":
        fee_finding = next(item for item in findings if item["claim_id"] == "fee_asked")
        assert verdict == "HIGH_RISK"
        assert fee_finding["status"] == "CONTRADICTED"
        assert fee_finding["evidence_ids"] == ["e1"]
        report = validate_output(
            {
                "headline": "Do not pay this fee",
                "summary": "We found an official notice about candidate fees.",
                "claims": [{"claim_id": "fee_asked", "status": "SUPPORTED", "text": "invented", "reason": "The notice conflicts.", "evidence_ids": ["fake-id"]}],
                "cant_verify": [],
                "do_this": [],
                "ask_them": [],
            },
            evidence,
            findings,
            verdict,
        )
        fee_report = next(item for item in report["claims"] if item["claim_id"] == "fee_asked")
        assert fee_report["status"] == "CONTRADICTED"
        assert fee_report["evidence_ids"] == ["e1"]
    elif fixture["name"] == "legit_offer":
        assert verdict == "NO_RED_FLAGS_FOUND"
    elif fixture["name"] == "tiny_company_unverified":
        assert verdict == "UNVERIFIED"
    print(f"{fixture['name']}: {verdict}")

mismatch_offer = ExtractedOffer(
    company="Northgate Technologies",
    email_domain="gmail.com",
    company_domain="northgate.com",
)
mismatch_findings, _, _ = build_findings(mismatch_offer, evidence, "northgate.hr@gmail.com")
email_finding = next(item for item in mismatch_findings if item["claim_id"] == "email_or_domain")
assert email_finding["status"] == "UNVERIFIED"

official_email_evidence = Evidence(
    id="e2",
    claim_id="",
    url="https://northgate.com/careers",
    title="Northgate careers",
    snippet="Official recruiter emails use jobs@northgate.com.",
    source_type="official",
    retrieved_at="2026-11-21T10:42:00+05:30",
    domain="northgate.com",
)
email_findings, _, _ = build_findings(
    mismatch_offer,
    [official_email_evidence],
    "northgate.hr@gmail.com",
)
email_finding = next(item for item in email_findings if item["claim_id"] == "email_or_domain")
assert email_finding["status"] == "CONTRADICTED"
assert email_finding["evidence_ids"] == ["e2"]

unknown_fee = ExtractedOffer(company="Unknown Co", role="Intern", fee_asked=None)
unknown_fee_findings, _, unknown_fee_verdict = build_findings(unknown_fee, [])
fee_finding = next(item for item in unknown_fee_findings if item["claim_id"] == "fee_asked")
assert fee_finding["status"] == "UNVERIFIED"
assert unknown_fee_verdict == "UNVERIFIED"


async def check_demo_extraction_fallbacks():
    original_gemini_json = extractor.gemini_json
    old_model = os.environ.get("EXTRACT_MODEL")
    os.environ["EXTRACT_MODEL"] = "demo-test-model"
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
    response = httpx.Response(429, request=request)
    failures = [
        httpx.HTTPStatusError("rate limited", request=request, response=response),
        httpx.HTTPStatusError(
            "service unavailable",
            request=request,
            response=httpx.Response(503, request=request),
        ),
        httpx.TimeoutException("timed out"),
        RuntimeError("Gemini failed: timeout"),
        RuntimeError("Gemini fallback failed: 503"),
    ]
    try:
        for failure in failures:
            async def fail_request(*args, error=failure, **kwargs):
                raise error

            extractor.gemini_json = fail_request
            for preset in extractor.DEMO_FALLBACKS:
                offer, used_fallback = await extractor.extract_offer(preset["offer_text"])
                assert used_fallback
                assert offer.company == preset["extracted"]["company"]
                assert offer.role == preset["extracted"]["role"]
    finally:
        extractor.gemini_json = original_gemini_json
        if old_model is None:
            os.environ.pop("EXTRACT_MODEL", None)
        else:
            os.environ["EXTRACT_MODEL"] = old_model

    print(f"demo_fallbacks: {len(extractor.DEMO_FALLBACKS)} presets x {len(failures)} failure cases")


asyncio.run(check_demo_extraction_fallbacks())


async def check_rule_based_report_fallback():
    original_gemini_json = report_module.gemini_json
    old_logger_disabled = report_module.logger.disabled
    old_model = os.environ.get("ANALYZE_MODEL")
    os.environ["ANALYZE_MODEL"] = "demo-test-model"
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
    response = httpx.Response(429, request=request)

    async def fail_report(*args, **kwargs):
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    report_module.gemini_json = fail_report
    report_module.logger.disabled = True
    try:
        scam_offer = ExtractedOffer.model_validate(fixtures[0]["extracted"])
        findings, flags, verdict = build_findings(scam_offer, evidence, fixtures[0]["offer"])
        cached_report = await report_module.compose_report(
            scam_offer,
            evidence,
            findings,
            flags,
            verdict,
            "simple_english",
            fixtures[0]["offer"],
        )
        assert cached_report["used_rule_based_report"]
        assert cached_report["verdict_level"] == "HIGH_RISK"
        assert cached_report["sources"][0]["url"] == evidence[0].url
    finally:
        report_module.gemini_json = original_gemini_json
        report_module.logger.disabled = old_logger_disabled
        if old_model is None:
            os.environ.pop("ANALYZE_MODEL", None)
        else:
            os.environ["ANALYZE_MODEL"] = old_model

    print(f"report_fallback: {cached_report['verdict_level']}; citations: {len(cached_report['sources'])}")


asyncio.run(check_rule_based_report_fallback())


async def check_you_search_citation_mapping():
    original_key = os.environ.get("YOU_API_KEY")
    os.environ["YOU_API_KEY"] = "test-you-api-key"
    api_results = [
        {
            "url": "https://www.infosys.com/careers/apply/recruitment-fraud-alert.html",
            "title": "Infosys Careers Recruitment Fraud Alert",
            "snippet": "Infosys does not charge candidates for recruitment. Official messages come from @infosys.com.",
        },
        {
            "url": "https://www.infosys.com/careers/data-analyst.html",
            "title": "Infosys Careers - Data Analyst",
            "snippet": "Infosys lists a Data Analyst opening.",
        },
        {
            "url": "https://news.example/infosys-recruitment",
            "title": "Fake job fee reports",
            "snippet": "Candidates reported UPI registration fee requests in fake job messages.",
        },
    ]

    def mock_search(request):
        assert str(request.url) == SEARCH_URL
        assert request.headers["X-API-Key"] == "test-you-api-key"
        assert json.loads(request.content)["query"] == "Infosys recruitment fraud"
        return httpx.Response(200, json={"results": {"web": api_results}})

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_search)) as client:
            results = await search_one(client, "Infosys recruitment fraud")
        groups = {
            "official": [results[0]],
            "careers": [results[1]],
            "fraud_notice": [results[0]],
            "scam_reports": [results[2]],
            "registration_news": [],
        }
        offer = ExtractedOffer(
            company="Infosys",
            company_domain="infosys.com",
            role="Data Analyst",
            email_domain="gmail.com",
            fee_asked=True,
            fee_amount="Rs 1,999",
            payment_channel="UPI",
        )
        evidence = process_evidence(groups, offer)
        assert [item.url for item in evidence] == [item["url"] for item in api_results]
        assert evidence[0].snippet.startswith("Infosys does not charge candidates")
        assert evidence[0].source_type == "official"
        assert set(evidence[0].query_types) == {"official", "fraud_notice"}

        findings, _, _ = build_findings(offer, evidence)
        findings_by_id = {item["claim_id"]: item for item in findings}
        assert "e1" in findings_by_id["company"]["evidence_ids"]
        assert findings_by_id["recruiter"]["evidence_ids"] == ["e1"]
        assert findings_by_id["email_or_domain"]["evidence_ids"] == ["e1"]
        assert findings_by_id["role"]["evidence_ids"] == ["e2"]
        assert findings_by_id["pay"]["evidence_ids"] == ["e2"]
        assert findings_by_id["fee_asked"]["status"] == "CONTRADICTED"
        assert findings_by_id["fee_asked"]["evidence_ids"] == ["e1"]
        assert findings_by_id["payment_channel"]["evidence_ids"] == ["e3"]
        assert process_evidence({}, offer) == []

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503, request=request)
            )
        ) as failed_client:
            try:
                await search_one(failed_client, "Infosys recruitment fraud")
            except httpx.HTTPStatusError as error:
                assert error.response.status_code == 503
            else:
                raise AssertionError("Search API errors must not fabricate evidence")
    finally:
        if original_key is None:
            os.environ.pop("YOU_API_KEY", None)
        else:
            os.environ["YOU_API_KEY"] = original_key

    print(f"you_search_citations: {len(evidence)} returned URLs mapped to linked findings")


asyncio.run(check_you_search_citation_mapping())


async def check_image_upload_sse_flow():
    original_model = os.environ.get("EXTRACT_MODEL")
    originals = {
        "gemini_extract_image": app_module.gemini_extract_image,
        "extract_offer": app_module.extract_offer,
        "investigate": app_module.investigate,
        "compose_report": app_module.compose_report,
    }
    os.environ["EXTRACT_MODEL"] = "demo-test-model"
    vision_calls = 0
    extracted_text = "Infosys Data Analyst offer asks for Rs 1,999."
    offer = ExtractedOffer(
        company="Infosys",
        company_domain="infosys.com",
        role="Data Analyst",
        fee_asked=True,
        fee_amount="Rs 1,999",
    )
    live_result = {
        "url": "https://www.infosys.com/careers/apply/recruitment-fraud-alert.html",
        "title": "Infosys recruitment fraud alert",
        "snippet": "Infosys cautions candidates against fake fee offers.",
    }

    async def fake_vision(data, mime_type, model):
        nonlocal vision_calls
        vision_calls += 1
        assert data == b"captured-jpeg"
        assert mime_type == "image/jpeg"
        assert model == "demo-test-model"
        return extracted_text

    async def fake_extract(text, hints):
        assert text == extracted_text
        return offer, False

    async def fake_investigate(company, role, website_url, company_domain, progress):
        await progress({
            "type": "step",
            "id": "search_official",
            "label": "Finding the company's official site",
            "status": "done",
            "query": "Infosys official",
        })
        return {"official": [live_result]}

    async def fake_report(offer, evidence, findings, flags, verdict, language, offer_text):
        return {
            "verdict_level": verdict,
            "language": language,
            "headline": "Review this offer",
            "summary": "Check the linked company information before proceeding.",
            "claims": findings,
            "cant_verify": [],
            "do_this": [],
            "ask_them": [],
            "sources": [item.model_dump() for item in evidence],
        }

    app_module.gemini_extract_image = fake_vision
    app_module.extract_offer = fake_extract
    app_module.investigate = fake_investigate
    app_module.compose_report = fake_report
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/analyze",
                data={"language": "simple_english"},
                files={"file": ("capture.jpg", b"captured-jpeg", "image/jpeg")},
            )
            assert response.status_code == 202
            assert vision_calls == 0
            stream = await client.get(f"/stream/{response.json()['job_id']}")

        assert vision_calls == 1
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[6:])
            for line in stream.text.splitlines()
            if line.startswith("data: ")
        ]
        report_event = next(event for event in events if event["type"] == "report")
        assert report_event["evidence_mode"] == "live"
        assert report_event["offer_text"] == extracted_text
        assert report_event["sources"][0]["url"] == live_result["url"]
        assert any(
            event["type"] == "step"
            and event["id"] == "reading"
            and event["label"] == "Extracting text from attachment"
            for event in events
        )
        assert any(event["type"] == "step" and event["id"] == "search_official" for event in events)
    finally:
        for name, function in originals.items():
            setattr(app_module, name, function)
        if original_model is None:
            os.environ.pop("EXTRACT_MODEL", None)
        else:
            os.environ["EXTRACT_MODEL"] = original_model

    print("image_upload_sse: JPEG accepted; vision extraction, live evidence and report event passed")


asyncio.run(check_image_upload_sse_flow())


async def check_gemini_keys_and_groq_fallback():
    names = (
        "VISION_API_KEY",
        "GEMINI_VISION_API_KEY",
        "ANALYZE_API_KEY",
        "GEMINI_ANALYZE_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "GROQ_MODEL",
    )
    original_env = {name: os.environ.pop(name, None) for name in names}
    original_generate = llm_module._gemini_generate
    original_groq_json = llm_module.groq_json
    try:
        os.environ["GEMINI_API_KEY"] = "legacy-test-key"
        assert llm_module.gemini_api_key_for("vision") == "legacy-test-key"
        assert llm_module.gemini_api_key_for("analysis") == "legacy-test-key"
        os.environ["GEMINI_VISION_API_KEY"] = "vision-alias-test-key"
        os.environ["VISION_API_KEY"] = "vision-test-key"
        os.environ["GEMINI_ANALYZE_API_KEY"] = "analyze-alias-test-key"
        os.environ["ANALYZE_API_KEY"] = "analyze-test-key"
        assert llm_module.gemini_api_key_for("vision") == "vision-test-key"
        assert llm_module.gemini_api_key_for("analysis") == "analyze-test-key"

        os.environ["GROQ_API_KEY"] = "groq-test-key"
        os.environ["GROQ_MODEL"] = "groq-test-model"

        async def fail_unexpected_gemini(payload, model, api_key):
            raise AssertionError("Gemini must not run when Groq is configured")

        async def succeed_groq(system_prompt, user_payload, model, api_key):
            assert system_prompt == "test system prompt"
            assert user_payload == {"sample": "untrusted"}
            assert model == "groq-test-model"
            assert api_key == "groq-test-key"
            return {"provider": "groq"}

        llm_module._gemini_generate = fail_unexpected_gemini
        llm_module.groq_json = succeed_groq
        result = await llm_module.gemini_json(
            "test system prompt",
            {"sample": "untrusted"},
            "extract-test-model",
            task="vision",
        )
        assert result == {"provider": "groq"}

        async def default_model_groq(system_prompt, user_payload, model, api_key):
            assert model == llm_module.DEFAULT_GROQ_MODEL
            return {"provider": "groq-default-model"}

        os.environ["GROQ_MODEL"] = ""
        llm_module.groq_json = default_model_groq
        default_result = await llm_module.gemini_json(
            "test system prompt",
            {"sample": "untrusted"},
            "extract-test-model",
            task="vision",
        )
        assert default_result == {"provider": "groq-default-model"}
        os.environ["GROQ_MODEL"] = "groq-test-model"
        llm_module.groq_json = succeed_groq

        groq_api_key = os.environ.pop("GROQ_API_KEY")
        async def analysis_response(payload, model, api_key):
            assert api_key == "analyze-test-key"
            return {
                "candidates": [{
                    "content": {"parts": [{"text": '{"provider":"gemini"}'}]}
                }]
            }

        llm_module._gemini_generate = analysis_response
        analysis_result = await llm_module.gemini_json(
            "analysis prompt",
            {"sample": "offer"},
            "analyze-test-model",
        )
        assert analysis_result == {"provider": "gemini"}
        os.environ["GROQ_API_KEY"] = groq_api_key

        async def vision_response(payload, model, api_key):
            assert api_key == "vision-test-key"
            return {
                "candidates": [{
                    "content": {"parts": [{
                        "text": '{"is_offer":true,"offer_text":"visible offer text"}'
                    }]}
                }]
            }

        llm_module._gemini_generate = vision_response
        extracted_text = await llm_module.gemini_extract_image(b"image", "image/jpeg", "vision-test-model")
        assert extracted_text == "visible offer text"

        async def no_offer_vision(payload, model, api_key):
            return {
                "candidates": [{
                    "content": {"parts": [{
                        "text": '{"is_offer":false,"offer_text":""}'
                    }]}
                }]
            }

        llm_module._gemini_generate = no_offer_vision
        try:
            await llm_module.gemini_extract_image(b"image", "image/jpeg", "vision-test-model")
        except llm_module.NoJobOfferDetected as error:
            assert str(error) == llm_module.NO_JOB_OFFER_MESSAGE
        else:
            raise AssertionError("Images without an offer must not return page text")

        groq_attempts = 0

        async def retry_groq(system_prompt, user_payload, model, api_key):
            nonlocal groq_attempts
            groq_attempts += 1
            if groq_attempts == 1:
                raise httpx.TimeoutException("mock Groq timeout")
            return {"provider": "groq retry"}

        async def rate_limited_gemini(payload, model, api_key):
            request = httpx.Request(
                "POST",
                "https://generativelanguage.googleapis.com/test",
            )
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

        llm_module._gemini_generate = rate_limited_gemini
        llm_module.groq_json = retry_groq
        retry_result = await llm_module.gemini_json(
            "retry prompt",
            {"sample": "offer"},
            "extract-test-model",
            task="vision",
        )
        assert retry_result == {"provider": "groq retry"}
        assert groq_attempts == 2

        original_client = llm_module.httpx.AsyncClient

        class FakeGroqClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers, json):
                assert url == "https://api.groq.com/openai/v1/chat/completions"
                assert headers["Authorization"] == "Bearer groq-test-key"
                assert json["model"] == "groq-test-model"
                return httpx.Response(
                    200,
                    request=httpx.Request("POST", url),
                    json={"choices": [{"message": {"content": '{"provider":"groq"}'}}]},
                )

        llm_module.httpx.AsyncClient = lambda **kwargs: FakeGroqClient()
        try:
            groq_result = await original_groq_json(
                "system prompt",
                {"sample": "offer"},
                "groq-test-model",
                "groq-test-key",
            )
        finally:
            llm_module.httpx.AsyncClient = original_client
        assert groq_result == {"provider": "groq"}
    finally:
        llm_module._gemini_generate = original_generate
        llm_module.groq_json = original_groq_json
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    print("llm_providers: key separation, legacy key fallback, and optional Groq fallback passed")


asyncio.run(check_gemini_keys_and_groq_fallback())


async def check_document_offer_filter():
    original_gemini_json = llm_module.gemini_json
    raw_document = "Navigation Home About. JOB OFFER: Example Co, Data Analyst, salary Rs 50,000. Apply at jobs@example.com."
    clean_offer = "JOB OFFER: Example Co, Data Analyst, salary Rs 50,000. Apply at jobs@example.com."

    async def filtered_document(system_prompt, user_payload, model, task):
        assert user_payload["document_text"] == raw_document
        assert "Ignore menus" in system_prompt
        assert model == "test-extract-model"
        assert task == "vision"
        return {"is_offer": True, "offer_text": clean_offer}

    llm_module.gemini_json = filtered_document
    try:
        extracted = await llm_module.extract_offer_text_from_document(raw_document, "test-extract-model")
        assert extracted == clean_offer

        async def reject_document(system_prompt, user_payload, model, task):
            return {"is_offer": False, "offer_text": ""}

        llm_module.gemini_json = reject_document
        try:
            await llm_module.extract_offer_text_from_document("Site menus and unrelated news.", "test-extract-model")
        except llm_module.NoJobOfferDetected as error:
            assert str(error) == llm_module.NO_JOB_OFFER_MESSAGE
        else:
            raise AssertionError("Non-offer documents must be rejected")
    finally:
        llm_module.gemini_json = original_gemini_json

    print("file_offer_filter: offer-only content retained; unrelated document rejected")


asyncio.run(check_document_offer_filter())


async def check_non_offer_upload_sse_error():
    original_vision = app_module.gemini_extract_image
    original_model = os.environ.get("EXTRACT_MODEL")
    os.environ["EXTRACT_MODEL"] = "test-extract-model"

    async def unrelated_page(data, mime_type, model):
        return "Home | Menu | Sign in | Weather forecast"

    app_module.gemini_extract_image = unrelated_page
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_module.app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/analyze",
                files={"file": ("unrelated.jpg", b"page-image", "image/jpeg")},
            )
            assert response.status_code == 202
            stream = await client.get(f"/stream/{response.json()['job_id']}")

        events = [
            json.loads(line[6:])
            for line in stream.text.splitlines()
            if line.startswith("data: ")
        ]
        error = next(event for event in events if event["type"] == "error")
        assert error["message"] == llm_module.NO_JOB_OFFER_MESSAGE
        assert not any(event["type"] == "report" for event in events)
    finally:
        app_module.gemini_extract_image = original_vision
        if original_model is None:
            os.environ.pop("EXTRACT_MODEL", None)
        else:
            os.environ["EXTRACT_MODEL"] = original_model

    print("non_offer_upload: clear SSE error returned without analyzing page chrome")


asyncio.run(check_non_offer_upload_sse_error())
