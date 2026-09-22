"""Command-line entrypoint for the job-applier agent."""

from __future__ import annotations

import argparse
import time

from agent.config import get_settings
from agent.email.receiver import EmailReceiver
from agent.models import Job, JobSource
from agent.orchestrator import Orchestrator
from agent.resume.extract import extract_resume, load_resume
from agent.store import AppStore


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract resume PDF -> JSON."""
    resume = extract_resume()
    from agent.resume.extract import save_resume

    path = save_resume(resume)
    print(f"Resume extracted -> {path}")
    print(f"  Skills: {len(resume.skills)} | Experience: {len(resume.experience)}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    """Apply to a single job URL."""
    resume = load_resume()
    orch = Orchestrator()
    job = Job(
        id=f"manual-{int(time.time())}",
        title=args.title or "Unknown title",
        company=args.company or "Unknown company",
        url=args.url,
        apply_url=args.url,
        source=JobSource.MANUAL,
        description=args.description or "",
        easy_apply=args.easy_apply,
    )
    app = orch.process_job(job, resume)
    print(f"Done: {app.status.value} (score {app.match.score if app.match else '?'}/100)")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search job boards and print normalized results."""
    from agent.browser.engine import Browser, BrowserOptions
    from agent.search.registry import search_all

    browser = Browser(BrowserOptions(headed=args.headed)).launch()
    try:
        jobs = search_all(browser, args.query, args.location, limit_per_board=args.limit)
    finally:
        browser.close()

    for j in jobs:
        flag = "EASY" if j.easy_apply else "ATS "
        print(f"[{flag}] {j.company} — {j.title} ({j.location})")
        print(f"       {j.url}")
    print(f"\n{len(jobs)} job(s) found.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check that the environment is configured correctly."""
    from agent.doctor import format_report, run_all

    report = run_all()
    print(format_report(report))
    return 0 if report.ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run the reply-processing loop (poll inbox, handle 4c replies)."""
    resume = load_resume()
    orch = Orchestrator()
    store = AppStore()
    receiver = EmailReceiver()

    def handler(reply):
        print(f"Processing reply from {reply.sender}: {reply.subject[:50]}")
        orch.handle_reply(reply)

    print("Polling inbox for replies... (Ctrl+C to stop)")
    try:
        while True:
            receiver.poll(handler)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="job-agent", description="Autonomous job applier")
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract resume PDF -> JSON")
    p_extract.set_defaults(func=cmd_extract)

    p_doctor = sub.add_parser("doctor", help="Check that your setup is configured")
    p_doctor.set_defaults(func=cmd_doctor)

    p_apply = sub.add_parser("apply", help="Apply to a single job URL")
    p_apply.add_argument("url")
    p_apply.add_argument("--title")
    p_apply.add_argument("--company")
    p_apply.add_argument("--description")
    p_apply.add_argument("--easy-apply", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    p_search = sub.add_parser("search", help="Search job boards for matching jobs")
    p_search.add_argument("query")
    p_search.add_argument("--location", default="")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--headed", action="store_true")
    p_search.set_defaults(func=cmd_search)

    p_run = sub.add_parser("run", help="Poll inbox and process replies")
    p_run.add_argument("--interval", type=int, default=60)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
