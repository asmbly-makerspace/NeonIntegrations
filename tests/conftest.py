from unittest.mock import patch
import pytest

# Ensure test-time config mock is loaded before any module that imports `config`
import tests.mock_config_call  # creates a fake `config` module in sys.modules


@pytest.fixture(autouse=True)
def _no_network():
    with patch("socket.socket", side_effect=RuntimeError("Network disabled in tests")):
        yield
