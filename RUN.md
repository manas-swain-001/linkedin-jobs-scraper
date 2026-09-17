# How to Run — LinkedIn Job Scraper

---

## Quick Start

Open a terminal in `E:\Jobs Scraper` and run:

```bash
uv run python -m jobs_scraper.run_cycle
```

That single command runs the **full pipeline**: scrape → generate mails → send live.

---

## Run Modes

```bash
# Generate only (no sending) — review what it produces
uv run python -m jobs_scraper.run_cycle --mode skip

# Preview — prints mails to terminal (no file changes, no send)
uv run python -m jobs_scraper.run_cycle --mode preview

# Dry-run — sends all mails to YOUR inbox only (test rendering + resume PDF)
uv run python -m jobs_scraper.run_cycle --mode dry-run --to myselfmanaskumar01@gmail.com

# Live — sends real mails to recruiter emails (default, no flag needed)
uv run python -m jobs_scraper.run_cycle
uv run python -m jobs_scraper.run_cycle --mode live
```

| Mode | Sends to recruiters? | Purpose |
|------|---------------------|---------|
| `skip` | No | Scrape + generate only; review mails in `data/emails/` |
| `preview` | No | Print mails to terminal only (no files saved) |
| `dry-run` | No (sends to your inbox only) | Test rendering + resume attachment |
| `live` | Yes | Real send to all scraped recruiter emails |

---

## Optional Flags

```bash
# Change delay between mails (default 60 seconds)
uv run python -m jobs_scraper.run_cycle --mode live --interval 90

# Combine dry-run + custom recipient
uv run python -m jobs_scraper.run_cycle --mode dry-run --to myselfmanaskumar01@gmail.com --interval 30
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `live` | `skip` / `preview` / `dry-run` / `live` |
| `--to` | *(none)* | Override recipient (dry-run only) |
| `--interval` | `60` | Seconds between each mail sent |

---

## What Happens on Each Run

```
Scrape (≤30 min)        →  data/posts.json        (new posts collected)
Generate mails (LLM)    →  data/emails/*.txt       (one file per post)
                           data/status.json         (SCRAPED → GENERATED → SENT)
                           data/skipped.json        (why any mails were skipped)
Send mails (SMTP)       →  each recruiter receives your resume + tailored mail
```

---

## Recommended First-Run Flow

```bash
# Step 1: Scrape + generate (no send) — check what was collected
uv run python -m jobs_scraper.run_cycle --mode skip

# Step 2: Open and review the generated mails
#         data/emails/*.txt

# Step 3: Check why any mails were skipped
#         data/skipped.json

# Step 4: Test sending to your own inbox
uv run python -m jobs_scraper.run_cycle --mode dry-run --to myselfmanaskumar01@gmail.com

# Step 5: After confirming everything looks right, go live
uv run python -m jobs_scraper.run_cycle --mode live
```

---

## Prerequisites

- **Python 3.14+** — installed via uv
- **LinkedIn session** — must be logged in on first run; the browser profile `.browser_profile` preserves it automatically
- **secrets.json** — must contain:
  - `GEMINI_API_KEY` — your Google AI Studio key
  - `GEMINI_MODEL` — e.g. `gemini-3.7-flash`
  - `SENDER_EMAIL` / `SMTP_PASSWORD` / `SMTP_USER` / `SMTP_HOST` / `SMTP_PORT` — your Gmail SMTP credentials
- **Resume PDF** — auto-detected from `E:\Jobs Scraper\Resume of Manas.pdf`
- **profile.json** — your candidate details (edited anytime; re-run picks up changes)

---

## Timing

| Phase | Duration |
|-------|----------|
| Scrape (scroll LinkedIn) | Up to **30 min** |
| Generate mails (Gemini LLM) | ~**3-5 sec** per post |
| Send mails (SMTP + PDF attach) | **60 sec** between each (configurable) |

---

## Files and What They Store

| File | Contents |
|------|----------|
| `data/posts.json` | All scraped posts (content, author, emails, phones, status) |
| `data/emails/<post_id>.txt` | Generated mail per post (`TO:` / `SUBJECT:` / body) |
| `data/status.json` | Per-post pipeline status (`SCRAPED` → `GENERATED` → `SENT`) |
| `data/skipped.json` | Skipped mails with reason + fix action |
| `logs/app.log` | Chronological run log |
| `secrets.json` | API keys + SMTP credentials (gitignored) |
| `profile.json` | Your candidate profile (edit anytime, re-run to retry) |

---

## If You Add Packages in Future

Use pip inside the existing venv (safest after the earlier uv corruption issue):

```bash
.venv\Scripts\python.exe -m pip install <package>
```

Or use uv sync to restore a clean state if the venv ever breaks:

```bash
uv sync
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Scraper hangs at login screen | LinkedIn session expired | Log in to LinkedIn in a browser, copy cookies, or delete `.browser_profile` and log in fresh |
| `UNAVAILABLE 503` errors | Gemini model temporarily overloaded | Wait a few minutes, rerun. The 3-model rotation handles this automatically |
| `PerDay 429` errors | Free-tier daily quota exhausted | Quota resets at midnight; wait or upgrade to paid tier |
| Mails show in `data/skipped.json` | Skipped posts need action | Read the `reason` and `action` fields; update `profile.json` accordingly |
| `ModuleNotFoundError: jobs_scraper` | Not in the right directory | Run from `E:\Jobs Scraper` |
