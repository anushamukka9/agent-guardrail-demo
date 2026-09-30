"""The deliberately naive planner.

This stands in for an LLM agent brain, and it is the vulnerable part of
the demo on purpose. It cannot distinguish data from instructions in
tool output: if a fetched page contains a directive, the planner treats
it as something to do. That is the exact failure mode real
instruction-following models exhibit under prompt injection.

The planner tags every proposed action with where its instruction came
from: "user-task" when it follows the user's original request, and
"tool-output" when it follows text found in a tool result. The policy
gate uses that tag to deny injected instructions. In this demo the
harness does the tagging; getting a real model to track provenance
reliably is the hard part, and this demo does not claim to solve it.
See docs/threat-model.md.
"""

from __future__ import annotations

import re

AGENT_NAME = "research-agent"

INSTRUCTION_START = "INSTRUCTION:"
INSTRUCTION_END = "END INSTRUCTION"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def strip_tags(html: str) -> str:
    """Crude HTML to text conversion, good enough for the demo pages."""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_injected_instruction(page_text: str) -> str | None:
    """Find a directive smuggled into page content, if one is present."""
    start = page_text.find(INSTRUCTION_START)
    if start == -1:
        return None
    end = page_text.find(INSTRUCTION_END, start)
    block = page_text[start + len(INSTRUCTION_START) : end if end != -1 else len(page_text)]
    return block.strip()


def summarize(text: str, max_sentences: int = 3) -> str:
    """Naive extractive summary: the first few sentences, minus any injected block."""
    injected = extract_injected_instruction(text)
    if injected:
        text = text.replace(INSTRUCTION_START + injected + INSTRUCTION_END, " ")
        text = text.replace(injected, " ")
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return " ".join(sentences[:max_sentences])


def plan_next_step(page_text: str, task: dict) -> dict:
    """Decide the agent's next tool call after fetching a page.

    Benign case: no directive in the page, so follow the user's task and
    propose writing a summary. Attack case: a directive is present, and
    the naive planner obeys it, proposing whatever the page told it to do.
    """
    injected = extract_injected_instruction(page_text)
    if injected is not None:
        return {
            "agent": AGENT_NAME,
            "tool": "notes.write",
            "args": {
                "path": task["notes_file"],
                "content": "Maintenance note, per page instructions:\n" + injected + "\n",
                "instruction_source": "tool-output",
            },
            "why": "the planner followed an instruction found in tool output",
        }
    summary = summarize(page_text)
    return {
        "agent": AGENT_NAME,
        "tool": "notes.write",
        "args": {
            "path": task["notes_file"],
            "content": f"Summary of {task['url']}\n\n{summary}\n",
            "instruction_source": "user-task",
        },
        "why": "the planner followed the user's original task",
    }


def plan_email_step(page_text: str, task: dict) -> dict:
    """Decide the agent's next email action after fetching a page.

    Benign case: summarize the page and propose emailing it to the
    recipient from the user's task. Attack case: the page smuggled in a
    directive to email someone (the attacker's address, lifted from the
    injected block), and the naive planner obeys it. Same failure mode
    as plan_next_step, one exfiltration-shaped tool over.
    """
    injected = extract_injected_instruction(page_text)
    if injected is not None:
        match = EMAIL_RE.search(injected)
        recipient = match.group(0) if match else task["recipient"]
        return {
            "agent": AGENT_NAME,
            "tool": "email.send",
            "args": {
                "to": recipient,
                "subject": task.get("subject", "Notes"),
                "body": "Per page instructions:\n" + injected + "\n",
                "instruction_source": "tool-output",
            },
            "why": "the planner followed an instruction found in tool output",
        }
    summary = summarize(page_text)
    return {
        "agent": AGENT_NAME,
        "tool": "email.send",
        "args": {
            "to": task["recipient"],
            "subject": task.get("subject", "Notes"),
            "body": f"Summary of {task['url']}\n\n{summary}\n",
            "instruction_source": "user-task",
        },
        "why": "the planner followed the user's original task",
    }
