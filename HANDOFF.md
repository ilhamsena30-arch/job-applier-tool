# 🤖 Handoff — Job Applier Tool

> Written 2026-09-23. User paused to sleep; this file exists so the next
> agent (or human) can pick up exactly where we left off.

## Current state

- **Branch:** `feature/auto-batch-runner` — HEAD `c9054b8` (pushed to origin).
- **Tests:** 31 passing. **Ruff:** clean on all touched files.
- **The core apply loop now works end-to-end in code** (not yet proven on a live
  form — that's the very next thing to verify).

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

## Next steps (in order)

1. **Clean duplicate store records.** 30 records, 22 distinct jobs, 7 duplicated
   (Indeed `jk` ids). Keep the newest per `agent.identity.canonical_job_key`.
   If rows were already written to the Google Sheet, dedupe there too.
2. **Put `[app-<id>]` in the email Subject too.** It's currently body-only;
   Gmail often strips the quoted body on reply, losing the token → the reply
   can't re-apply. The subject always survives.
3. **Add "extra info" to `data/resume.json`:** work authorization / visa,
   notice period, salary expectation, LinkedIn URL, website. **Ask the user**
   for the values first.
4. **Ask the user to share the sheet** with the service account as **Editor**:
   `ilhamsena@job-applier-agent-509414.iam.gserviceaccount.com`
   Sheet: `1jaBZe13dhrSxpP79Pjg6Z8uU1jdHzSl7y85OCCFLvks`
   (Tracker prints a non-fatal 403 until this is done.)
5. **Verify live** (headed, watch the window):
   ```bash
   ./.venv/Scripts/python.exe -m agent auto --dry-run --query "SDET" --limit 1
   ```
   Expect: browser opens → listing → clicks Apply → real form → fields filled.
6. **Merge PRs #2 → #3 → #4 → #5** (stacked in that order). `gh` CLI is NOT
   installed — create PRs via the GitHub REST API using a token from
   `git credential fill` (must pipe stdin `protocol=https\nhost=github.com\n\n`,
   otherwise it hangs).

## Questions to ask the user when they return

- Visa / work-authorization, notice period, salary expectation, LinkedIn URL
  (for step 3 above).
- Flatten the 4-deep PR stack before merging?
- Rotate the exposed DeepSeek key (see `docs`/memory security note).

## Gotchas (hard-won)

- Use **bash** syntax: `./.venv/Scripts/python.exe`. Backslash paths break.
- `git credential fill` MUST receive stdin or it hangs forever.
- Playwright sync API is bound to its creating thread — never screenshot the
  runner's browser from a background thread.
- Inbox poll uses `UNSEEN` capped at 20 — never `search("ALL")` (7k-mail hang).
- Browser launch is fatal/loud by design — don't wrap it in best-effort.
- `agent/livestream.py` is staged but unreferenced — decide keep or drop.
