# OfferCheck UI: design direction + image prompts (paste into ChatGPT)

## How to use
1. Open ChatGPT image generation. For EACH section below: paste the GLOBAL STYLE block first, then that section's prompt, in the same message.
2. Generate one image per section. If the text in the image is garbled, regenerate ONCE. Do not spend more than one round on this. The image is only a visual target. The real UI is code.
3. Save images as `01-home.png`, `02-investigating.png`, ... (numbers match sections below) and send them back here (or to Gemini). Sections 1 to 8 are required. Sections 9 and 10 (other verdict states) are optional but recommended, put them in `ui-mockups/` too.
4. Then Claude/Gemini turns them into code (HTML/React) that you run in VS Code.

## UI direction (what it should feel like)
- Calm and trustworthy, like a banking app plus a clean notes app. Not a hacker dashboard, not purple AI gradients.
- Mobile first (students use phone and WhatsApp). Desktop adds a split view: offer on the left, evidence on the right.
- The user must get the answer in 3 seconds: a big verdict, one line, then "Do this now". Details are below, for people who want proof.
- Every claim has a colored status and a small source chip that opens the source.
- Three status colors only: red = contradicted, amber = could not confirm, green = confirmed.

## Fixed sample content (use exactly this in all images so they match)
Fictional company: **Northgate Technologies**.

Pasted offer:
"Congratulations! You are selected for Remote AI Internship at Northgate Technologies. Stipend Rs 45,000/month. No interview needed. Pay registration fee Rs 1,999 (refundable) today to confirm your seat. Contact HR Rohit on WhatsApp. Mail: northgate.hr.careers@gmail.com"

Verdict: HIGH RISK
Headline: "Do not pay. This offer looks fake."
Summary: "The company's own site says it never asks for money. We could not confirm the recruiter."

Claims:
1. "Pay Rs 1,999 registration fee" | CONTRADICTED | "Northgate's own page says it never asks candidates for money." | source: northgate.com/fraud-alert (Official)
2. "Recruiter emails from Gmail" | CONTRADICTED | "Northgate emails come from @northgate.com, not Gmail." | source: northgate.com/careers (Official)
3. "Remote AI Internship" | UNVERIFIED | "No matching role on Northgate's careers page." | source: northgate.com/careers (Official)
4. "HR Rohit works at Northgate" | UNVERIFIED | "We could not confirm this person works there." | no source
5. "Stipend Rs 45,000/month" | UNVERIFIED | "We found no pay details for this role." | no source
6. "Northgate Technologies" | CONFIRMED | "The company is real." | source: Business news article (News)

Do this now: "Do not pay anything." / "Email Northgate using the address on northgate.com." / "Block the number and report it on cybercrime.gov.in."
Cannot verify: "Who Rohit really is" / "If this role exists" / "The stipend amount"
Ask them: "Can you email me from an @northgate.com address?" / "What is the job ID on the careers page?"

Sources list: northgate.com/fraud-alert (Official), northgate.com/careers (Official), Business news article (News), Reddit thread about fake internship offers (Forum)

---

## GLOBAL STYLE (paste before every section prompt)

```
Create a clean, modern web app UI mockup as a flat screenshot (not a photo of a device, no device frame). Light theme, calm and trustworthy, like a mix of a banking app and a good notes app. Background off-white #F7F7F5. White cards with 12px rounded corners and thin light grey borders. Dark ink text #1A1A1A. One accent color deep blue #2F5BEA. Status colors: red #D93025 (contradicted), amber #E8A200 (could not confirm), green #1E8E3E (confirmed), grey #6B7280 for secondary text. Font: Inter. Large readable text, generous spacing. No gradients, no neon, no glassmorphism, no 3D, no stock illustrations, no dark hacker look. All text must be sharp, correctly spelled and readable. Use exactly the sample text I give. Product name: OfferCheck.
```

---

## Section 1: Home / input (desktop, 1440x900)

