"""The policy gate: every tool call passes through agent-policy-kit first.

Decisions are deterministic: allow runs the tool, deny blocks it, approve
routes to a human (simulated by a callback in the demo). Every evaluation
and every approval resolution is appended to a JSONL audit log.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent_policy_kit import (
    ApprovalStore,
    Decision,
    evaluate,
    load_policy,
    log_decision,
    log_resolution,
    request_approval,
    resolve_approval,
)

# approver(action, decision) -> (approved, by, note)
Approver = Callable[[dict[str, Any], Decision], tuple[bool, str, str]]


class BlockedAction(Exception):
    """Raised when the policy gate refuses a tool call."""

    def __init__(self, decision: Decision, note: str = ""):
        self.decision = decision
        reason = decision.reason + (f" ({note})" if note else "")
        super().__init__(f"blocked: {decision.decision} by rule '{decision.rule}': {reason}")


class PolicyGate:
    def __init__(self, policy_path: str | Path, audit_path: str | Path, approvals_path: str | Path):
        self.policy = load_policy(policy_path)
        self.audit_path = Path(audit_path)
        self.store = ApprovalStore(Path(approvals_path))

    def run(
        self, action: dict[str, Any], tool_fn: Callable[[], Any], approver: Approver | None = None
    ) -> dict[str, Any]:
        """Evaluate one action and run the tool only if policy permits."""
        decision = evaluate(self.policy, action)

        if decision.decision == "allow":
            log_decision(self.audit_path, decision, action)
            return {"status": "executed", "result": tool_fn(), "decision": decision}

        if decision.decision == "deny":
            log_decision(self.audit_path, decision, action)
            raise BlockedAction(decision)

        # approve: ask a human, defaulting to denied when nobody is home.
        request = request_approval(
            self.store, action, self.policy.name, decision.rule or "", ttl_minutes=30
        )
        log_decision(self.audit_path, decision, action, request["id"])
        if approver is None:
            approved, by, note = False, "no-approver", "no approver configured"
        else:
            approved, by, note = approver(action, decision)
        resolved = resolve_approval(self.store, request["id"], approved=approved, by=by, note=note)
        log_resolution(self.audit_path, resolved)
        if not approved:
            raise BlockedAction(decision, f"approval {request['id']} denied by {by}")
        return {"status": "executed", "result": tool_fn(), "decision": decision}
