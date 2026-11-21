# OfferCheck

**Real-time job, internship & freelance offer verification powered by live You.com evidence.**

## The problem

Scams can borrow a real company’s name and look convincing. Candidates face impersonated recruiters, advance-fee traps, WhatsApp/Hinglish pitches, and spoofed email addresses.

## The solution

OfferCheck extracts offer claims, checks companies, recruiters, and domains against live You.com search results, and inspects available email headers for SPF, DKIM, and Reply-To signals. A deterministic rule engine—not the language model—decides the verdict. The UI reports **HIGH RISK**, **COULD NOT VERIFY**, or **NO RED FLAGS FOUND**. The last label is not a guarantee of safety; a company with no verifiable footprint is not marked safe.

## What makes it different

- **Evidence-bound citations:** the claim ledger links only to URLs returned by You.com. Missing evidence stays unverified.
- **Rules plus extraction:** deterministic fee and domain-mismatch rules work alongside LLM extraction for Hinglish and WhatsApp-style offers, advance-fee patterns, and free-email versus official-domain mismatches.
- **Multiple inputs:** paste text, share a browser tab/window/screen, paste or drop an image, upload a PDF or `.eml`, or connect Gmail with read-only OAuth.
- **Email signals:** `.eml` and imported Gmail messages can be checked for SPF, DKIM, and Reply-To mismatches.
- **Provider resilience:** Gemini Vision handles image extraction; Groq and Gemini provide configurable text generation and fallback. SSE streams progress to the UI.

## System architecture

```text
Input [Text / Share Screen / Upload / Gmail]
                    |
                    v
        Claim & Header Extractor
                    |
          +---------+----------+
          |                    |
          v                    v
 Deterministic Risk Rules   Live You.com Search
          |                    |
          +---------+----------+
                    v
       Citation & Verdict Ledger
                    |
                    v
              SSE Web UI
```

## Features and guardrails

- Rule-based risk verdicts; the LLM extracts claims and helps write the explanation, but never chooses the verdict.
- Live evidence is separated from unsupported claims, with source links restricted to actual search results.
- Offer-only extraction ignores unrelated page chrome in screenshots and documents; non-offer files get a clear rejection.
- English and Hinglish reports, demo presets, cached demo fallbacks, and live SSE progress.
- Gmail access is read-only. OAuth tokens are held in process memory, not written to files; sessions are lost when the server restarts.
- OfferCheck is an evidence aid, not legal or financial advice. Verify important claims using contact details from the employer’s official website.

## Try the app

1. Start OfferCheck using the setup below and open [http://127.0.0.1:8000](http://127.0.0.1:8000).
2. Try a built-in preset, or paste a job, internship, or freelance offer and select **Check this offer**.
3. Use **Share screen** to select a tab, window, or screen; alternatively paste/drop an image or upload a PDF.
4. Upload an `.eml` file to inspect its message body and headers.
5. To try Gmail, configure Google OAuth below, select **Connect Gmail**, approve read-only access, and choose a recent matching message.

The included demo offers are fictional impersonation scenarios, not claims about the named companies. Cached demo evidence may be older than live results and is labeled. **NO RED FLAGS FOUND** does not establish that an offer is genuine.

## Developer setup

**Prerequisites:** Python 3.10+, Node.js for the JavaScript syntax check, and provider credentials for live search/model calls.

```powershell
git clone https://github.com/aryantyagi2211/OfferChecking.git
Set-Location OfferChecking
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Set-Location backend
python -m pip install -r requirements.txt
Set-Location ..
Copy-Item .env.example .env
```

Add credentials to the local `.env` file; never commit it. **Only `YOU_API_KEY` is required for live search.** Gemini text/image features and Gmail are optional and need their corresponding credentials.

| `.env` variable | Purpose |
| --- | --- |
| `YOU_API_KEY` | You.com Search API key for live evidence and citations. |
| `GEMINI_API_KEY` | Shared Gemini key fallback for vision and analysis. |
| `VISION_API_KEY` | Preferred Gemini Vision key. |
| `GEMINI_VISION_API_KEY` | Alternate Gemini Vision key name. |
| `ANALYZE_API_KEY` | Preferred Gemini text-analysis key. |
| `GEMINI_ANALYZE_API_KEY` | Alternate Gemini analysis key name. |
| `EXTRACT_MODEL` | Gemini extraction model; sample default is `gemini-2.5-flash-lite`. |
| `ANALYZE_MODEL` | Gemini analysis model; sample default is `gemini-2.5-flash`. |
| `GROQ_API_KEY` | Optional Groq text-generation provider key. |
| `GROQ_MODEL` | Groq model; sample default is `openai/gpt-oss-20b`. |
| `SESSION_SECRET` | Signs local Gmail session/state cookies; generated by the app if empty. |
| `GOOGLE_CLIENT_ID` | Optional Google OAuth client ID for Gmail. |
| `GOOGLE_CLIENT_SECRET` | Optional Google OAuth client secret for Gmail. |
| `GOOGLE_REDIRECT_URI` | OAuth callback URI; default is `http://127.0.0.1:8000/auth/google/callback`. |

For Gmail, enable the Gmail API in Google Cloud, configure the OAuth consent screen, and add your account as a test user. Create a Web application OAuth client and register the redirect URI above. The app requests only `gmail.readonly`.

Run the app from the repository root:

```powershell
python -m uvicorn app:app --app-dir backend --reload
```

### API overview

| Endpoint | Purpose |
| --- | --- |
| `POST /analyze` | Submit offer text, an image/PDF/`.eml`, or a selected Gmail message. |
| `GET /stream/{job_id}` | Receive live analysis steps and the final report via SSE. |
| `GET /auth/google/start` | Begin Gmail OAuth. |
| `GET /auth/google/callback` | Complete the OAuth flow. |
| `GET /api/gmail/status` | Check whether Gmail is configured and connected. |
| `GET /api/gmail/messages` | List recent job-related messages. |
| `POST /api/gmail/disconnect` | Disconnect the local Gmail session. |

### Tests

From the repository root:

```powershell
python backend\test_fixtures.py
python backend\test_gmail_oauth.py
node --check frontend\app.js
```

## Stack

FastAPI · Server-Sent Events · You.com Search API · Gemini Vision · Groq/Gemini text generation · vanilla HTML, CSS, and JavaScript.
