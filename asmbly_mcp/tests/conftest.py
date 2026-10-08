import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# These tests are collected two ways: by this folder's own project (see ../pyproject.toml)
# and by the repo-wide `python -m pytest` in CI. Make the repo root and the shared Neon
# mock helpers importable either way.
REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Same fake keys as tests/conftest.py, so neonUtil and openPathUtil import without real ones
FAKE_KEYS = SimpleNamespace(
    N_APIkey="test_neon_key",
    N_APIuser="test_neon_user",
    D_APIkey="test_discourse_key",
    D_APIuser="test_discourse_user",
    O_APIkey="test_openpath_key",
    O_APIuser="test_openpath_user",
    G_user="test_gmail_user@test.com",
    G_password="test_gmail_password",
)
sys.modules.setdefault("config", FAKE_KEYS)
sys.modules.setdefault("aws_ssm", FAKE_KEYS)


# Unit tests should not access the network. Blocking connect (not socket creation)
# leaves the event loop used by the async tests working.
@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("Network disabled in tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)
