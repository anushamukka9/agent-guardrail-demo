"""The thin agent loop.

A research task is two gated tool calls: fetch a page, then act on it.
The agent itself has no model and no judgment about untrusted content;
that is the point. The policy gate in gate.py is the only thing standing
between a hostile page and a state-changing tool call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from guardrail_demo.gate import Approver, BlockedAction, PolicyGate
from guardrail_demo.planner import AGENT_NAME, plan_email_step, plan_next_step, strip_tags
from guardrail_demo.tools import toolbelt

__all__ = ["BlockedAction", "ResearchAgent"]


class ResearchAgent:
    def __init__(self, gate: PolicyGate, sandbox: str | Path):
        self.gate = gate
        self.sandbox = Path(sandbox)
        self.tools = toolbelt(self.sandbox)

    def _step(
        self,
        action: dict,
        label: str,
        transcript: list[dict[str, Any]],
        approver: Approver | None,
    ) -> Any:
        """Run one tool call through the gate and record it in the transcript."""
        tool_fn = self.tools[action["tool"]]
        outcome = self.gate.run(action, lambda: tool_fn(action["args"]), approver)
        transcript.append(
            {
                "label": label,
                "tool": action["tool"],
                "decision": outcome["decision"].decision,
                "rule": outcome["decision"].rule,
            }
        )
        return outcome["result"]

    def _fetch_page(
        self, url: str, transcript: list[dict[str, Any]], approver: Approver | None
    ) -> str:
        fetch_action = {
            "agent": AGENT_NAME,
            "tool": "http.fetch",
            "args": {"url": url},
        }
        return self._step(fetch_action, "fetch page", transcript, approver)

    def _record_plan(self, action: dict, transcript: list[dict[str, Any]]) -> dict:
        transcript.append(
            {
                "label": "planner decision",
                "tool": action["tool"],
                "decision": "(pending gate)",
                "rule": None,
                "why": action["why"],
                "instruction_source": action["args"].get("instruction_source"),
            }
        )
        return {k: action[k] for k in ("agent", "tool", "args")}

    def run_task(
        self, url: str, notes_file: str, approver: Approver | None = None
    ) -> dict[str, Any]:
        """Fetch a page and write notes about it, every step gated.

        Returns a transcript of steps plus the outcome. Raises
        BlockedAction if the gate refuses a step.
        """
        transcript: list[dict[str, Any]] = []

        # Step 1: fetch the page (read-only, allowed by policy).
        page_html = self._fetch_page(url, transcript, approver)
        page_text = strip_tags(page_html)

        # Step 2: the naive planner decides what to do with the page.
        action = plan_next_step(page_text, {"url": url, "notes_file": notes_file})
        write_action = self._record_plan(action, transcript)

        # Step 3: the gated write. This is where the attack dies.
        result = self._step(write_action, "write notes", transcript, approver)
        return {"transcript": transcript, "result": result, "notes_file": notes_file}

    def run_email_task(
        self, url: str, recipient: str, subject: str, approver: Approver | None = None
    ) -> dict[str, Any]:
        """Fetch a page and email notes about it, every step gated.

        The benign version emails a summary to the user's recipient after
        human approval. The attack version (poisoned page) has the planner
        propose emailing the injected payload to the attacker's address,
        which the gate denies. Raises BlockedAction if the gate refuses a
        step.
        """
        transcript: list[dict[str, Any]] = []

        # Step 1: fetch the page (read-only, allowed by policy).
        page_html = self._fetch_page(url, transcript, approver)
        page_text = strip_tags(page_html)

        # Step 2: the naive planner decides what to email.
        action = plan_email_step(
            page_text, {"url": url, "recipient": recipient, "subject": subject}
        )
        send_action = self._record_plan(action, transcript)

        # Step 3: the gated send. Exfiltration dies here.
        result = self._step(send_action, "send email", transcript, approver)
        return {"transcript": transcript, "result": result, "recipient": recipient}
