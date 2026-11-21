# HANDOFF: Beyond 9TO5 Buildathon (Aryan, solo + AI teammates)

Last updated by: Claude (full audit, 2026-11-21). Next owner: Gemini (or Claude again).
IMPORTANT: task.md is the only task list and progress log. This file is context and decisions. Where this file and task.md disagree, task.md wins. Sections 2 to 7 below are the ORIGINAL plan; section 13 lists what changed.

## 0. How to talk to Aryan
- Casual, direct, Hinglish. He says "bro". Match tone.
- No over-explaining, no fluff. If an idea or code is weak, say so and say why.
- Reality-check everything against what judges and the real world will see.

## 1. Context
- Event: Beyond 9TO5 Buildathon (Bengaluru). Solo participant: Aryan.
- Chosen track: **Track 2, You.com** (live, cited web data). Build an agent/app/integration that uses You.com APIs to give citation-backed answers.
- Docs: https://you.com/docs
- Judging criteria: UNKNOWN (ask Aryan). Time left: UNKNOWN (ask Aryan).
- Risk already identified: generic "research assistant" will be built by many teams. Must be a sharp niche with a clear decision.

## 2. The idea (working name: OfferCheck)
**One line:** Paste a job/internship/freelance offer, get a cited verdict on whether it is legit or a scam, plus what to ask before you accept or pay.

**User:** Indian students and freelancers (the "beyond 9 to 5" crowd) who get offers on WhatsApp, LinkedIn, Telegram, email.
**Decision it helps with:** "Should I reply, share documents, pay a registration/training fee, or accept?"

**Why it fits Track 2:** the product IS live web evidence with citations. Without citations the verdict is worthless, so the sponsor API is the core, not a side feature.

