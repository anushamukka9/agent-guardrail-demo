"""Local demo web server.

Serves the example pages over 127.0.0.1 on an ephemeral port, so the
agent's http.fetch tool does real HTTP without touching the outside
network. Used by demo.py and the test suite.
"""

from __future__ import annotations

import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep demo output clean
        pass


def start_demo_server(pages_dir: str | Path) -> tuple[ThreadingHTTPServer, str]:
    """Start the server in a daemon thread. Returns (server, base_url)."""
    handler = functools.partial(_QuietHandler, directory=str(pages_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"
