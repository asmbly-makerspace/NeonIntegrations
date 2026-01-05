"""
Unit tests for dailyMaintenance.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from neonUtil import N_baseURL
from openPathUtil import O_baseURL


class TestDailyMaintenance:
    """Test suite for dailyMaintenance.main()"""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_ssm, mock_mailjet, mock_discourse):
        """Setup SSM, Mailjet, and Discourse mocks for all tests in this class."""
        self.mock_ssm = mock_ssm
        self.mock_mailjet = mock_mailjet
        self.mock_discourse = mock_discourse

    def test_main_runs_with_no_accounts(self, requests_mock):
        """Test that main() runs successfully when there are no accounts to process"""
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

        import dailyMaintenance
        dailyMaintenance.main()

        # Verify all major APIs were called
        assert neon_search_mock.called, "Neon account search API should be called"
        assert openpath_mock.called, "OpenPath users API should be called"
        # Mailjet uses the SDK (mocked above), not direct HTTP calls
        assert self.mock_mailjet.contactslist.get.called, "Mailjet contactslist API should be called via SDK"
        # Note: discourseUpdateGroups() returns early when accounts dict is empty,
        # so Discourse API won't be called in the no-accounts case

    def test_main_processes_single_account(self, requests_mock):
        """Test that main() processes a single valid account through all systems"""
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
        requests_mock.get(
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
        requests_mock.get(
            f'{N_baseURL}/accounts/123/memberships',
            json={"memberships": []}
        )

        # Mock OpenPath get all users
        openpath_mock = requests_mock.get(
            f'{O_baseURL}/users',
            json={"data": [], "totalCount": 0}
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
        assert self.mock_mailjet.contactslist.get.called, "Mailjet contactslist API should be called via SDK"
