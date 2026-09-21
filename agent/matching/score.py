"""Score a Job against the user's Resume using the LLM."""

from __future__ import annotations

from agent.config import get_settings
from agent.llm import get_llm
from agent.models import Job, MatchResult, Resume

_SYSTEM_PROMPT = """You are a recruiting assistant. You compare a candidate's resume to a
job description and produce a strict, honest match assessment.

Scoring rubric (0-100):
- Skills overlap (weight 40): exact and adjacent skills from the JD present in the resume.
- Experience & seniority (weight 30): years and level vs the JD's requirements.
- Domain / industry (weight 15): relevant context, tools, and technologies.
- Education & credentials (weight 15): degrees, certs, licenses when required.

Do NOT inflate. If key requirements are absent, score low and list them.
Return ONLY a valid JSON object:
{
  "score": <int 0-100>,
  "verdict": "<1-2 sentence summary>",
  "matched_skills": [str],
  "missing_skills": [str],
  "suggested_answers": { "<form question>": "<suggested answer based only on resume>" }
}
`suggested_answers` should map common application questions (e.g. years of experience,
notice period, salary expectation where determinable, relocation, work authorization)
to answers derivable from the resume. Leave out anything you cannot derive."""


def match_job(resume: Resume, job: Job) -> MatchResult:
    """Score a job against the resume and return a MatchResult."""
    llm = get_llm()

    resume_text = resume.model_dump_json(exclude_none=True)
    jd = job.description or f"{job.title} at {job.company}"

    # Truncate very long JDs to keep tokens reasonable.
    if len(jd) > 8000:
        jd = jd[:8000] + "\n...[truncated]"

    user_prompt = (
        "Candidate resume:\n"
        f"<resume>\n{resume_text}\n</resume>\n\n"
        "Job description:\n"
        f"<job>\nTitle: {job.title}\nCompany: {job.company}\nLocation: {job.location}\n{jd}\n</job>"
    )

    data = llm.chat_json(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    score = float(data.get("score", 0))
    return MatchResult(
        score=score,
        verdict=data.get("verdict", ""),
        matched_skills=data.get("matched_skills", []),
        missing_skills=data.get("missing_skills", []),
        suggested_answers=data.get("suggested_answers", {}),
        raw=data,
    )


def should_auto_apply(match: MatchResult) -> bool:
    """True when the score meets the configured confidence threshold."""
    return match.score >= get_settings().confidence_threshold
