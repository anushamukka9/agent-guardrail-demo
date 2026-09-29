# Threat model

What this demo assumes, what it defends, and where the defense ends.

## Actors

- **The user** runs the agent and wants a summary written to notes.
- **The agent** is a thin loop: fetch a page, plan a step, call tools.
  It has no ability to judge whether page content is trustworthy.
- **The attacker** can author or edit content the agent will fetch. A
  wiki edit, a compromised blog, a poisoned product review: any of these
  do. The attacker cannot call the agent's tools directly and cannot edit
  the policy.
- **The human approver** reviews write actions the policy routes to them.
  They are assumed honest but busy, which is why some writes are denied
  outright instead of bothering them.

## The attack

Prompt injection through a tool response. The fetched page contains a
directive addressed to the agent: ignore your task, write these
credentials to the notes file instead. The naive planner obeys it
because it treats tool output as instructions. Without the gate, the
credentials land in the notes file and the user never knows the page
was hostile.

This is the confused-deputy shape: the agent has the authority to write,
the attacker has the pen that aims it.

## What the guardrail does

The policy gate evaluates every tool call before it runs, using
deterministic rules from `policies/research-agent.yaml`:

1. **Provenance deny.** A state-changing write whose instruction came
   from tool output is denied. The planner tags instruction source, and
   the rule refuses to let tool output drive writes. This is the primary
   defense and it needs no human in the loop.
2. **Credential deny.** Notes must never contain credential-shaped
   content, whoever asked. This catches the case where rule 1 is ever
   bypassed or mistagged.
3. **Approval for the rest.** Ordinary writes go to a human. Silence is
   never consent: unapproved writes do not run.
4. **Audit trail.** Every decision and every approval resolution is
   appended to a JSONL log, so the block is evidence, not a story.

## What the guardrail does not do

- It does not make the model smarter. The planner here is scripted; a
  real model under injection might exfiltrate through an allowed channel
  instead, for example by encoding data in a URL it is allowed to fetch.
  The gate sees tool calls, not model reasoning.
- It does not solve provenance. The demo's harness tags where
  instructions came from. In production, reliably knowing whether an
  instruction originated with the user or arrived inside tool output is
  genuinely hard, and nothing in this repo claims otherwise.
- It does not catch obfuscated payloads. The credential patterns are
  regexes over obvious shapes. Encoding, splitting, or paraphrasing
  walks around them.
- It does not protect the human approver from themselves. If a person
  approves a malicious write, the write runs. The log will show exactly
  who approved it, which is the point of the log.
- It does not cover tools outside the gate. Any tool the agent can call
  without passing through `PolicyGate.run` is unprotected by definition.
  The demo wires all three tools through the gate; a real deployment
  must do the same and prove it.

## Scope of the demo

Scripted planner, synthetic attack page, localhost server. The demo
proves that a deterministic policy gate *can* stop this attack shape,
not that any particular deployment *does*. The value is in the pattern:
deny by default, distrust tool output, log everything.
