from unittest.mock import patch, MagicMock
import sys
import pytest

# Inject mocked config.py (not committed since it contains secrets)
sys.modules['config'] = MagicMock()

# Unit tests should not access the network
@pytest.fixture(autouse=True)
def _no_network():
    with patch("socket.socket", side_effect=RuntimeError("Network disabled in tests")):
        yield
