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

1. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```
   (Optional anti-detect engine: `pip install invisible-playwright` — see AIHawk.)
2. Copy `.env.example` → `.env` and fill in your keys (DeepSeek, Gmail app password, Sheets ID).
3. Put your resume at `data/resume.pdf`.

## Usage

```bash
python -m agent extract                      # resume.pdf -> resume.json
python -m agent apply "https://..." --title "SWE" --company "Acme"   # one-off apply
python -m agent run                          # poll inbox, handle your replies
uvicorn agent.dashboard:app --reload         # web dashboard (status + recordings)
```

## Decisions & safety

- **Build vs borrow:** uses AIHawk's anti-detect engine when installed; falls back to Playwright.
- **MCP:** raw Playwright (same engine), per project decision.
- **LinkedIn:** dedicated low-value account, conservative pacing; Easy Apply is notify-only.
- **Model:** `deepseek-flash` (vision-capable) for extraction/form-reading; `deepseek-v4-pro` for hard reasoning (no vision).

## Project layout

```
agent/
  config.py       # settings from .env
  models.py       # Resume, Job, MatchResult, Application
  llm.py          # DeepSeek client (OpenAI-compatible)
  resume/         # PDF -> JSON extraction
  matching/       # scoring + threshold
  search/         # board adapters
  apply/          # form filler
  browser/        # anti-detect / Playwright engine
  email/          # SMTP sender + IMAP receiver
  tracker/        # Google Sheets
  pdf/            # tailored resume PDF
  store.py        # JSON application store
  orchestrator.py # main loop
  cli.py, dashboard.py
skills/resume-updater/SKILL.md   # VS Code agent skill
```