```
Desktop screen 1440x900. Top bar: "OfferCheck" logo text on the left, small link "How it works" on the right. Center: headline "A company can be real. Its job offer can still be fake." and one grey line below: "Paste an offer. We check it against live sources and show proof."
Below: a large white input card with a big text area containing this pasted text: "Congratulations! You are selected for Remote AI Internship at Northgate Technologies. Stipend Rs 45,000/month. No interview needed. Pay registration fee Rs 1,999 (refundable) today to confirm your seat. Contact HR Rohit on WhatsApp. Mail: northgate.hr.careers@gmail.com"
Under the text area, a row of 3 outlined buttons with simple line icons: "Paste screenshot", "Upload file", "Connect Gmail". On the right of that row, a solid blue button "Check this offer".
Below the card, a row of small chips: "Try an example: Fake fee offer", "Fake WhatsApp job", "Real offer". Footer small grey text: "We never say safe. We only say what we could confirm."
```

## Section 2: Investigating (live progress, desktop 1440x900)

```
Desktop screen 1440x900, same top bar. Two columns. Left column: the pasted offer text in a white card (same sample text), slightly dimmed. Right column: a white card titled "Checking this offer" with a vertical list of 5 steps, each with a status icon: "Reading the offer" (green check), "Finding Northgate's official site and careers page" (green check), "Looking for Northgate's fraud warning page" (blue spinner, in progress), "Searching scam reports" (grey, waiting), "Writing your result" (grey, waiting). Under each finished step a small grey line showing what was searched, for example: Searched: "Northgate Technologies careers". At the bottom a thin blue progress bar at 60 percent.
```

## Section 3: Result top: verdict card (desktop 1440x900)

```
Desktop screen 1440x900, same top bar. At the top of the page, a wide white card with a thick red left border. Inside: a red pill badge "HIGH RISK". Large bold headline: "Do not pay. This offer looks fake." Under it, one grey line: "The company's own site says it never asks for money. We could not confirm the recruiter." On the right inside the card, two buttons: solid blue "Do this now" and outlined "Share result". Below the card, a faint hint of the next section (a card titled "What we checked") so the page looks scrollable. Keep it airy and calm, not alarming or flashy.
```

## Section 4: Result: claim ledger with offer on the left (desktop 1440x900)

```
Desktop screen 1440x900, two columns under a small verdict strip "HIGH RISK" at the top. Left column (40%): a white card titled "Your offer" with the offer text and parts highlighted: "registration fee Rs 1,999" highlighted red, "northgate.hr.careers@gmail.com" highlighted red, "Remote AI Internship" highlighted amber, "HR Rohit" highlighted amber, "Rs 45,000/month" highlighted amber, "Northgate Technologies" highlighted green. Right column (60%): a white card titled "What we checked" with 6 rows. Each row: a colored status dot/icon and label (red "Contradicted", amber "Could not confirm", green "Confirmed"), the claim in bold, one short grey reason line, and small rounded source chips such as "northgate.com/fraud-alert · Official". Rows in this order, with this exact text:
1 red: Pay Rs 1,999 registration fee. "Northgate's own page says it never asks candidates for money." chip: northgate.com/fraud-alert · Official
2 red: Recruiter emails from Gmail. "Northgate emails come from @northgate.com, not Gmail." chip: northgate.com/careers · Official
3 amber: Remote AI Internship. "No matching role on Northgate's careers page." chip: northgate.com/careers · Official
4 amber: HR Rohit works at Northgate. "We could not confirm this person works there."
5 amber: Stipend Rs 45,000/month. "We found no pay details for this role."
6 green: Northgate Technologies. "The company is real." chip: Business news · News
```

## Section 5: Action card: do this, cannot verify, ask them (desktop 1440x900)

```
Desktop screen 1440x900, same top bar and small verdict strip. Three white cards side by side. Card 1 titled "Do this now" with 3 numbered steps: "1. Do not pay anything." "2. Email Northgate using the address on northgate.com." "3. Block the number and report it on cybercrime.gov.in." Card 2 titled "We could not confirm" with 3 amber bullet items: "Who Rohit really is", "If this role exists", "The stipend amount". Card 3 titled "Ask the recruiter" with 2 short questions in light grey boxes: "Can you email me from an @northgate.com address?" and "What is the job ID on the careers page?" Each box has a small "Copy" button. Under card 3 a note in small grey text: "A real recruiter will not mind these questions."
```

## Section 6: Sources drawer (desktop 1440x900)

