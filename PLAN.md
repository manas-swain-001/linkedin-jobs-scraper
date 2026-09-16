# LinkedIn Recruiter Post Scraper + AI Auto-Mailer

## Purpose

Collect recruiter job posts from LinkedIn (Full Stack / React / Node search), extract the contact info from each post (email first, phone as fallback), then automatically write a short, professional, **tailored** email for each recruiter using Gemini AI — matching the *specific* requirements each post asks for — and send it via SMTP with the candidate's resume attached.

Because different posts ask for different details (some want CTC, location, notice period, years of experience; some ask only a few things; some ask nothing), we **cannot** use one fixed mail template. Gemini reads each post + the candidate profile and generates a unique, honest per-post email.

---

## Pipeline Overview

```
step 1        step 2              step 3                    step 4
┌─────────┐  ┌─────────────────┐  ┌──────────────────────┐  ┌───────────────┐
│ Scraper │→ │  contacts.json  │→ │  Gemini mail agent   │→ │  SMTP sender  │
│ (30 min)│  │  dedupe store   │  │  1 mail per post     │  │  2 min apart  │
└─────────┘  └─────────────────┘  └──────────────────────┘  └───────────────┘
     │                                  │                         │
     └──> status.json (PER_POST tracking: PENDING / GENERATED / SENT / SKIPPED+reason)
```

---

## File Structure

```
E:\Jobs Scraper\
├── profile.json            # candidate fact sheet (editable anytime, save to re-process SKIPPED)
├── resume.pdf              # attached to every mail
├── src\jobs_scraper\
│   ├── common.py           # shared LinkedIn session + navigation helpers (existing)
│   ├── scrape_posts.py     # scrape up to 30 min, dedupe by email/phone/post (existing, upgraded)
│   ├── generate_mails.py   # Gemini: 1 tailored mail per contact + status update
│   ├── send_mails.py       # SMTP sender (preview / dry-run / live modes)
│   └── run_cycle.py        # manual entry: scrape → generate → send in one run
├── data\
│   ├── contacts.json       # dedup store: every email / phone / post id ever seen
│   ├── status.json         # per-post: PENDING → GENERATED → SENT / SKIPPED(reason)
│   ├── skipped.json      # why a mail was skipped (missing email / entry-level / profile field)
│   └── emails\             # generated subject + body per contact (human-reviewable)
└── logs\
```

---

## Run Flow (manual `run_cycle`; automation later)

1. **Scrape (max 30 min)** — e.g.
   - Scroll posts results page, collect post content + contact info.
   - Email is the primary target; if no email but a mobile/phone number exists, capture the phone.
   - **Dedup by POST content, not by contact**: the same recruiter can have multiple open roles —
     each *genuinely new* post (text <88% similar to one already collected for that contact)
     is allowed, so every matching position gets a mail. Near-identical reposts of the same
     role are skipped (no duplicate mails for the same job).

2. **Track every post** in `status.json`:
   - `PENDING` → `GENERATED` → `SENT`
   - `SKIPPED` with a reason, e.g. `missing: notice_period`
   - When the user edits `profile.json` and saves, `SKIPPED` items are re-processed on the next run.

3. **Generate mail (Gemini AI)**:
   - Inputs: (a) the recruiter's post text, (b) the candidate profile from `profile.json`.
   - System prompt rules:
     - Read what the recruiter asks for in the post.
     - Write a short, simple, professional email using only the matching facts from the profile.
     - Cover only the details the post asks for — never follow one fixed pattern.
     - Never invent CTC / location / notice / experience numbers.
     - If the post requires something not present in the profile → mark `SKIPPED` with the missing field as the reason (and don't send).
   - Output: `subject` + `body`, saved under `data\emails\`.

4. **Send via SMTP**:
   - Only contacts with status `GENERATED` → mark `SENT`.
   - One mail every **2 minutes**.
   - Resume PDF attached to every mail.
   - Every send logged with timestamp + success/fail.

---

## Sending Modes (safety first — NO risk taking)

| Mode      | Behavior                                                              |
|-----------|-----------------------------------------------------------------------|
| `preview` | Generate mails, show them; edit/adjust the system prompt if needed; re-generate until approved |
| `dry-run` | Send the exact same mails **only to the candidate's own inbox** to verify rendering + attachment |
| `live`    | Real send to recruiters (only after dry-run passes)                   |

Order of use: **preview → dry-run → live** (with system-prompt tuning between preview rounds).

---

## Scheduler Behavior (deferred — manual mode first)

- **Current phase:** manual. Run the whole cycle with one command:
  `python -m jobs_scraper.run_cycle` (scrape ≤30 min → generate → send live).
  Test variants: `--mode dry-run --to <your-email>` or `--mode skip`.
- **Planned (later):** automate twice a day, Mon–Fri, **09:00 and 15:00**.
  Each run: scrape ≤30 min → generate → send (2-min interval).
  Mechanism TBD: Windows Task Scheduler vs always-on Python service.

---

## Candidate Profile Fields (`profile.json`)

Initial set (extendable later):

| Field | Example |
|-------|---------|
| name | `John Doe` |
| email | `john@example.com` |
| phone | `+91 1234567890` |
| current_ctc | `₹12 LPA` |
| expected_ctc | `₹18 LPA` |
| nationality | `Indian` |
| current_location | `New Delhi` |
| preferred_locations | `[]` |
| notice_period | `30 days` |
| availability_of_joining | `Immediate` |
| years_of_experience | `5` |
| skills | `[]` |
| linkedin_url | `https://www.linkedin.com/in/...` |
| education | `B.Tech CSE` |
| resume_path | `resume.pdf` |

---

## Pending Inputs Required From the User

1. **SMTP details** — host, port, username, sender email, app password. ✅ configured
2. **Gemini API key** — ✅ configured (gemini-3.7-flash with 3.5/3-flash rotation; stops after all 3 fail)
3. **Resume path** — confirm `E:\Jobs Scraper\Resume of Manas.pdf`. ✅ auto-detected
4. **Automation timing** — deferred; manual `run_cycle` until user approves

---

## Non-Goals / Guardrails

- No duplicate mails for the same post; multiple positions from the same recruiter each get their own mail (content-based dedup enforced).
- No emails sent in `preview` or `dry-run` modes to real recruiters.
- No fabricated candidate facts — missing data = `SKIPPED` with reason, never guessed.
- Sending pace is intentionally slow (2 min interval) to avoid spam behavior.