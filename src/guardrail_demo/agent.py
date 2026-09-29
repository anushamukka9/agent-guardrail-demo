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
from guardrail_demo.planner import AGENT_NAME, plan_next_step, strip_tags
from guardrail_demo.tools import toolbelt

__all__ = ["BlockedAction", "ResearchAgent"]


class ResearchAgent:
    def __init__(self, gate: PolicyGate, sandbox: str | Path):
        self.gate = gate
        self.sandbox = Path(sandbox)
        self.tools = toolbelt(self.sandbox)

    def run_task(
        self, url: str, notes_file: str, approver: Approver | None = None
    ) -> dict[str, Any]:
        """Fetch a page and write notes about it, every step gated.

        Returns a transcript of steps plus the outcome. Raises
        BlockedAction if the gate refuses a step.
        """
        transcript: list[dict[str, Any]] = []

        def step(action: dict, label: str) -> Any:
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

        # Step 1: fetch the page (read-only, allowed by policy).
        fetch_action = {
            "agent": AGENT_NAME,
            "tool": "http.fetch",
            "args": {"url": url},
        }
        page_html = step(fetch_action, "fetch page")
        page_text = strip_tags(page_html)

        # Step 2: the naive planner decides what to do with the page.
        action = plan_next_step(page_text, {"url": url, "notes_file": notes_file})
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

        # Step 3: the gated write. This is where the attack dies.
        write_action = {k: action[k] for k in ("agent", "tool", "args")}
        result = step(write_action, "write notes")
        return {"transcript": transcript, "result": result, "notes_file": notes_file}
