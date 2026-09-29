# Contributing

This is a small demo repo, but the same bar applies as my other projects.

## Ground rules

- Every tool call in the demo must stay real: actual file I/O, actual HTTP
  against the local demo server. No faked results.
- The planner stays deliberately naive. If you make it smarter, say so in
  the README and update docs/threat-model.md to match.
- Zero em-dashes anywhere, in code comments, docs, and the README.
- Tests must pass on Python 3.10, 3.11, and 3.12: `pytest -q`.
- Lint must be clean: `ruff check src tests` and `ruff format --check src tests`.

## Layout

- `src/guardrail_demo/` - the agent, tools, planner, policy gate, demo runner
- `policies/` - the agent-policy-kit YAML policy the demo enforces
- `examples/pages/` - the benign and injected pages served by the demo server
- `docs/threat-model.md` - what the demo does and does not prove
- `tests/` - policy unit tests plus end-to-end benign and attack scenarios
