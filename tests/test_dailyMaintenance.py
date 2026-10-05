"""
Unit tests for dailyMaintenance.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
import requests
from openPathUtil import O_baseURL
from discourseUtil import D_baseURL, GROUP_IDS, USERS_PER_PAGE
from neonUtil import MEMBERSHIP_ID_REGULAR, N_baseURL
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

    def test_discourse_id_is_assigned_before_the_group_sync(self, requests_mock):
        """The ID reconciliation runs first and writes back into neonAccounts in place,
        so a member linked this cycle is already eligible for Makers this cycle."""
        from neonUtil import N_baseURL

        member = NeonUserMock(5001, email='bob@example.com').add_membership(
            MEMBERSHIP_ID_REGULAR, today_plus(-365), today_plus(365), fee=100.0)
        NeonUserMock.mock_search(requests_mock, [member])
        requests_mock.get(f'{O_baseURL}/users', json={"data": [], "totalCount": 0})
        requests_mock.get(f'{D_baseURL}/admin/users/list/active.json?page=0&show_emails=true',
            json=[{"username": "BobS", "name": "Bob Smith", "email": "bob@example.com"}])
        neonPatch = requests_mock.patch(f'{N_baseURL}/accounts/5001', json={})
        addMakers = requests_mock.put(f'{D_baseURL}/groups/{GROUP_IDS["makers"]}/members.json',
            json={"success": "OK", "usernames": [], "emails": []})
        requests_mock.delete(f'{D_baseURL}/groups/{GROUP_IDS["community"]}/members.json',
            json={"success": "OK", "usernames": [], "skipped_usernames": []})

        import dailyMaintenance
        dailyMaintenance.main()

        # the DiscourseID was written to Neon...
        assert neonPatch.called
        assert neonPatch.last_request.json()["individualAccount"]["accountCustomFields"][0]["value"] == "bobs"
        # ...and the group sync picked it up in the same run
        assert addMakers.last_request.body == "usernames=bobs"

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
        requests_mock.get(f'{D_baseURL}/groups/stewards/members.json?limit={USERS_PER_PAGE}&offset=0',
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

    def test_openpath_failure_does_not_skip_the_later_phases(self, requests_mock):
        """An OpenPath error used to end the run before Discourse and Mailjet were
        synced. The later phases should still run, and the run should exit non-zero."""
        NeonUserMock.mock_search(requests_mock, [NeonUserMock()])
        requests_mock.get(f'{O_baseURL}/users', status_code=503)

        import dailyMaintenance
        with pytest.raises(SystemExit) as excinfo:
            dailyMaintenance.main()

        assert excinfo.value.code == 1
        assert self.mock_discourse['users'].called, "DiscourseID sync should still run"
        assert self.mock_discourse['makers'].called, "Discourse group sync should still run"
        assert self.mock_mailjet.contactslist.get.called, "Mailjet sync should still run"

    def test_discourse_failure_does_not_skip_mailjet(self, requests_mock):
        """Discourse logs bad status codes itself, but a dropped connection raises."""
        NeonUserMock.mock_search(requests_mock, [NeonUserMock()])
        requests_mock.get(f'{O_baseURL}/users', json={"data": [], "totalCount": 0})
        requests_mock.get(f'{D_baseURL}/groups/makers/members.json?limit={USERS_PER_PAGE}&offset=0',
            exc=requests.exceptions.ConnectionError)

        import dailyMaintenance
        with pytest.raises(SystemExit) as excinfo:
            dailyMaintenance.main()

        assert excinfo.value.code == 1
        assert self.mock_mailjet.contactslist.get.called, "Mailjet sync should still run"

    def test_openpath_account_failures_fail_the_run(self, requests_mock, mocker):
        """openPathUpdateAll may report the accounts it couldn't update instead of
        raising. That should still mark the run as failed."""
        import dailyMaintenance
        NeonUserMock.mock_search(requests_mock, [NeonUserMock()])
        # only whether the list is empty matters here, not what is in it
        mocker.patch.object(dailyMaintenance, 'openPathUpdateAll', return_value=["1234"])

        with pytest.raises(SystemExit) as excinfo:
            dailyMaintenance.main()

        assert excinfo.value.code == 1
        assert self.mock_mailjet.contactslist.get.called, "Mailjet sync should still run"

    def test_neon_fetch_failure_stops_before_any_sync(self, requests_mock):
        """Without the complete account list nothing is safe to sync: a member whose
        record failed to load would look expired and lose door access."""
        member = NeonUserMock(5001).add_membership(
            MEMBERSHIP_ID_REGULAR, today_plus(-365), today_plus(365), fee=100.0)
        NeonUserMock.mock_search(requests_mock, [member])
        requests_mock.get(f'{N_baseURL}/accounts/5001/memberships', status_code=500)
        openpath_mock = requests_mock.get(f'{O_baseURL}/users', json={"data": [], "totalCount": 0})

        import dailyMaintenance
        with pytest.raises(SystemExit) as excinfo:
            dailyMaintenance.main()

        assert excinfo.value.code == 1
        assert not openpath_mock.called
        assert not self.mock_discourse['users'].called
        assert not self.mock_discourse['makers'].called
        assert not self.mock_mailjet.contactslist.get.called
