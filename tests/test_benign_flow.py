"""End-to-end: the benign task completes, with approval, and is logged."""

from __future__ import annotations

import json
from pathlib import Path

from guardrail_demo.agent import ResearchAgent
from guardrail_demo.gate import PolicyGate
from tests.conftest import POLICY_PATH


def read_audit(audit_path: Path):
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]


def approver_ok(action, decision):
    return True, "test-human", "looks fine"


def test_benign_flow_writes_notes_with_approval(server, sandbox):
    audit_path = sandbox / "audit.log"
    gate = PolicyGate(POLICY_PATH, audit_path, sandbox / "approvals.json")
    agent = ResearchAgent(gate, sandbox)

    outcome = agent.run_task(f"{server}/article.html", "notes.txt", approver=approver_ok)

    notes = (sandbox / "notes.txt").read_text(encoding="utf-8")
    assert "Summary of" in notes
    assert "s3cr3t" not in notes

    decisions = [s["decision"] for s in outcome["transcript"]]
    assert decisions[0] == "allow"  # fetch
    assert decisions[1] == "(pending gate)"  # planner proposal, not yet judged
    write_steps = [s for s in outcome["transcript"] if s["label"] == "write notes"]
    assert write_steps and write_steps[0]["decision"] == "approve"
    assert write_steps[0]["rule"] == "notes-need-approval"
    # the notes file existing proves the approved write actually executed

    records = read_audit(audit_path)
    kinds = [(r["kind"], r["decision"]) for r in records]
    assert ("decision", "allow") in kinds
    assert ("decision", "approve") in kinds
    assert ("resolution", "approved") in kinds
    # the approval request id links the decision to its resolution
    approve_recs = [r for r in records if r["kind"] == "decision" and r["decision"] == "approve"]
    assert approve_recs and approve_recs[0]["approval_request_id"]