```
Desktop screen 1440x900. Main page dimmed in the background. A white side drawer slides in from the right (width about 480px), titled "Sources we used" with a close X. Inside: 4 source cards stacked. Each shows: a small tag (Official, Official, News, Forum), page title, domain in grey, a 2 line snippet in grey, "Checked today, 10:42 AM", and an "Open source" link. Items: "Northgate fraud alert" (northgate.com/fraud-alert, Official), "Careers at Northgate" (northgate.com/careers, Official), "Northgate opens new office" (Business news, News), "Fake internship offers, beware" (Reddit thread, Forum). At the bottom of the drawer small grey text: "A source supports one claim. It does not prove everything else."
```

## Section 7: Upload + Gmail picker (desktop 1440x900)

```
Desktop screen 1440x900, home screen dimmed behind. A centered white modal titled "Add your offer" with two tabs: "Upload" (active) and "Gmail". Upload tab: a large dashed drop area with the text "Drop a screenshot, PDF or .eml file here, or paste with Ctrl+V" and small grey text "Images, PDF, .eml. Max 10 MB. We delete files after checking." Show one uploaded thumbnail file named "whatsapp-offer.png" with a small remove X. Below, a faint preview of the Gmail tab content: a list of 3 emails each with sender, subject and a "Check" button: "Northgate HR · Internship Selection Letter", "Talent Team · Congratulations on your offer", "Hiring Desk · Final step: confirm your seat". Small grey note: "We only read the email you pick. Read-only access."
```

## Section 8: Mobile home and mobile result (two screens in one image, each 390x844)

```
Two mobile app screens side by side, each 390x844, flat screenshots with no phone frame. Left screen (Home): "OfferCheck" at top, headline "A company can be real. Its job offer can still be fake." large text area with the sample offer text, three small buttons "Paste screenshot", "Upload", "Gmail", and a full-width solid blue button "Check this offer". Right screen (Result): a red pill "HIGH RISK", big headline "Do not pay. This offer looks fake.", one grey summary line, then a card "Do this now" with 3 numbered steps, then the first two claim rows (red "Pay Rs 1,999 registration fee" and red "Recruiter emails from Gmail") with source chips, and a text link "See all 6 checks". Thumb-friendly spacing, large tap targets.
```

---

## Section 9: Result: "could not verify" state (desktop 1440x900)

```
Desktop screen 1440x900, same top bar. Wide white verdict card with a thick amber left border. Amber pill badge "COULD NOT VERIFY". Large bold headline: "We could not confirm this offer." One grey line: "This is a small company with few public sources. That does not mean it is fake." On the right, solid blue button "Do this now". Below the card, a card "What we checked" with 4 rows, all amber "Could not confirm" except one green "Confirmed": green "Riverbend Software, a company page exists", amber "Remote Data Intern role", amber "Recruiter Priya works there", amber "Stipend Rs 12,000/month". Sources chips only where there is a source, otherwise a small grey text "No source found". Calm, not alarming.
```

## Section 10: Result: "no red flags found" state (desktop 1440x900)

```
Desktop screen 1440x900, same top bar. Wide white verdict card with a thick blue (#2F5BEA) left border. Blue pill badge "NO RED FLAGS FOUND". Large bold headline: "This offer matches the company's careers page." One grey line: "We found no red flags. Still confirm the recruiter before sharing documents." A small grey note inside the card: "Not a guarantee." Do NOT use green for the verdict and do not use the word safe anywhere. Below, a card "What we checked" with 4 rows: green "Confirmed" Riverbend Software is a real company (chip: riverbend.example/about, Official), green "Confirmed" role listed on the careers page (chip: riverbend.example/careers, Official), green "Confirmed" no fee asked, amber "Could not confirm" Recruiter Priya works there.
```

Label rule for ALL images: status words are "Confirmed", "Contradicted", "Could not confirm". Verdict words are "HIGH RISK", "COULD NOT VERIFY", "NO RED FLAGS FOUND".
Note: the "Share result" button copies a short text summary (link/PDF sharing is a later feature).

---

## After images are made (for Claude/Gemini)
- Build with plain HTML/CSS/JS (decided in task.md, no build step). Use the colors and spacing from the GLOBAL STYLE block as CSS variables.
- Layout: mobile single column; at 900px and wider use the split view from section 4.
- Data comes from the report JSON (data contract in task.md, writer rules in report_system_prompt.md). UI must support all 3 verdict states. The verdict badge comes from `verdict_level`, never from model text.
- Do not add anything that is not in the images unless the images are missing a state (empty, error, loading).