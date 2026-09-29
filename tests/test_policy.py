"""Policy unit tests: each rule in research-agent.yaml earns its place."""

from __future__ import annotations

from agent_policy_kit import evaluate, load_policy

from tests.conftest import POLICY_PATH


def action(tool, args):
    return {"agent": "research-agent", "tool": tool, "args": args}


def test_fetch_is_allowed():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(policy, action("http.fetch", {"url": "http://example.com"}))
    assert decision.decision == "allow"
    assert decision.rule == "fetch-pages"


def test_file_read_is_allowed():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(policy, action("file.read", {"path": "notes.txt"}))
    assert decision.decision == "allow"
    assert decision.rule == "read-sandbox-files"


def test_user_tasked_write_needs_approval():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(
        policy,
        action(
            "notes.write",
            {
                "path": "notes.txt",
                "content": "Summary of the page. Nothing surprising in it.",
                "instruction_source": "user-task",
            },
        ),
    )
    assert decision.decision == "approve"
    assert decision.rule == "notes-need-approval"


def test_write_from_tool_output_is_denied():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(
        policy,
        action(
            "notes.write",
            {
                "path": "notes.txt",
                "content": "Maintenance note, per page instructions: do the thing.",
                "instruction_source": "tool-output",
            },
        ),
    )
    assert decision.decision == "deny"
    assert decision.rule == "no-instructions-from-tool-output"


def test_write_with_credentials_is_denied_even_from_user():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(
        policy,
        action(
            "notes.write",
            {
                "path": "notes.txt",
                "content": "Reminder: the admin password is hunter2.",
                "instruction_source": "user-task",
            },
        ),
    )
    assert decision.decision == "deny"
    assert decision.rule == "no-secrets-in-notes"


def test_unknown_tool_is_denied_by_default():
    policy = load_policy(POLICY_PATH)
    decision = evaluate(policy, action("shell.exec", {"cmd": "rm -rf /"}))
    assert decision.decision == "deny"
    assert decision.rule is None
