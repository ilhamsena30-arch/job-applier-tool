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

    p_apply = sub.add_parser("apply", help="Apply to a single job URL")
    p_apply.add_argument("url")
    p_apply.add_argument("--title")
    p_apply.add_argument("--company")
    p_apply.add_argument("--description")
    p_apply.add_argument("--easy-apply", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    p_run = sub.add_parser("run", help="Poll inbox and process replies")
    p_run.add_argument("--interval", type=int, default=60)
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
