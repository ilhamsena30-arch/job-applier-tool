---
name: resume-updater
description: Update the candidate's structured resume (data/resume.json) from new information the user provides. Use when the user shares new skills, experience, education, contact details, or corrections and wants them merged into their resume used by the job-applier agent. Preserves existing fields, merges rather than replaces, and writes valid JSON matching the Resume schema (name, email, phone, location, linkedin, website, summary, skills[], experience[], education[]).
---

# Resume Updater

You update `data/resume.json` — the structured resume consumed by the job-application agent.

## When to use
- The user emails/mentions new skills, jobs, education, or corrected details.
- A pending application reported "missing" data that the user then supplied.

## Workflow
1. Read `data/resume.json`. If it does not exist, first run `python -m agent extract` (requires `data/resume.pdf`).
2. Read the user's update and determine what changed.
3. Merge carefully:
   - **skills**: append new skills, de-duplicate, keep original casing.
   - **experience**: add new entries with `title`, `company`, `start`, `end`, `bullets`. If updating an existing role, match by `company` + `title`.
   - **education**: add or update by `school`.
   - **personal fields** (name, email, phone, location, linkedin, website, summary): replace only if the new value is non-empty.
4. Never delete existing data the user did not ask to remove.
5. Write the result back as pretty-printed JSON (2-space indent) with UTF-8 encoding.

## Schema
```json
{
  "name": "", "email": "", "phone": "", "location": "",
  "linkedin": "", "website": "", "summary": "",
  "skills": [],
  "experience": [{"title": "", "company": "", "start": "", "end": "", "bullets": []}],
  "education": [{"school": "", "degree": "", "field": "", "start": "", "end": ""}]
}
```

## After updating
- Confirm the file is valid JSON and matches the schema.
- If the update came from a job-application reply, the agent will re-apply automatically on its next cycle.
