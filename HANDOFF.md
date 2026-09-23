# 🤖 Handoff — Job Applier Tool

> Written 2026-09-23. User paused to sleep; this file exists so the next
> agent (or human) can pick up exactly where we left off.

## Current state

- **Branch:** `feature/auto-batch-runner` (pushed to origin).
- **Tests:** 31 passing before this session; this session added 2 store-dedupe
  tests but could NOT run them here (this Mac has no Python 3.11+ / venv).
  Re-run pytest on the original machine before merging.
- **This session's changes:**
  1. `agent/store.py` — `AppStore.dedupe()` (keep newest per canonical job key)
     and prune-on-`save()`, so duplicate records can never re-accumulate.
  2. `agent/orchestrator.py` — `[app-<id>]` now in every email **Subject** (was
     body-only; Gmail strips the quoted body on reply).
  3. `agent/models.py` — `Resume` gained `work_authorization`,
     `notice_period`, `salary_expectation` (fed to the form-filler LLM).
- **User answers collected** (see below). **Sheet sharing: DONE** (Editor).

## What was just fixed (commit `c9054b8`)

1. **"Get to the form"** — `agent/apply/navigation.py` (new): detects a job
   *listing* page, clicks `Apply` / `Apply now` / `Apply on company site`,
   follows redirects + new tabs, then verifies a real form is present.
2. **Iframe-aware fill** — `agent/apply/filler.py` scans all frames (Indeed's
   inline apply is an iframe), filters out search/nav inputs, and reports
   honestly when no real form exists.
3. **Duplicate-applies fix** — `agent/identity.py` (new): canonical job key
   (`indeed:<jk>`, `linkedin:<currentJobId>`) so tracking-param URL noise
   doesn't make the same job look new. Wired into `runner.py` + both adapters.
4. **Reply loop (4c)** — `agent/orchestrator.py`: `[app-<id>]` threaded into
   every email, matcher scans body + subject, and `_reapply` now applies
   **directly** (previously re-scored and could pend again, stranding the loop).

## Remaining next steps (on the ORIGINAL machine, in order)

1. **Pull this branch**, then `python -m pytest` (expect 33 = 31 + 2 new store
   tests) and `ruff check agent tests`.
2. **Clean duplicate store records.** `AppStore.dedupe()` now does it — run it
   once (e.g. `python -c "from agent.store import AppStore; print(AppStore().dedupe())"`)
   or let the next batch's saves prune. The old 30 records / 7 dupes live on
   that machine. If rows were already written to the Google Sheet, dedupe there too.
3. **Apply the resume extra info** (section below) into `data/resume.json`.
4. **Rotate the DeepSeek key** in `.env` before any live run.
5. **Verify live** (headed, watch the window):
   ```bash
   ./.venv/Scripts/python.exe -m agent auto --dry-run --query "SDET" --limit 1
   ```
   Expect: browser opens → listing → clicks Apply → real form → fields filled.
6. **Merge PRs #2 → #3 → #4 → #5** (as-is). `gh` CLI is NOT installed — use the
   GitHub REST API with a token from `git credential fill` (pipe stdin
   `protocol=https\nhost=github.com\n\n` or it hangs).

## Questions to ask the user when they return

- Visa / work-authorization, notice period, salary expectation, LinkedIn URL
  (for step 3 above).
- Flatten the 4-deep PR stack before merging?
- Rotate the exposed DeepSeek key (see `docs`/memory security note).
User decisions & resume extra info (collected 2026-09-23)

- Work authorization: **Open to visa transfer**
- Notice period: **2 months (negotiable to 1 month); if a form forces a numeric
  answer, use 2**
- Salary expectation: **70–80% of the posted range; if no range is posted,
  email the user to look personally**
- LinkedIn: `https://www.linkedin.com/in/ilham-perdana-jalasena-19890036b/`
- Website/GitHub: `https://github.com/ilhamsena30-arch`
- Environment: **continue on the original machine** — this Mac is not set up
  (no `.venv` / `.env` / resume PDF / store records).
- PR stack: **merge as-is**, in order #2 → #3 → #4 → #5.
- DeepSeek key: **rotate before any live run** (user will paste the new key).

To apply the resume info: after extraction (or by editing `data/resume.json`),
set `work_authorization`, `notice_period`, `salary_expectation` and
`linkedin` / `website` to the values abovenshot the
  runner's browser from a background thread.
- Inbox poll uses `UNSEEN` capped at 20 — never `search("ALL")` (7k-mail hang).
- Browser launch is fatal/loud by design — don't wrap it in best-effort.
- `agent/livestream.py` is staged but unreferenced — decide keep or drop.
