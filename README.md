# OfferCheck

A company can be real. Its job offer can still be fake.

## How it works

Offer text is treated as untrusted data. The app extracts claims, searches You.com in parallel, and applies deterministic rules to the returned evidence. Gemini helps extract details and write the report; it never chooses the verdict.

```text
Offer -> claim extraction -> parallel You.com search -> evidence + rule engine -> report
```

## Run locally

Run these commands from the project root in PowerShell. Create `.env` only if you do not already have one:

```powershell
python -m pip install -r backend\requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set YOU_API_KEY, EXTRACT_MODEL and ANALYZE_MODEL, plus provider keys in .env
python -m uvicorn app:app --app-dir backend --reload
```

Open http://127.0.0.1:8000. Run the offline verdict and demo-fallback checks in a second terminal:

```powershell
python backend\test_fixtures.py
```

Fresh checks call You.com with `X-API-Key` from `.env`; only URLs returned in `results.web` can be cited. The result status distinguishes live evidence from an older browser-cached demo report. Exact demo presets have cached extraction details for Gemini HTTP 429/503/timeouts. Presets are fictional impersonation scenarios, not claims about Infosys. A cached report is used only after a temporary provider failure.

`POST /analyze` accepts multipart fields `text`, `company`, `recruiter`, `role`, `url`, `domain`, `language`, and optional `file`. It returns a job ID quickly; file OCR runs in the subsequent `GET /stream/{job_id}` SSE job, which emits live steps and the report.

For screen capture, click **Share screen** and choose a tab, window, or screen in the browser picker. OfferCheck captures one frame, resizes it to at most 1280px, and compresses it as JPEG. A compact attachment card remains visible while OCR runs in the background. Canceling or denying permission uploads nothing. Clipboard paste and drag-and-drop still work. Screen capture requires a secure browser context; `http://127.0.0.1:8000` qualifies.

File extraction keeps only job, internship, or freelance offer content and ignores page chrome or unrelated text. If no offer is detected, the analysis stops with a clear message instead of showing unrelated page content.

Gemini uses `VISION_API_KEY` (or `GEMINI_VISION_API_KEY`) for image OCR and claim extraction, and `ANALYZE_API_KEY` (or `GEMINI_ANALYZE_API_KEY`) for report writing. Each falls back to `GEMINI_API_KEY`. `EXTRACT_MODEL` and `ANALYZE_MODEL` remain configurable. When `GROQ_API_KEY` is set, Groq is tried first for text-only extraction/report calls, then Gemini; if Gemini is temporarily unavailable, Groq is retried. `GROQ_MODEL` defaults to `openai/gpt-oss-20b`. Image OCR remains on Gemini.

## Limitations

- Live checks need You.com credentials, an internet connection, and Gemini Vision/Analyze credentials or the optional Groq text fallback. Image OCR specifically needs a Gemini Vision key.
- Cached reports are limited to the built-in demo presets and may contain older evidence; the UI labels these results. User-entered offers are not cached.
- `NO RED FLAGS FOUND` is not a guarantee. A missing result is not proof of fraud; use `UNVERIFIED` when evidence is insufficient.
- Gmail OAuth is not implemented; the Gmail dialog is a UI placeholder. Use text input, screenshots, PDFs, or `.eml` files.
- Offer text and uploaded content are sent to the configured model/search providers for processing. The backend does not persist submitted offers.
