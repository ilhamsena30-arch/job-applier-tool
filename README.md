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
python -m agent search "python developer" --location remote   # search boards
python -m agent apply "https://..." --title "SWE" --company "Acme"   # one-off apply
python -m agent run                          # poll inbox, handle your replies
python -m agent dashboard --port 8000        # web dashboard (live video + status)
```

Then open http://127.0.0.1:8000 — the **live browser stream** shows whatever the
agent is doing in real time. Click **Start demo browser** to preview the stream
without running an application. The stream is MJPEG (`multipart/x-mixed-replace`),
so it works in a plain `<img>` tag with no client library.

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Dashboard: live video, application table, recordings, apply form |
| `GET /stream` | MJPEG live video of the active browser (add `?fps=5` to tune) |
| `GET /demo/start` \| `/demo/stop` | Launch / stop a preview browser for the stream |
| `POST /apply` | Apply to a URL (the stream follows the real application) |

## Decisions & safety

- **Build vs borrow:** uses AIHawk's anti-detect engine (`invisible-playwright`, patched Firefox) as the default browser; falls back to plain Playwright Chromium if not installed. Configurable via `BROWSER_ENGINE=auto|aihawk|playwright`.
- **MCP:** raw Playwright (same engine), per project decision.
- **LinkedIn:** dedicated low-value account, conservative pacing; Easy Apply is notify-only.
- **Model:** `deepseek-flash` (vision-capable) for extraction/form-reading; `deepseek-v4-pro` for hard reasoning (no vision).
- **Search:** dedicated adapters for LinkedIn and Indeed with warm-up + security-check retry (Indeed serves a bot wall on cold direct searches).
- **Live view:** the dashboard streams the browser over MJPEG at ~3fps; the orchestrator registers its browser so every real application is watchable live. Recordings are still saved for replay.

## Project layout

```
agent/
  config.py       # settings from .env
  models.py       # Resume, Job, MatchResult, Application
  llm.py          # DeepSeek client (OpenAI-compatible)
  resume/         # PDF -> JSON extraction
  matching/       # scoring + threshold
  search/         # board adapters (LinkedIn, Indeed) + registry
  apply/          # form filler
  browser/        # AIHawk anti-detect / Playwright engine
  email/          # SMTP sender + IMAP receiver
  tracker/        # Google Sheets
  pdf/            # tailored resume PDF
  store.py        # JSON application store
  livestream.py   # live MJPEG frame source + active-browser registry
  orchestrator.py # main loop
  cli.py, dashboard.py
skills/resume-updater/SKILL.md   # VS Code agent skill
```
