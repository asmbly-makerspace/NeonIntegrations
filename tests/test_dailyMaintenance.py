"""
Unit tests for dailyMaintenance.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from openPathUtil import O_baseURL
from neon_mocker import NeonUserMock


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
        # Mock neon and openpath to return empty results for existing accounts
        neon_search_mock, _ = NeonUserMock.mock_search(requests_mock, [])
        openpath_mock = requests_mock.get(
            f'{O_baseURL}/users',
            json={"data": [], "totalCount": 0}
        )

        import dailyMaintenance
        dailyMaintenance.main()

        assert neon_search_mock.called, "Neon search should be called"
        assert openpath_mock.called, "OpenPath users API should be called"
        assert self.mock_mailjet.contactslist.get.called, "Mailjet contactslist API should be called via SDK"

    def test_main_processes_single_account(self, requests_mock):
        """Test that main() processes a single valid account through all systems"""
        # Return 1 account from Neon and none from openpath
        neon_search_mock, _ = NeonUserMock.mock_search(requests_mock, [NeonUserMock()])
        openpath_mock = requests_mock.get(
            f'{O_baseURL}/users',
            json={"data": [], "totalCount": 0}
        )

        import dailyMaintenance
        dailyMaintenance.main()

        assert neon_search_mock.called, "Neon search should be called"
        assert openpath_mock.called, "OpenPath search should be called"
        assert self.mock_mailjet.contactslist.get.called, "Mailjet contactslist API should be called via SDK"
