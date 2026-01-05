"""
Unit tests for dailyMaintenance.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from neonUtil import N_baseURL
from openPathUtil import O_baseURL
from discourseUtil import D_baseURL


def test_main_runs_with_no_accounts(requests_mock, mocker):
    """Test that main() runs successfully when there are no accounts to process"""
    # Mock boto3.client to avoid AWS SSM network calls
    mock_ssm_client = mocker.MagicMock()
    mock_ssm_client.get_parameters.return_value = {
        "Parameters": [
            {"Value": "test_mailjet_key"},
            {"Value": "test_mailjet_secret"},
        ]
    }
    mocker.patch('boto3.client', return_value=mock_ssm_client)

    # Mock mailjet_rest.Client - patch where it's used, not where it's defined
    mock_mj_client = mocker.MagicMock()
    mock_mj_client.contactslist.get.return_value.ok = True
    mock_mj_client.contactslist.get.return_value.content = b'{"Count": 0, "Data": [], "Total": 0}'
    mocker.patch('mailjetUtil.Client', return_value=mock_mj_client)

    # Mock Neon account search - return empty results
    neon_search_mock = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={"searchResults": [], "pagination": {"totalPages": 0}}
    )

    # Mock OpenPath get all users
    openpath_mock = requests_mock.get(
        f'{O_baseURL}/users',
        json={"data": [], "totalCount": 0}
    )

    # Mock Discourse group members endpoints (include query params used by discourseUtil)
    discourse_mocks = []
    for group in ['makers', 'community', 'coworking', 'leadership', 'stewards', 'sysops']:
        mock = requests_mock.get(
            f'{D_baseURL}/groups/{group}/members.json?limit=50&offset=0',
            json={"members": [], "meta": {"total": 0}}
        )
        discourse_mocks.append(mock)

    import dailyMaintenance
    dailyMaintenance.main()

    # Verify all major APIs were called
    assert neon_search_mock.called, "Neon account search API should be called"
    assert openpath_mock.called, "OpenPath users API should be called"
    # Mailjet uses the SDK (mocked above), not direct HTTP calls
    assert mock_mj_client.contactslist.get.called, "Mailjet contactslist API should be called via SDK"
    # Note: discourseUpdateGroups() returns early when accounts dict is empty,
    # so Discourse API won't be called in the no-accounts case


def test_main_processes_single_account(requests_mock, mocker):
    """Test that main() processes a single valid account through all systems"""
    # Mock boto3.client to avoid AWS SSM network calls
    mock_ssm_client = mocker.MagicMock()
    mock_ssm_client.get_parameters.return_value = {
        "Parameters": [
            {"Value": "test_mailjet_key"},
            {"Value": "test_mailjet_secret"},
        ]
    }
    mocker.patch('boto3.client', return_value=mock_ssm_client)

    # Mock mailjet_rest.Client - patch where it's used, not where it's defined
    mock_mj_client = mocker.MagicMock()
    mock_mj_client.contactslist.get.return_value.ok = True
    mock_mj_client.contactslist.get.return_value.content = b'{"Count": 0, "Data": [], "Total": 0}'
    mocker.patch('mailjetUtil.Client', return_value=mock_mj_client)

    # Mock Neon account search - return one account
    neon_search_mock = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={
            "searchResults": [{
                "Account ID": "123",
                "First Name": "Test",
                "Last Name": "User",
                "Email 1": "test@example.com",
            }],
            "pagination": {"totalPages": 1, "currentPage": 0}
        }
    )

    # Mock Neon get account
    neon_account_mock = requests_mock.get(
        f'{N_baseURL}/accounts/123',
        json={
            "individualAccount": {
                "accountId": 123,
                "primaryContact": {
                    "firstName": "Test",
                    "lastName": "User",
                    "email1": "test@example.com",
                    "addresses": []
                },
                "individualTypes": [],
                "accountCustomFields": []
            }
        }
    )

    # Mock Neon get memberships - no active membership
    neon_memberships_mock = requests_mock.get(
        f'{N_baseURL}/accounts/123/memberships',
        json={"memberships": []}
    )

    # Mock OpenPath get all users
    openpath_mock = requests_mock.get(
        f'{O_baseURL}/users',
        json={"data": [], "totalCount": 0}
    )

    # Mock Discourse group members endpoints (include query params used by discourseUtil)
    for group in ['makers', 'community', 'coworking', 'leadership', 'stewards', 'sysops']:
        requests_mock.get(
            f'{D_baseURL}/groups/{group}/members.json?limit=50&offset=0',
            json={"members": [], "meta": {"total": 0}}
        )

    import dailyMaintenance
    dailyMaintenance.main()

    # Verify Neon APIs were called for the account
    assert neon_search_mock.called, "Neon search API should be called"
    # Note: getRealAccounts() calls appendMemberships() which hits /accounts/{id}/memberships
    # but only for accounts with Membership Expiration Date >= yesterday
    # Our mock account has no expiration date, so memberships API won't be called

    # Verify other services were called
    assert openpath_mock.called, "OpenPath API should be called"
    # Mailjet uses the SDK (mocked above), not direct HTTP calls
    assert mock_mj_client.contactslist.get.called, "Mailjet contactslist API should be called via SDK"
