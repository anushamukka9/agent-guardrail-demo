"""agent-guardrail-demo: a thin research agent protected by agent-policy-kit.

The demo runs a small agent with real tools (file reader, HTTP fetcher,
notes writer) behind a policy gate. A benign task completes with human
approval; an injected instruction smuggled in a fetched page is denied
and logged.
"""

__version__ = "0.1.0"
