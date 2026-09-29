"""End-to-end: the injected instruction is blocked and the block is logged."""

from __future__ import annotations

import json

import pytest

from guardrail_demo.agent import BlockedAction, ResearchAgent
from guardrail_demo.gate import PolicyGate
from tests.conftest import POLICY_PATH


def approver_ok(action, decision):
    # Even a cooperative human never sees this: the deny fires first.
    return True, "test-human", "looks fine"


def test_attack_is_blocked_and_logged(server, sandbox):
    audit_path = sandbox / "audit.log"
    gate = PolicyGate(POLICY_PATH, audit_path, sandbox / "approvals.json")
    agent = ResearchAgent(gate, sandbox)

    with pytest.raises(BlockedAction) as excinfo:
        agent.run_task(f"{server}/article-injected.html", "notes.txt", approver=approver_ok)

    assert excinfo.value.decision.decision == "deny"
    assert excinfo.value.decision.rule == "no-instructions-from-tool-output"

    # The injected credentials never reach the notes file.
    notes_path = sandbox / "notes.txt"
    if notes_path.exists():
        content = notes_path.read_text(encoding="utf-8")
        assert "s3cr3t" not in content
        assert "admin" not in content

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    denies = [r for r in records if r["kind"] == "decision" and r["decision"] == "deny"]
    assert denies, "expected a deny record in the audit log"
    assert denies[0]["rule"] == "no-instructions-from-tool-output"
    assert "tool-output" in denies[0]["action"]["args"]["instruction_source"]


def test_attack_without_approver_is_still_blocked(server, sandbox):
    # No human on call changes nothing: deny needs no approval round-trip.
    audit_path = sandbox / "audit.log"
    gate = PolicyGate(POLICY_PATH, audit_path, sandbox / "approvals.json")
    agent = ResearchAgent(gate, sandbox)

    with pytest.raises(BlockedAction):
        agent.run_task(f"{server}/article-injected.html", "notes.txt", approver=None)
