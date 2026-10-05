"""
Tests for the real aws_ssm.py (conftest.py stubs it out) and
mailjetUtil.get_mailjet_credentials, with boto3.client patched.
"""

import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

import mailjetUtil
from mailjetUtil import MJCredentials

REPO_ROOT = Path(__file__).parent.parent

# lambda_function lives in alta_open_lambda/, which is not a package
sys.path.insert(0, str(REPO_ROOT / "alta_open_lambda"))

import lambda_function as lf


# Parameters aws_ssm.py requests, in alphabetical order
SSM_VALUES = {
    "/altaopen/api_key": "altaopen-key",
    "/altaopen/api_user": "altaopen-user",
    "/discourse/api_key": "discourse-key",
    "/discourse/api_user": "discourse-user",
    "/gmail/password": "gmail-password",
    "/gmail/user": "gmail-user",
    "/neon/api_key": "neon-key",
    "/neon/api_user": "neon-user",
}

# aws_ssm export -> SSM parameter
AWS_SSM_EXPORTS = {
    "N_APIkey": "/neon/api_key",
    "N_APIuser": "/neon/api_user",
    "G_user": "/gmail/user",
    "G_password": "/gmail/password",
    "O_APIkey": "/altaopen/api_key",
    "O_APIuser": "/altaopen/api_user",
    "D_APIkey": "/discourse/api_key",
    "D_APIuser": "/discourse/api_user",
}

MAILJET_VALUES = {
    "/mailjet/api_key": "mailjet-public-key",
    "/mailjet/api_secret": "mailjet-secret-key",
}
MAILJET_CREDENTIALS = MJCredentials(
    public_key="mailjet-public-key", secret_key="mailjet-secret-key"
)


class _StopHere(Exception):
    """Raised by the patched MJService to stop the run."""


def ssm_response(values, invalid=()):
    """Fake GetParameters response."""
    return {
        "Parameters": [{"Name": name, "Value": value} for name, value in values.items()],
        "InvalidParameters": list(invalid),
    }


def mock_ssm_client(mocker, response):
    client = mocker.MagicMock()
    client.get_parameters.return_value = response
    mocker.patch("boto3.client", return_value=client)
    return client


def load_real_aws_ssm():
    """Run aws_ssm.py as a new module, bypassing the conftest stub."""
    spec = importlib.util.spec_from_file_location(
        "aws_ssm_under_test", REPO_ROOT / "aws_ssm.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reversed_order(values):
    return dict(reversed(list(values.items())))


# ============================================================================
# aws_ssm.py
# ============================================================================

@pytest.mark.parametrize("order", [dict, reversed_order], ids=["alphabetical", "reversed"])
def test_aws_ssm_reads_each_secret_by_name(mocker, order):
    client = mock_ssm_client(mocker, ssm_response(order(SSM_VALUES)))

    aws_ssm = load_real_aws_ssm()

    for export, parameter in AWS_SSM_EXPORTS.items():
        assert getattr(aws_ssm, export) == SSM_VALUES[parameter], export

    client.get_parameters.assert_called_once()
    kwargs = client.get_parameters.call_args.kwargs
    assert sorted(kwargs["Names"]) == sorted(SSM_VALUES)
    assert kwargs["WithDecryption"] is True


def test_aws_ssm_missing_parameters_fail_naming_them(mocker):
    missing = ["/gmail/password", "/neon/api_user"]
    found = {name: value for name, value in SSM_VALUES.items() if name not in missing}
    mock_ssm_client(mocker, ssm_response(found, invalid=missing))

    with pytest.raises(RuntimeError, match="SSM parameter") as excinfo:
        load_real_aws_ssm()

    message = str(excinfo.value)
    for name in missing:
        assert name in message
    # Names only, never secret values
    for value in found.values():
        assert value not in message


# ============================================================================
# Mailjet credentials (mailjetUtil.get_mailjet_credentials)
# ============================================================================

def test_daily_maintenance_reads_mailjet_credentials_by_name(mocker):
    mock_ssm_client(mocker, ssm_response(reversed_order(MAILJET_VALUES)))
    mj_service = mocker.patch.object(mailjetUtil, "MJService", side_effect=_StopHere)

    with pytest.raises(_StopHere):
        mailjetUtil.run_mailjet_maintenance()

    mj_service.assert_called_once_with(MAILJET_CREDENTIALS)


def test_lambda_reads_mailjet_credentials_by_name(mocker):
    mock_ssm_client(mocker, ssm_response(reversed_order(MAILJET_VALUES)))
    mj_service = mocker.patch.object(lf, "MJService", side_effect=_StopHere)
    account = {
        "Account ID": "123",
        "FacilityTourDate": "01/02/2026",
        "Email 1": "member@example.com",
        "First Name": "Test",
        "Last Name": "Member",
        "MailjetContactID": "456",
    }

    with pytest.raises(_StopHere):
        lf.add_member_to_mailjet(account, [datetime.date(2027, 1, 2)])

    mj_service.assert_called_once_with(MAILJET_CREDENTIALS)


def test_missing_mailjet_parameter_fails_naming_it(mocker):
    found = {"/mailjet/api_key": "mailjet-public-key"}
    mock_ssm_client(mocker, ssm_response(found, invalid=["/mailjet/api_secret"]))
    mj_service = mocker.patch.object(mailjetUtil, "MJService")

    with pytest.raises(RuntimeError, match="/mailjet/api_secret") as excinfo:
        mailjetUtil.run_mailjet_maintenance()

    assert "mailjet-public-key" not in str(excinfo.value)
    mj_service.assert_not_called()
