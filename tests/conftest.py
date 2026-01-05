from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import sys
import pytest

# Inject mocked config.py (not committed since it contains secrets)
# Use actual string values so they work as HTTP headers
sys.modules['config'] = SimpleNamespace(
    N_APIkey="test_neon_key",
    N_APIuser="test_neon_user",
    D_APIkey="test_discourse_key",
    D_APIuser="test_discourse_user",
    O_APIkey="test_openpath_key",
    O_APIuser="test_openpath_user",
    G_user="test_gmail_user@test.com",
    G_password="test_gmail_password",
)

# Also mock aws_ssm.py which is used in EC2/Lambda environments
# This prevents boto3 from trying to hit AWS SSM at import time
sys.modules['aws_ssm'] = SimpleNamespace(
    N_APIkey="test_neon_key",
    N_APIuser="test_neon_user",
    D_APIkey="test_discourse_key",
    D_APIuser="test_discourse_user",
    O_APIkey="test_openpath_key",
    O_APIuser="test_openpath_user",
    G_user="test_gmail_user@test.com",
    G_password="test_gmail_password",
)

# Unit tests should not access the network
@pytest.fixture(autouse=True)
def _no_network():
    with patch("socket.socket", side_effect=RuntimeError("Network disabled in tests")):
        yield
