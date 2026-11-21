# OfferCheck — Verify job & internship offers with live You.com evidence

> A company can be real. Its job offer can still be fake.

OfferCheck helps students and freelancers investigate job, internship, and freelance offers. It compares specific offer claims with live public sources and shows what it could confirm and what remains uncertain.

## What it does

- **Rule-based verdicts:** flags candidate fees, recruiter/domain mismatches, and other concrete signals; the model never chooses the verdict.
- **Live citations:** searches You.com and links claims only to URLs returned by the Search API.
- **English and Hinglish:** review reports in either language.
- **Screenshots and files:** share a screen, paste/drop an image, or upload PDF/`.eml`; extraction keeps offer content and ignores unrelated page text.
- **Gmail:** optional read-only OAuth, recent job-email picker, and `.eml` header checks.
- **Resilient demos:** cached preset responses cover temporary model failures such as HTTP 429, 503, or timeouts; the UI labels cached results.

## How it works

```text
Offer text / file / selected email
        ↓
Offer-only extraction → claim extraction
        ↓
Parallel You.com Search API queries → deduplicated, URL-whitelisted evidence
        ↓
Deterministic rules → verdict and claim ledger
        ↓
Gemini/Groq report wording → SSE progress and cited report
```

**Stack:** Python + FastAPI, You.com Search API, Gemini Vision, Groq/Gemini text generation, Server-Sent Events (SSE), and vanilla HTML/CSS/JavaScript.

## Run locally

Run from the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pip install -r requirements.txt
Set-Location ..
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Fill in the needed values in `.env` (never commit this file):

- `YOU_API_KEY` — required for live search/citations.
- `GEMINI_API_KEY`, or separate `VISION_API_KEY` and `ANALYZE_API_KEY`. Image OCR needs a Gemini Vision key.
- Optional `GROQ_API_KEY` and `GROQ_MODEL` for text calls/fallback. `EXTRACT_MODEL` and `ANALYZE_MODEL` select Gemini models.
- Optional Gmail OAuth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`. The app creates `SESSION_SECRET` in `.env` if it is missing or empty.

Start the app from the repository root:

```powershell
python -m uvicorn app:app --app-dir backend --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Run the offline checks in another terminal:

```powershell
python backend\test_fixtures.py
python backend\test_gmail_oauth.py
node --check frontend\app.js
```

## Connect Gmail (optional)

Enable the Gmail API in Google Cloud, configure the OAuth consent screen, and add your account as a test user. Create a **Web application** OAuth client and register this authorized redirect URI exactly:

```text
http://127.0.0.1:8000/auth/google/callback
```

Put the client ID and secret in local `.env`, restart OfferCheck, then click **Connect Gmail** and approve read-only access. Choose an email to load it into the offer box; review it before clicking **Check this offer**. OAuth tokens stay in process memory, are not written to files or logs, and must be reauthorized after the server restarts. Disconnect clears the local session.

## Demo notes and limitations

- Built-in examples are fictional impersonation scenarios; they are not claims about Infosys or another company.
- Cached demo evidence can be older than live search results and is labeled in the UI. User-entered offers are not cached.
- `NO RED FLAGS FOUND` is not a guarantee. A lack of evidence means **UNVERIFIED**, not proof of fraud or authenticity.
- Live results need internet access and valid provider credentials. Gmail also needs a configured Google Cloud OAuth client and enabled Gmail API.
- Offer text and selected email content are sent to configured providers for analysis. Submitted offers and Gmail tokens are not persisted by the app; in-memory jobs and sessions are lost when the server stops.
- OfferCheck is an evidence aid, not a legal or financial guarantee. Verify important claims with the employer through contact details from its official site.