**Core rule:** every claim in the report must carry a source link. If no evidence is found, output "UNVERIFIED", never "SAFE". Absence of a web footprint means "could not verify", NOT "scam" (small startups are real). Only active red flags (fee asked, impersonation, contradiction with the company's own page) make a result HIGH RISK.

### Input
- Raw offer text (WhatsApp/email paste). Optional: company name, recruiter name, email/domain, website URL.

### Pipeline
1. Extract entities with an LLM: company, recruiter, domain/email, role, pay, any money asked from candidate, urgency language.
2. Run targeted You.com searches (live, cited):
   - Company exists? official site, LinkedIn page, news, registration mentions
   - Complaints/scam reports: "<company> scam", "<company> fake internship", reviews, forums
   - The pattern: "registration fee / security deposit / training fee for job" known scam patterns
   - Pay benchmark: typical stipend/rate for that role in India
3. LLM synthesizes a report using ONLY retrieved snippets (no invented facts).
4. Output (UPDATED): verdict HIGH_RISK / UNVERIFIED / NO_RED_FLAGS_FOUND (no Low/Medium tiers), claim ledger with a citation per claim, things we could not confirm, do-this steps, questions to ask. Exact JSON shape is in task.md (data contract).

### Demo flow (must work in 30 seconds)
Paste a fake "pay Rs 2999 registration fee, get 40k/month work from home" offer -> High risk with cited evidence -> then paste a real company offer -> shows verified signals with sources. Two contrasting examples = strong demo.

## 3. Stack (keep it boring, solo-friendly)
- Backend: Python + FastAPI (single service).
- LLM: any (Claude or Gemini API) used for entity extraction and report writing.
- Search: You.com API (verify exact endpoint/params in the docs before coding; do not guess).
- Frontend: DECIDED plain HTML/CSS/JS served by FastAPI (see task.md). Mobile first.
- Deploy: whatever is fastest (Render/Vercel/HF Space). Local demo is acceptable if deploy fails.

## 4. Plan (ORIGINAL, SUPERSEDED by the phases in task.md. Kept for history)
| Block | Goal | Owner |
|---|---|---|
| H0 to H1 | Lock idea (see section 6), read You.com docs, one working API call that returns cited results | Aryan + Claude |
| H1 to H3 | Backend pipeline: extract entities -> searches -> synthesize report with citations | Claude (arch + core), Gemini (helpers/tests) |
| H3 to H5 | UI: input, loading state, report with clickable citations, risk badge | Gemini |
| H5 to H6 | Prepare 3 demo offers (1 obvious scam, 1 subtle scam, 1 legit). Test and fix | Aryan |
| Last 1 to 2h | README, 2 min demo video/script, submission form, freeze code | Aryan |

Old cut list (superseded; screenshot input is now P0). Use the priority tags and cut order in task.md.

## 5. Task split between AIs (see owner tags in task.md)
- Claude: architecture, prompts, backend core, reviewing risky logic.
- Gemini: UI, test cases, README, demo script, fixing bugs from the status log.
- Rule: whoever stops must update section 7 so the next one never starts blind.

## 6. Idea validation (DONE, results in section 9)
| AI | Verdict | Main point |
|---|---|---|
| ChatGPT | YES 7.5/10 | Real problem, weak differentiation. Build an evidence investigation, not a classifier |
| Kimi | NO 5.5/10 | Obvious idea. Lead with evidence, impersonation demo, domain check |
| Gemini | NO 5.5/10 | Thin wrapper risk. Show claim to citation traceability, live steps |

Decision rule: if most say NO for the same reason, fix that reason or switch to the backup idea. Note: AIs share similar training, so unanimous YES is weak proof. Judge by specific criticisms, not vote count.

Backup idea: "Rate Reality" agent that takes a freelancer's skill + city and returns cited live demand, going rates and client sources, then recommends a pricing decision. More generic, use only if OfferCheck fails validation.

## 7. STATUS LOG (ORIGINAL, SUPERSEDED: track progress with the checkboxes and Progress log in task.md)
- [x] Idea locked (OfferCheck, reframed, see section 9)
- [ ] You.com API key obtained and test call working
- [ ] Entity extraction working
- [ ] Search + citation pipeline working
- [ ] Report generation (no uncited claims)
- [ ] UI
- [ ] Demo cases tested
- [ ] README + demo video
- [ ] Submitted

Last action: validation done (ChatGPT YES 7.5, Kimi NO 5.5, Gemini NO 5.5), idea LOCKED with reframe, see section 9.
Blockers: judging criteria and deadline not known yet.
Next action: H0 to H1 block: You.com API key + one working cited search call. NO more idea validation or pivots.

## 8. Known risks
- Fake companies may have almost no web footprint: handle with UNVERIFIED, do not call them safe.
- LLM may hallucinate sources: only cite URLs actually returned by the search API.
- Defamation/overclaiming: phrase as "signals found" with sources, not "this company is a scam".
- Existing scam checkers exist (general website scam checkers). Our edge: offer-specific, India-focused, cited evidence plus next-step questions.


## 9. Validation results and LOCKED decisions (final, do not reopen)
Votes: ChatGPT YES 7.5/10, Kimi NO 5.5/10, Gemini NO 5.5/10. All three agree on the same thing: problem is real, but a plain "paste offer -> risk score" is an obvious wrapper. Fix = differentiation in evidence and demo, not a pivot.

### New central promise
"A company can be real. Its job offer can still be fake." An investigation agent that tells you what it could PROVE and what it could NOT, with a source for each.

### Locked design changes
1. Claim ledger: split the offer into atomic claims (company, recruiter affiliation, vacancy exists, fee asked, pay, email domain). Each claim is classified SUPPORTED / CONTRADICTED / UNVERIFIED with citation. This replaces the vibe-based risk score as the main output.
2. Verdict is derived by deterministic rules, LLM only explains. Critical: upfront fee, OTP/bank request. High: free-mail recruiter claiming big company, lookalike domain, no matching vacancy on official careers page. Company existing = limited positive evidence only.
3. Separate "company exists" from "this recruiter/offer is authentic". Never treat a citation as proof of identity.
4. Main demo case = impersonation: real big company (data-rich, so search works), fake recruiter/offer. Second demo = legit offer. Third = tiny/no-footprint company shows UNVERIFIED with "what to do next" (call the number on the official site, not the one in the message).
5. UI: left = pasted offer with claims highlighted, right = claim vs live citation. Show live search steps and the exact queries used (auditable).
6. Safety: pasted text is untrusted data (prompt injection). Wording is "signals found / could not verify", never "this company is a scam". Only cite URLs actually returned by the API.
7. Indian scam patterns first: registration/security/training/laptop fees, UPI to personal number, Telegram task scams, fake internship certificates.
8. Handle Hinglish/informal WhatsApp text in the parser.

### Reality notes
- Domain age/WHOIS is NOT a You.com feature. Optional extra via a free RDAP lookup only if core is done. Do not make it a dependency.
- Recruiter LinkedIn cross-check: cannot scrape LinkedIn. Only report what search results show; else UNVERIFIED.
- Closest competitor named by ChatGPT: JobAthlete fake-job checker. Aryan to look at it for 5 minutes max, then move on.
- Rejected pivots: ForwardCheck (viral forwards) and ClaimLedger as a general fact-checker. Too much scope for solo. Their ideas absorbed only where listed above.

### Cut list (in order)
draft reply modes -> questions-to-ask -> shareable report link -> Low/Medium tiers (keep Evidence Found vs Unverified vs High risk) -> any extra UI polish.
Never cut: claim ledger with citations, rule-based verdict, UNVERIFIED logic, impersonation demo.

## 10. Pitch sharpening (Aryan said the idea looks generic)
Decision: do NOT switch ideas. Sharpen the hook instead.
- New hook: "The company itself tells you this offer is fake." The agent finds the impersonated company's OWN recruitment-fraud notice and official careers page via You.com and uses them as cited evidence against the offer's claims (e.g. offer asks a fee, company's official page says it never charges candidates; offered role not listed on official careers page).
- Evidence sources to retrieve per offer: (1) company's official fraud/recruitment-scam notice, (2) official careers page listing for the claimed role, (3) independent scam reports, (4) company registration/news.
- Claims map to evidence in the claim ledger: SUPPORTED / CONTRADICTED / UNVERIFIED, each with a source link.
- If a company has no published fraud notice, say so (UNVERIFIED), do not invent one.
- Demo: pick a big Indian/global company that publishes such a notice, verify live before the demo that the page exists.

## 11. Scope update: inputs (Aryan asked for Gmail connect, browser screenshots, media upload)
- Full architecture, phased tasks and post-build backlog live in task.md. Follow task.md for what to do next.
- Decision: screenshot paste/drag-drop + image/PDF upload are P0/P1 (cheap with a vision LLM). `.eml` upload is P1 and is the Gmail fallback. Real Gmail OAuth is P2, only after the core demo works.
- Reason: Gmail OAuth is the most time-expensive input and is not what wins the track. Citations and the claim ledger are.

## 12. Report writing and UI direction
- Report writer rules (short, simple words, JSON output, backend checks): report_system_prompt.md.
- UI direction and per-section image prompts (Aryan generates mockups in ChatGPT, one round only): ui_image_prompts.md. Build the real UI from those images, mobile first.
- Language option: simple_english or hinglish (students read on phones, in a hurry).

## 13. Audit fixes (2026-11-21) and current state
Changed after re-checking everything discussed:
1. Verdict values are now HIGH_RISK / UNVERIFIED / NO_RED_FLAGS_FOUND. UI never says "safe". "No red flags" is shown in blue with a "not a guarantee" note.
2. Absence of web footprint is NOT a risk signal (fixed in section 2).
3. Next-step advice (helpline, "do not pay") comes from a static library in code, not from the LLM, so nothing is invented.
4. UI is plain HTML/CSS/JS served by FastAPI. UI and backend share one JSON data contract (task.md), so they can be built in parallel. UI is built from mock data first.
5. Project folder is `offerchecker` with docs/ inside. Pointer files (CLAUDE.md, GEMINI.md, AGENTS.md, copilot-instructions) tell any AI to read docs/HANDOFF.md and docs/task.md first.
6. Build starts in two stages: Stage 1 setup only, Stage 2 real build only after Aryan writes START BUILD (after checking hackathon rules on pre-written code).
7. Models are split by step (extract / classify / write) with env vars. See task.md section 5.
8. Still NOT written: claim extractor prompt and claim classifier prompt (task 0.6).
9. Still UNKNOWN: hackathon hours, judging criteria, pre-written-code policy, You.com credits (task.md section 3b).

Current state: planning. No product code written. Next: 0.11 to 0.12 in task.md.