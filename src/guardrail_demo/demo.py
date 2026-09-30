"""Runnable story: a benign run, then the same agent under attack.

Usage:
    python demo.py [--scenario both|benign|attack|benign-email|attack-email|all] [--quiet]

Everything runs locally: the pages are served from examples/pages over
localhost, notes land in a temp sandbox, emails are queued to a sandbox
outbox file (never delivered), and the audit log is printed as the
evidence. Exit code is 0 in all scenarios; in the attack scenarios the
guardrail denying the write or the send IS the success case.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from guardrail_demo.agent import BlockedAction, ResearchAgent
from guardrail_demo.gate import PolicyGate
from guardrail_demo.server import start_demo_server
from guardrail_demo.tools import read_outbox

REPO_ROOT = Path(__file__).resolve().parent


def find_repo_root() -> Path:
    """Locate the repo checkout (policies + example pages).

    Prefers the current working directory, then walks up from this file.
    The demo is meant to run from a checkout of the repo.
    """
    candidates = [Path.cwd(), REPO_ROOT, *REPO_ROOT.parents]
    for candidate in candidates:
        if (candidate / "policies" / "research-agent.yaml").exists():
            return candidate
    raise SystemExit(
        "could not find the repo checkout: run demo.py from the agent-guardrail-demo directory"
    )


def approver_ok(action, decision):
    return True, "demo-human", "summary looks fine, approved"


def print_audit(audit_path: Path, say) -> None:
    say("  audit log:")
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        extra = ""
        if rec["kind"] == "decision":
            extra = f"rule={rec['rule']}"
            if rec.get("approval_request_id"):
                extra += f" approval={rec['approval_request_id']}"
        elif rec["kind"] == "resolution":
            extra = rec["reason"]
        say(f"    {rec['ts']} {rec['kind']:10} {rec['decision']:8} {extra}")


def run_scenario(name: str, page: str, notes_file: str, quiet: bool, repo_root: Path) -> None:
    say = (lambda *a: None) if quiet else print
    pages_dir = repo_root / "examples" / "pages"
    policy = repo_root / "policies" / "research-agent.yaml"
    sandbox = Path(tempfile.mkdtemp(prefix="guardrail-demo-"))
    audit_path = sandbox / "audit.log"
    approvals_path = sandbox / "approvals.json"

    server, base_url = start_demo_server(pages_dir)
    try:
        gate = PolicyGate(policy, audit_path, approvals_path)
        agent = ResearchAgent(gate, sandbox)
        url = f"{base_url}/{page}"

        say(f"\n=== scenario: {name} ===")
        say(f"  task: fetch {page} and write notes to {notes_file}")
        try:
            outcome = agent.run_task(url, notes_file, approver=approver_ok)
            for step in outcome["transcript"]:
                why = f" ({step['why']})" if step.get("why") else ""
                say(
                    f"  [{step['label']}] {step['tool']} -> "
                    f"{step['decision']} (rule: {step['rule']}){why}"
                )
            say(f"  notes written: {sandbox / notes_file}")
            content = (sandbox / notes_file).read_text(encoding="utf-8")
            say("  notes preview: " + content[:160].replace("\n", " ") + "...")
        except BlockedAction as blocked:
            say(f"  BLOCKED: {blocked}")
            say("  the injected instruction never reached the notes file.")
        print_audit(audit_path, say)
    finally:
        server.shutdown()


def run_email_scenario(
    name: str, page: str, recipient: str, subject: str, quiet: bool, repo_root: Path
) -> None:
    say = (lambda *a: None) if quiet else print
    pages_dir = repo_root / "examples" / "pages"
    policy = repo_root / "policies" / "research-agent.yaml"
    sandbox = Path(tempfile.mkdtemp(prefix="guardrail-demo-"))
    audit_path = sandbox / "audit.log"
    approvals_path = sandbox / "approvals.json"

    server, base_url = start_demo_server(pages_dir)
    try:
        gate = PolicyGate(policy, audit_path, approvals_path)
        agent = ResearchAgent(gate, sandbox)
        url = f"{base_url}/{page}"

        say(f"\n=== scenario: {name} ===")
        say(f"  task: fetch {page} and email notes to {recipient}")
        try:
            outcome = agent.run_email_task(url, recipient, subject, approver=approver_ok)
            for step in outcome["transcript"]:
                why = f" ({step['why']})" if step.get("why") else ""
                say(
                    f"  [{step['label']}] {step['tool']} -> "
                    f"{step['decision']} (rule: {step['rule']}){why}"
                )
            outbox = read_outbox(sandbox)
            say(f"  outbox: {len(outbox)} message(s)")
            for message in outbox:
                preview = message["body"][:120].replace("\n", " ")
                say(f"    to={message['to']} subject={message['subject']!r}")
                say(f"    body preview: {preview}...")
        except BlockedAction as blocked:
            say(f"  BLOCKED: {blocked}")
            say("  the injected instruction never left the sandbox as email.")
            outbox = read_outbox(sandbox)
            say(f"  outbox: {len(outbox)} message(s) - nothing was sent.")
        print_audit(audit_path, say)
    finally:
        server.shutdown()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="agent-guardrail-demo story runner")
    parser.add_argument(
        "--scenario",
        choices=["both", "benign", "attack", "benign-email", "attack-email", "all"],
        default="both",
        help="'both' keeps the original notes-write story; 'all' runs every scenario.",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the audit evidence")
    args = parser.parse_args(argv)
    repo_root = find_repo_root()

    if args.scenario in ("both", "benign", "all"):
        run_scenario(
            "benign: summarize a normal page",
            "article.html",
            "notes-benign.txt",
            args.quiet,
            repo_root,
        )
    if args.scenario in ("both", "attack", "all"):
        run_scenario(
            "attack: the same agent fetches a poisoned page",
            "article-injected.html",
            "notes-attack.txt",
            args.quiet,
            repo_root,
        )
    if args.scenario in ("benign-email", "all"):
        run_email_scenario(
            "benign-email: email a summary of a normal page",
            "article.html",
            "user@example.com",
            "Page summary",
            args.quiet,
            repo_root,
        )
    if args.scenario in ("attack-email", "all"):
        run_email_scenario(
            "attack-email: the poisoned page tells the agent to exfiltrate by email",
            "article-injected-email.html",
            "user@example.com",
            "Page summary",
            args.quiet,
            repo_root,
        )
    if not args.quiet:
        print(
            "\nDone. In the attack scenarios, the deny in the audit log is the "
            "whole point: the guardrail caught what the agent could not see."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
