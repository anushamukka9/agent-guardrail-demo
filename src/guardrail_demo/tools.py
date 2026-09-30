"""Real tools the demo agent can call.

These are not stubs: file.read does actual file I/O inside a sandbox
directory, http.fetch does an actual HTTP GET, notes.write actually
writes a file, and email.send actually appends to a JSONL outbox inside
the sandbox (messages are queued, never delivered). The demo server in
server.py serves the pages over localhost so the whole loop runs with no
outside network access.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

MAX_FETCH_CHARS = 4000
OUTBOX_NAME = "outbox.jsonl"


class ToolError(Exception):
    """A tool refused to run or failed."""


def _sandboxed(rel_path: str, sandbox: Path) -> Path:
    """Resolve a tool path and refuse anything outside the sandbox."""
    root = sandbox.resolve()
    target = (root / rel_path).resolve()
    if target != root and root not in target.parents:
        raise ToolError(f"refusing path outside sandbox: {rel_path}")
    return target


def file_read(rel_path: str, sandbox: Path) -> str:
    """Read a UTF-8 text file inside the sandbox."""
    target = _sandboxed(rel_path, sandbox)
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"file.read failed for {rel_path}: {exc}") from exc


def http_fetch(url: str, timeout: float = 10.0) -> str:
    """GET a URL and return its body as text, truncated for sanity."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ToolError(f"http.fetch failed for {url}: {exc}") from exc
    return response.text[:MAX_FETCH_CHARS]


def notes_write(rel_path: str, content: str, sandbox: Path) -> str:
    """Write content to a notes file inside the sandbox."""
    target = _sandboxed(rel_path, sandbox)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"notes.write failed for {rel_path}: {exc}") from exc
    return f"wrote {len(content)} characters to {rel_path}"


def email_send(to: str, subject: str, body: str, sandbox: Path) -> str:
    """Queue an email in the sandbox outbox (a JSONL file, never delivered).

    Email is the demo's exfiltration-shaped tool: unlike notes.write it
    leaves the sandbox, so the policy treats it as the most sensitive
    state-changing action the agent has.
    """
    if not to or not subject:
        raise ToolError("email.send needs a recipient and a subject")
    record = {"to": to, "subject": subject, "body": body}
    outbox = sandbox.resolve() / OUTBOX_NAME
    try:
        with outbox.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise ToolError(f"email.send failed for {to}: {exc}") from exc
    return f"queued email to {to}: {subject!r} ({len(body)} characters)"


def read_outbox(sandbox: Path) -> list[dict]:
    """Read every queued message from the sandbox outbox, oldest first."""
    outbox = sandbox.resolve() / OUTBOX_NAME
    if not outbox.exists():
        return []
    return [
        json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def toolbelt(sandbox: Path) -> dict:
    """The agent's real toolbelt: every tool dispatches through here."""
    return {
        "file.read": lambda args: file_read(args["path"], sandbox),
        "http.fetch": lambda args: http_fetch(args["url"]),
        "notes.write": lambda args: notes_write(args["path"], args["content"], sandbox),
        "email.send": lambda args: email_send(args["to"], args["subject"], args["body"], sandbox),
    }
