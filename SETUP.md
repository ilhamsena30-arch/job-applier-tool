# Setup Guide

Step-by-step setup for the Job Applier Agent. Work through it in order — you can
stop after Part 1 and still use `extract` and `search`.

> **Shell:** examples use **bash** (Windows venv layout).
> Run `python -m agent doctor` at any time to see exactly what is still missing.

---

## Part 1 — Required

### 1.1 Install dependencies

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m invisible_playwright fetch   # main engine
./.venv/Scripts/python.exe -m playwright install chromium  # optional fallback
```

Or activate once and drop the prefix:

```bash
source .venv/Scripts/activate
python -m invisible_playwright fetch
```

> **Common mistake:** `python -m pip playwright install chromium` gives
> `unknown command "playwright"` — the word goes to *pip*. Use
> `python -m playwright install chromium` (no `pip`).

Verify:

```bash
./.venv/Scripts/python.exe -m agent doctor
```

### 1.2 Add your resume

Drop your resume PDF into `data/`. **The filename is not hardcoded** — the agent
finds any PDF whose name contains `resume` (case-insensitive):

```
data/Resume-Ilham_Perdana_Jalasena-SDET.pdf   -> matched
data/Ilham_Perdana_Resume.pdf                 -> matched
data/cv-2027.pdf                              -> NOT matched (no "resume")
```

If several PDFs match, the **newest by modified time wins and the others are
deleted**, so exactly one resume remains. To pin a specific file instead, set
`RESUME_PDF_PATH` in `.env` (that skips discovery and cleanup).

Then convert it to structured JSON:

```bash
./.venv/Scripts/python.exe -m agent extract
```

This writes `data/resume.json` (always that name — it is an internal artifact and
is never sent to employers). **Open it and check it is correct** — the agent uses
this file for matching, form-filling and the tailored PDF. Fix errors by hand; it
is plain JSON.

> `data/*.pdf` and `data/*.json` are gitignored, so your resume is never committed.

### 1.3 DeepSeek API key

1. Sign up at <https://platform.deepseek.com> and top up (prepaid).
2. **API Keys** → **Create new API key** → copy it (`sk-...`, shown only once).

---

## Part 2 — The `.env` file

All credentials live in one file. Create it:

```bash
cp .env.example .env
```

**This file is gitignored — never commit it.**

### DeepSeek

```dotenv
DEEPSEEK_API_KEY=sk-your-real-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro
```

> `deepseek-flash` handles vision (PDF parsing, reading screenshots).
> `deepseek-v4-pro` has **no** vision — used only for hard reasoning.

### Gmail (notifications + reading your replies)

Gmail requires an **App Password**; your normal password will not work.

1. Enable **2-Step Verification**: <https://myaccount.google.com/security>
2. Create an App Password: <https://myaccount.google.com/apppasswords>
   (name it "job-agent") → copy the 16-character code.
3. Add it:

```dotenv
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
```

### Google Sheets (application tracker)

1. <https://console.cloud.google.com> → create a project.
2. **APIs & Services** → **Library** → enable **Google Sheets API**.
3. **Credentials** → **Create credentials** → **Service account** → create.
4. Open the service account → **Keys** → **Add key** → **Create new key** → **JSON**.
5. Save the downloaded file as `credentials.json` in the repo root.
6. Create a Google Sheet, then **Share** it with the service account email
   (`name@project.iam.gserviceaccount.com`) as **Editor**.
7. Copy the ID from the sheet URL
   (`docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`):

```dotenv
GOOGLE_CREDENTIALS_FILE=credentials.json
SPREADSHEET_ID=1AbC...your_sheet_id...XyZ
```

### Tuning (optional)

```dotenv
CONFIDENCE_THRESHOLD=75.0   # auto-apply at/above this score
DAILY_RATE_LIMIT=10         # HARD cap on applications per day (enforced)
HEADED=true                 # show the browser window
BROWSER_ENGINE=auto         # auto | aihawk | playwright

# What to search for, and how the auto runner behaves:
SEARCH_QUERIES=SDET|QA Automation Engineer|Test Automation Engineer
SEARCH_LOCATION=Jakarta
SEARCH_LIMIT=10             # jobs per board per query
AUTO_SUBMIT=true            # false = fill forms but never submit
LOOP_INTERVAL_HOURS=6.0     # sleep between batches with --loop
```

### Verify

```bash
./.venv/Scripts/python.exe -m agent doctor
```

Every line should read `[ OK ]` before you continue.

---

## Part 3 — Validate end to end

```bash
# 1. Resume parsed?
./.venv/Scripts/python.exe -m agent extract

# 2. Can it find jobs? (opens a real browser)
./.venv/Scripts/python.exe -m agent search "python developer" --location remote --headed

# 3. Dashboard with live video
./.venv/Scripts/python.exe -m agent dashboard --port 8000
#    -> open http://127.0.0.1:8000 , click "Start demo browser"

# 4. The full loop — dry run first (fills forms, submits nothing)
./.venv/Scripts/python.exe -m agent auto --dry-run --limit 3

# 5. When the dry run looks right, let it submit
./.venv/Scripts/python.exe -m agent auto
```

`agent auto` searches, matches, applies, tracks to your sheet, and emails you —
then you can run it again, or use `--loop` to have it repeat on a schedule.

---

## Part 4 — LinkedIn (read before looking for a password setting)

**There is no LinkedIn username/password setting, and that is deliberate.**

### Why

- A plaintext LinkedIn password in `.env` is a bad idea.
- Programmatic login is exactly what triggers LinkedIn's bot detection and gets
  accounts restricted.
- The agent deliberately **never auto-submits Easy Apply** — for those jobs it
  only emails you the link. So it does not need an authenticated session to help.

### Current behaviour

The LinkedIn adapter (`agent/search/linkedin.py`) searches LinkedIn's *public*
job listings with a fresh browser (no saved login):

- **Public job search:** works unauthenticated (may be rate-limited).
- **Logged-in-only results / Easy Apply details:** not available yet, because the
  browser keeps no persistent profile, so a login would not survive between runs.

### Recommended approach (needs a small change)

Add **persistent browser profiles**, so you log in *by hand once* in the visible
window and the session is reused:

1. Launch the browser with a saved profile directory.
2. Log into LinkedIn manually; solve any captcha yourself.
3. Later runs reuse that session — no password is ever stored by the agent.

Risks if you do this:

- Use a **dedicated / low-value LinkedIn account**, never your primary one.
- Keep `DAILY_RATE_LIMIT` low (start at 5–10).
- LinkedIn automation violates their Terms of Service; restrictions are possible.
  Prefer applying on company ATS sites (Greenhouse / Lever / Workday).

### Indeed

Same story — no credentials needed or accepted. Indeed works unauthenticated;
the adapter warms up the homepage first to get past the bot wall.

---

## Security checklist

- [ ] `.env` exists and is **not** committed (`git status` must not list it)
- [ ] `credentials.json` is **not** committed
- [ ] `data/*.pdf` (your resume, any name) and `data/resume.json` are **not** committed
- [ ] Gmail uses an App Password, not your real password
- [ ] LinkedIn uses a low-value account (only if you enable sessions later)

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `unknown command "playwright"` | Word sent to pip | Use `python -m playwright ...` (no `pip`) |
| `..venvScriptspython.exe: command not found` | PowerShell path in bash (backslashes are escapes) | Use `./.venv/Scripts/python.exe` |
| `[Errno 10048]` on port 8000 | Port already in use | Dashboard auto-picks the next free port |
| `ModuleNotFoundError: agent` | Running system Python | Use the venv: `./.venv/Scripts/python.exe` |
