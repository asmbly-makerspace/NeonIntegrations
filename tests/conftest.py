from unittest.mock import patch, MagicMock, mock_open
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


# ============================================================================
# Shared fixtures for mocking external services
# ============================================================================

@pytest.fixture
def mock_ssm(mocker):
    """Mock AWS SSM client used by mailjetUtil for fetching API keys."""
    mock_ssm_client = mocker.MagicMock()
    mock_ssm_client.get_parameters.return_value = {
        "Parameters": [
            {"Value": "test_mailjet_key"},
            {"Value": "test_mailjet_secret"},
        ]
    }
    mocker.patch('boto3.client', return_value=mock_ssm_client)
    return mock_ssm_client


@pytest.fixture
def mock_mailjet(mocker):
    """Mock Mailjet REST client."""
    mock_mj_client = mocker.MagicMock()
    mock_mj_client.contactslist.get.return_value.ok = True
    mock_mj_client.contactslist.get.return_value.content = b'{"Count": 0, "Data": [], "Total": 0}'
    mocker.patch('mailjetUtil.Client', return_value=mock_mj_client)
    return mock_mj_client


@pytest.fixture
def mock_smtp(mocker):
    """Mock SMTP for email sending."""
    mock_smtp_instance = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp_instance)
    mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_instance.__exit__ = MagicMock(return_value=False)
    return mock_smtp_instance


@pytest.fixture
def mock_google_apis(mocker):
    """Mock Google Drive and Forms APIs."""
    # Mock credentials file read
    mocker.patch('builtins.open', mock_open(read_data='{}'))

    # Mock Google credentials
    mock_creds = MagicMock()
    mock_creds.with_subject.return_value = mock_creds
    mocker.patch(
        'google.oauth2.service_account.Credentials.from_service_account_file',
        return_value=mock_creds
    )

    # Mock Google API service builders
    mock_drive_service = MagicMock()
    mock_forms_service = MagicMock()

    def mock_build(service_name, version, credentials):
        if service_name == "drive":
            return mock_drive_service
        elif service_name == "forms":
            return mock_forms_service
        return MagicMock()

    mocker.patch('googleapiclient.discovery.build', side_effect=mock_build)

    return {
        'credentials': mock_creds,
        'drive': mock_drive_service,
        'forms': mock_forms_service,
    }


@pytest.fixture
def mock_discourse(requests_mock):
    """Mock Discourse API group member endpoints with empty responses."""
    from discourseUtil import D_baseURL

    groups = ['makers', 'community', 'coworking', 'leadership', 'stewards', 'sysops']
    mocks = {}
    for group in groups:
        mocks[group] = requests_mock.get(
            f'{D_baseURL}/groups/{group}/members.json?limit=50&offset=0',
            json={"members": [], "meta": {"total": 0}}
        )
    return mocks
