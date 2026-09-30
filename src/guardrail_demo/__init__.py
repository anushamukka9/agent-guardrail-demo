"""agent-guardrail-demo: a thin research agent protected by agent-policy-kit.

The demo runs a small agent with real tools (file reader, HTTP fetcher,
notes writer, sandboxed email sender) behind a policy gate. Benign tasks
complete with human approval; injected instructions smuggled into fetched
pages are denied and logged.
"""

__version__ = "0.1.0"
