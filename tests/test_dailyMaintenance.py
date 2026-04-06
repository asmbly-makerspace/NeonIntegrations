"""
Unit tests for dailyMaintenance.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from openPathUtil import O_baseURL
from discourseUtil import D_baseURL, GROUP_IDS
from neonUtil import MEMBERSHIP_ID_REGULAR
from neon_mocker import NeonUserMock, today_plus


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

    def test_discourse_case_mismatch_does_not_cause_churn(self, requests_mock):
        """Discourse usernames are case-insensitive. A steward stored in Neon as
        'BobSmith' who appears in Discourse as 'bobsmith' should not be
        removed and re-added every sync cycle."""
        start = today_plus(-365)
        end = today_plus(365)
        steward = lambda id, did: NeonUserMock(
            id,
            individualTypes=['Steward'],
            custom_fields={'DiscourseID': did},
        ).add_membership(MEMBERSHIP_ID_REGULAR, start, end, fee=100.0)

        NeonUserMock.mock_search(requests_mock, [
            steward(1, 'BobSmith'),    # case mismatch with Discourse
            steward(2, 'janedoe'),     # consistent with Discourse
            steward(3, 'newsteward'),  # not yet in Discourse group
        ])
        requests_mock.get(f'{O_baseURL}/users', json={"data": [], "totalCount": 0})
        requests_mock.get(f'{D_baseURL}/groups/stewards/members.json?limit=50&offset=0',
            json={"members": [{"username": "bobsmith", "name": "Bob Smith"},
                              {"username": "janedoe", "name": "Jane Doe"}],
                  "meta": {"total": 2}})
        modify = {}
        for name, gid in GROUP_IDS.items():
            modify[f'add_{name}'] = requests_mock.put(f'{D_baseURL}/groups/{gid}/members.json',
                json={"success": "OK", "usernames": [], "emails": []})
            modify[f'rm_{name}'] = requests_mock.delete(f'{D_baseURL}/groups/{gid}/members.json',
                json={"success": "OK", "usernames": [], "skipped_usernames": []})

        import dailyMaintenance
        dailyMaintenance.main()

        # only the newsteward is added, not BobSmith
        assert modify['add_stewards'].last_request.body == "usernames=newsteward"
        assert not modify['rm_stewards'].called
