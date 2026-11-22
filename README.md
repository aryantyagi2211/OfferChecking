# OfferCheck

**Real-time job, internship & freelance offer verification powered by live You.com evidence.**
**Live App:** [https://offercheck-lfok.onrender.com/](https://offercheck-lfok.onrender.com/)
## The problem

Scams can borrow a real company’s name and look convincing. Candidates face impersonated recruiters, advance-fee traps, WhatsApp/Hinglish pitches, and spoofed email addresses.

## Pitch & Product Showcase

### Slides 1–4

| Slide 1 | Slide 2 |
| --- | --- |
| <img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0001.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0001.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0001.jpg` | <img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0002.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0002.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0002.jpg` |
| **Slide 3**<br><img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0003.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0003.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0003.jpg` | **Slide 4**<br><img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0004.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0004.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0004.jpg` |

<details>
<summary>Slides 5–9</summary>

| Slide 5 | Slide 6 |
| --- | --- |
| <img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0005.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0005.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0005.jpg` | <img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0006.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0006.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0006.jpg` |
| **Slide 7**<br><img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0007.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0007.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0007.jpg` | **Slide 8**<br><img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0008.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0008.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0008.jpg` |
| **Slide 9**<br><img src="assets/OfferCheck%20%E2%80%94%20Real-Time%20Job%20Scam%20Verification_page-0009.jpg" alt="OfferCheck — Real-Time Job Scam Verification_page-0009.jpg" width="100%"><br>`OfferCheck — Real-Time Job Scam Verification_page-0009.jpg` | |

</details>

## The solution

OfferCheck extracts offer claims, checks companies, recruiters, and domains against live You.com search results, and inspects available email headers for SPF, DKIM, and Reply-To signals. A deterministic rule engine—not the language model—decides the verdict. The UI reports **HIGH RISK**, **COULD NOT VERIFY**, or **NO RED FLAGS FOUND**. The last label is not a guarantee of safety; a company with no verifiable footprint is not marked safe.

## What makes it different

- **Zero-hallucination citation ledger:** links only to URLs returned by You.com; missing evidence stays unverified.
- **Rules plus extraction:** deterministic fee and domain-mismatch rules work alongside LLM extraction for Hinglish and WhatsApp-style offers, advance-fee patterns, and free-email versus official-domain mismatches.
- **Language support:** analyze offers and read reports in English or Hinglish.

## System architecture

```text
 Text / Preset / Share Screen / File / Gmail
                    |
                    v
     Offer + Email Header Extraction
                    |
          +---------+----------+
          |                    |
          v                    v
 Deterministic Risk Rules   You.com Search
          |                 (live sources)
          +---------+----------+
                    v
       Evidence & Verdict Ledger
                    |
          Report wording + SSE
                    |
                    v
        Responsive Light-theme UI
```

## Features and guardrails

- **Text and presets:** paste an offer or use a fictional demo offer to see the analysis flow.
- **Share screen and files:** share a tab, window, or screen; paste/drop an image; or upload PDF/`.eml`. Vision and file extraction focus on job, internship, and freelance offer content, rejecting unrelated material.
- **Gmail:** read-only OAuth picker returns up to the 10 most recent matching offer emails. Imported text is cleaned and formatted; SPF, DKIM, and Reply-To checks use the fetched original headers.
- **Providers and progress:** Gemini Vision extracts image text. Configured Groq and Gemini text providers provide fallback for temporary errors such as rate limits/timeouts; SSE streams analysis progress.
- **Responsive UI:** a polished light theme presents the verdict, claim ledger, sources, and next-step actions on desktop and mobile.
- The LLM extracts claims and helps write explanations; it never chooses the verdict. Unsupported claims stay unverified, and zero-footprint companies are never marked safe.
- Gmail OAuth tokens are held in process memory, not written to files; sessions are lost when the server restarts.
- OfferCheck is an evidence aid, not legal or financial advice. Verify important claims using contact details from the employer’s official website.

## Try the app

1. Start OfferCheck using the setup below and open [http://127.0.0.1:8000](http://127.0.0.1:8000).
2. Try a built-in preset, or paste a job, internship, or freelance offer and select **Check this offer**.
3. Use **Share screen** to select a tab, window, or screen; alternatively paste/drop an image or upload a PDF. Unrelated page text is not added as an offer.
4. Upload an `.eml` file to inspect its cleaned offer text and sender-authentication headers.
5. To try Gmail, configure Google OAuth below, select **Connect Gmail**, approve read-only access, and choose one of up to 10 recent matching messages.

The included demo offers are fictional impersonation scenarios, not claims about the named companies. Cached demo evidence may be older than live results and is labeled. **NO RED FLAGS FOUND** does not establish that an offer is genuine.

## Developer setup

**Prerequisites:** Python 3.10+, Node.js for the JavaScript syntax check, and provider credentials for live search/model calls.

```powershell
git clone https://github.com/aryantyagi2211/OfferChecking.git
Set-Location OfferChecking
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
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
Google OAuth credentials can also be supplied as a `client_secret.json` in `backend/`, the repository root, or `/etc/secrets/`.

Run the app from the repository root:

```powershell
python -m uvicorn app:app --app-dir backend --reload
```

For Render, use `pip install -r requirements.txt` as the build command and:

```text
uvicorn backend.app:app --host 0.0.0.0 --port $PORT --workers 1
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
