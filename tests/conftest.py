from unittest.mock import patch
import pytest


@pytest.fixture(autouse=True)
def _no_network():
    with patch("socket.socket", side_effect=RuntimeError("Network disabled in tests")):
        yield
