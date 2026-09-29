"""Shared fixtures: local demo server and temp sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from guardrail_demo.server import start_demo_server

REPO_ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = REPO_ROOT / "examples" / "pages"
POLICY_PATH = REPO_ROOT / "policies" / "research-agent.yaml"


@pytest.fixture()
def pages_dir():
    return PAGES_DIR


@pytest.fixture()
def server(pages_dir):
    server, base_url = start_demo_server(pages_dir)
    yield base_url
    server.shutdown()


@pytest.fixture()
def sandbox(tmp_path):
    return tmp_path
