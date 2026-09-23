# Job Applier Agent

> Autonomous job-application agent: **search → match → apply → track → email**, powered by DeepSeek + a headful anti-detect browser (AIHawk / Playwright).

## How it works

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Search      │ → │  Match &     │ → │  Apply /     │ → │  Track       │
│  boards      │   │  Score (LLM) │   │  Notify      │   │  Google She… │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
                                             │                    ▲
                                             ▼                    │
                                      ┌──────────────┐   ┌──────────────┐
                                      │  Email you   │ → │  You reply   │
                                      │  (Gmail)     │   │  (4c)        │
                                      └──────────────┘   └──────────────┘
```

- **Score ≥ threshold** → auto-apply on the ATS site; email you a ✅ success note.
- **Score < threshold** → email you what's missing + link + company + title (pending).
- **LinkedIn Easy Apply** → never auto-submit; email you the link (+ tailored PDF if above threshold).
- **You reply** → the agent updates `resume.json` and re-applies.

## Setup

**See [SETUP.md](SETUP.md) for the full step-by-step guide** (resume, API keys,
Gmail App Password, Google Sheets, LinkedIn caveats).

Quick version:

1. Install dependencies:
   ```bash
   python -m venv .venv
   ./.venv/Scripts/python.exe -m pip install -r requirements.txt
   ./.venv/Scripts/python.exe -m invisible_playwright fetch
   ```
2. Copy `.env.example` → `.env` and fill in your keys (DeepSeek, Gmail app password, Sheets ID).
3. Drop your resume PDF into `data/` — **any** filename containing `resume`
   (e.g. `Resume-Your_Name.pdf`). Newest wins; stale copies are pruned.
4. Check everything: `./.venv/Scripts/python.exe -m agent doctor`

## Usage

Activate the venv once (`source .venv/Scripts/activate`) so `python` works, or
prefix each command with `./.venv/Scripts/python.exe`.

```bash
python -m agent doctor            # check your setup first
python -m agent extract           # resume PDF -> resume.json
python -m agent auto              # THE FULL LOOP: search, match, apply, track, email
python -m agent auto --dry-run    # fill forms but do NOT submit (safe rehearsal)
python -m agent auto --loop --interval 6   # batch, sleep 6h, repeat (Ctrl+C to stop)
python -m agent search "python developer" --location remote   # search only
python -m agent apply "https://..." --title "SWE" --company "Acme"   # one job
python -m agent run               # only poll inbox for your replies
python -m agent dashboard --port 8000    # web dashboard (live video + status)
```

### `agent auto`

One command runs the whole pipeline:

1. Polls the inbox and handles your replies (step 4c).
2. Searches every query in `SEARCH_QUERIES` across the job boards.
3. De-duplicates, and skips jobs already handled before.
4. For each job: match → route → apply/notify → track → email.
5. Stops early once `DAILY_RATE_LIMIT` is reached.

| Flag | Purpose |
| --- | --- |
| `--query "A\|B"` | Override `SEARCH_QUERIES` for this run |
| `--location` | Override `SEARCH_LOCATION` |
| `--limit` | Jobs per board per query |
| `--dry-run` | Fill forms but **do not submit** |
| `--loop` | Repeat: batch, sleep, batch… |
| `--interval H` | Hours to sleep between batches (default `LOOP_INTERVAL_HOURS`) |

`DAILY_RATE_LIMIT` is **enforced** — the runner counts what was applied today
and stops when the cap is hit.

## Decisions & safety

- **Build vs borrow:** uses AIHawk's anti-detect engine (`invisible-playwright`, patched Firefox) as the default browser; falls back to plain Playwright Chromium if not installed. Configurable via `BROWSER_ENGINE=auto|aihawk|playwright`.
- **MCP:** raw Playwright (same engine), per project decision.
- **LinkedIn:** dedicated low-value account, conservative pacing; Easy Apply is notify-only.
- **Model:** `deepseek-flash` (vision-capable) for extraction/form-reading; `deepseek-v4-pro` for hard reasoning (no vision).
- **Search:** dedicated adapters for LinkedIn and Indeed with warm-up + security-check retry (Indeed serves a bot wall on cold direct searches).

## Project layout

```
agent/
  config.py       # settings from .env
  models.py       # Resume, Job, MatchResult, Application
  llm.py          # DeepSeek client (OpenAI-compatible)
  resume/         # PDF -> JSON extraction + filename discovery
  matching/       # scoring + threshold
  search/         # board adapters (LinkedIn, Indeed) + registry
  apply/          # form filler
  browser/        # AIHawk anti-detect / Playwright engine
  email/          # SMTP sender + IMAP receiver
  tracker/        # Google Sheets
  pdf/            # tailored resume PDF
  store.py        # JSON application store
  doctor.py       # setup diagnostics (`agent doctor`)
  ratelimit.py    # enforces DAILY_RATE_LIMIT
  runner.py       # batch driver for `agent auto`
  orchestrator.py # match -> route -> apply -> track -> email
  cli.py, dashboard.py
SETUP.md          # step-by-step setup guide
skills/resume-updater/SKILL.md   # VS Code agent skill
```
