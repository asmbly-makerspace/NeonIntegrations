import pytest
from datetime import datetime, timezone

from openPathUpdateAll import openPathUpdateAll
from neonUtil import MEMBERSHIP_ID_REGULAR, MEMBERSHIP_ID_CERAMICS, ACCOUNT_FIELD_OPENPATH_ID, N_baseURL
from openPathUtil import GROUP_SUBSCRIBERS, O_baseURL

from tests.neon_mocker import NeonMock, today_plus, assert_history


NEON_ID = 123
ALTA_ID = 456
CRED_ID = 789


REGULAR = MEMBERSHIP_ID_REGULAR
CERAMICS = MEMBERSHIP_ID_CERAMICS


def build_alta_user(alta_id, groups=None):
    return {
        'OpenPathID': alta_id,
        'name': "John Doe",
        'email': "john@example.com",
        'groups': groups,
    }


class TestOpenPathUpdateAll:

    @pytest.fixture
    def setup_mocks(self, mocker):
        return {
            'getAllUsers': mocker.patch('openPathUtil.getAllUsers'),
            'updateGroups': mocker.patch('openPathUtil.updateGroups'),
            'createUser': mocker.patch('openPathUtil.createUser'),
            'createMobileCredential': mocker.patch('openPathUtil.createMobileCredential'),
        }

    def test_update_all_basic(self, requests_mock, mocker, setup_mocks):
        """Test basic bulk update with users that have existing OpenPathIDs"""
        # Create Alta accounts with different groups
        test_groups = (['test_group'], ['test_group_2'])
        alta_accounts = {
            i+1: build_alta_user(i+1, groups)
            for i, groups in enumerate(test_groups)
        }

        # Create matching Neon accounts with OpenPathIDs
        neon_accounts = {}
        for i, (alta_id, groups) in enumerate(zip(alta_accounts.keys(), test_groups), start=1):
            account_id = str(i)
            neon_accounts[account_id] = NeonMock(
                account_id, firstName=f"User{i}", lastName=f"Test{i}",
                email=f"user{i}@example.com", open_path_id=alta_id
            ).mock(requests_mock)

        # When `openPathUtil.getAllUsers()` is called, return our fake accounts
        setup_mocks['getAllUsers'].return_value = alta_accounts

        # Run the openPathUpdateAll script with our fake accounts.
        openPathUpdateAll(neon_accounts)

        # Verify that openPathUtil.updateGroups was called with the correct arguments
        expected_calls = [
            mocker.call(neon_acct, openPathGroups=group_list)
            for neon_acct, group_list
            in zip(neon_accounts.values(), test_groups)
        ]
        setup_mocks['updateGroups'].assert_has_calls(expected_calls)

    def test_bulk_update_with_mixed_membership_types(self, requests_mock, mocker, setup_mocks):
        """Test bulk update with mix of paid regular, paid ceramics, and comped users"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        accounts = [
            # User 1: Paid regular membership with facility access
            (
                NeonMock(1001, "Alice", open_path_id=2001, waiver_date=start, facility_tour_date=tour)\
                    .add_membership(REGULAR, start, end)\
                    .mock(requests_mock),
                build_alta_user(2001, ['facility_access']),
            ),

            # User 2: Paid ceramics membership with facility access
            (
                NeonMock(1002, "Bob", open_path_id=2002, waiver_date=start, facility_tour_date=tour)\
                    .add_membership(CERAMICS, start, end)\
                    .mock(requests_mock),
                build_alta_user(2002, ['ceramics_access']),
            ),

            # User 3: Comped regular membership (no waiver/tour - no facility access)
            (
                NeonMock(1003, "Carol", open_path_id=3003)\
                    .add_membership(REGULAR, start, end)\
                    .mock(requests_mock),
                build_alta_user(3003, []),
            ),
        ]

        setup_mocks['getAllUsers'].return_value = {alta['OpenPathID']: alta for _, alta in accounts}

        neon_accounts = {neon["Account ID"]: neon for neon, _ in accounts}
        openPathUpdateAll(neon_accounts)

        # Verify updateGroups is called for users with existing OpenPathID
        assert setup_mocks['updateGroups'].call_count == 3
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_creates_user_for_facility_access_without_openpathid(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update creates new OpenPath user for member with facility access but no OpenPathID"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        facility_user = NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0)\
            .mock(requests_mock)
        setup_mocks['createUser'].return_value = {**facility_user, 'OpenPathID': ALTA_ID}
        setup_mocks['getAllUsers'].return_value = {}

        openPathUpdateAll({NEON_ID: facility_user})

        # Verify createUser is called for this user
        setup_mocks['createUser'].assert_called_once()
        setup_mocks['createMobileCredential'].assert_called_once()
        # updateGroups should be called with empty groups list per openPathUpdateAll implementation
        setup_mocks['updateGroups'].assert_called_once()
        call_args = setup_mocks['updateGroups'].call_args
        assert call_args[1]['openPathGroups'] == []

    def test_bulk_update_ignores_no_membership_no_openpathid(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update ignores users without membership and no OpenPathID"""
        neon_account = NeonMock(NEON_ID).mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {}

        openPathUpdateAll({NEON_ID: neon_account})

        # Verify no OpenPath operations are called
        setup_mocks['updateGroups'].assert_not_called()
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_warns_missing_waiver(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update warns about users with OpenPathID but missing waiver"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_account = NeonMock(NEON_ID, open_path_id=ALTA_ID, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0)\
            .mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {
            ALTA_ID: build_alta_user(ALTA_ID, ['facility_access']),
        }

        openPathUpdateAll({NEON_ID: neon_account})

        setup_mocks['updateGroups'].assert_called_once()

    def test_bulk_update_handles_multiple_accounts_in_batches(self, requests_mock, mocker, setup_mocks):
        """Test bulk update with large batch of accounts to verify loop handling"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # Create 20 users with varying membership statuses
        for i in range(20):
            neon_id = 10 + i
            alta_id = 100 + i

            if i % 3 == 0:  # Every 3rd user gets paid membership with facility access
                neon_accounts[neon_id] = NeonMock(neon_id, open_path_id=alta_id, waiver_date=start, facility_tour_date=tour)\
                    .add_membership(REGULAR, start, end, fee=100.0)\
                    .mock(requests_mock)
            else:
                neon_accounts[neon_id] = NeonMock(neon_id, open_path_id=alta_id).mock(requests_mock)
            alta_accounts[alta_id] = build_alta_user(alta_id, [f'group_{i}'])

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll(neon_accounts)

        # All users have OpenPathID, so updateGroups should be called 20 times
        assert setup_mocks['updateGroups'].call_count == 20

    def test_bulk_update_counts_subscription_types_accurately(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update correctly counts paid regular vs ceramics subscriptions"""
        start0 = today_plus(-365 * 2)
        end0 = today_plus(-366)
        start1 = today_plus(-365)
        end1 = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User 1: Paid regular only
        neon_accounts[1] = NeonMock(1, open_path_id=10)\
            .add_membership(REGULAR, start1, end1, fee=100.0)\
            .mock(requests_mock)
        alta_accounts[10] = build_alta_user(10)

        # User 2: Paid ceramics only
        neon_accounts[2] = NeonMock(2, open_path_id=20)\
            .add_membership(CERAMICS, start1, end1, fee=150.0)\
            .mock(requests_mock)
        alta_accounts[20] = build_alta_user(20)

        # User 3: Both paid regular AND paid ceramics (upgrade case)
        neon_accounts[3] = NeonMock(3, open_path_id=30)\
            .add_membership(REGULAR, start0, end0, fee=100.0)\
            .add_membership(CERAMICS, start1, end1, fee=150.0)\
            .mock(requests_mock)
        alta_accounts[30] = build_alta_user(30)

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll(neon_accounts)

        # All should call updateGroups (all have OpenPathID)
        assert setup_mocks['updateGroups'].call_count == 3

    def test_bulk_update_missing_required_access_fields(self, requests_mock, mocker, setup_mocks):
        """Test bulk update with users missing required facility access fields"""
        start = today_plus(-365)
        end = today_plus(365)

        neon_account = NeonMock(NEON_ID, open_path_id=ALTA_ID)\
            .add_membership(REGULAR, start, end, fee=100.0)\
            .mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {
            ALTA_ID: build_alta_user(ALTA_ID),
        }

        openPathUpdateAll({NEON_ID: neon_account})

        # Has OpenPathID so updateGroups is called, but no createUser (missing access requirements)
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()

    def test_bulk_update_openpathid_as_integer_conversion(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update correctly converts OpenPathID to int for Alta lookup"""
        neon_account = NeonMock(NEON_ID, open_path_id=ALTA_ID).mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {
            ALTA_ID: build_alta_user(ALTA_ID, ['test_group']),
        }

        openPathUpdateAll({NEON_ID: neon_account})

        # Should successfully find user in Alta accounts via int conversion
        setup_mocks['updateGroups'].assert_called_once()
        call_args = setup_mocks['updateGroups'].call_args
        assert call_args[1]['openPathGroups'] == ['test_group']

    def test_bulk_update_with_access_suspended(self, requests_mock, mocker, setup_mocks):
        """Test that suspended accounts don't get facility access even with waiver/tour"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_account = NeonMock(NEON_ID, open_path_id=ALTA_ID, waiver_date=start,
                 facility_tour_date=tour, custom_fields={'AccessSuspended': 'Yes'})\
            .add_membership(REGULAR, start, end, fee=100.0)\
            .mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {
            ALTA_ID: build_alta_user(ALTA_ID),
        }

        openPathUpdateAll({NEON_ID: neon_account})

        # Should still update groups (has OpenPathID), but not create new access
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()


def test_creates_user(requests_mock):
    rm = requests_mock

    start = today_plus(-365)
    tour = today_plus(-364)
    end = today_plus(365)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Setup Neon account with valid membership no OpenPathID
    account = NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)
    neon_account = account.mock(rm)

    # Return no existing OpenPath users
    get_all_users = rm.get(f'{O_baseURL}/users', json={"data": [], "totalCount": 0})

    # Mock each write in the order it should be called
    writes = dict(
        create_alta=rm.post(
            f'{O_baseURL}/users',
            status_code=201,
            json={"data": {"id": ALTA_ID, "createdAt": now}},
        ),
        update_neon=rm.patch(
            f'{N_baseURL}/accounts/{NEON_ID}',
            status_code=200,
        ),
        update_groups=rm.put(
            f'{O_baseURL}/users/{ALTA_ID}/groupIds',
            status_code=204,
        ),
        credentials=rm.post(
            f'{O_baseURL}/users/{ALTA_ID}/credentials',
            status_code=201,
            json={"data": {"id": CRED_ID}},
        ),
        setup_mobile=rm.post(
            f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile',
            status_code=204,
        ),
    )

    # New user --> get all users, create user, update neon, update groups, create mobile credential
    assert_history(rm, lambda: openPathUpdateAll({NEON_ID: neon_account}), [
        (get_all_users._method, get_all_users._url),  # getAllUsers
        *[(m._method, m._url) for m in writes.values()]  # writes happen in expected order
    ])

    # Verify body of each write
    assert writes['create_alta'].last_request.json() == {
        "identity": {
            "email": account.email,
            "firstName": account.firstName,
            "lastName": account.lastName,
        },
        "externalId": NEON_ID,
        "hasRemoteUnlock": False,
    }
    assert writes['update_neon'].last_request.json() == {
        "individualAccount": {
            "accountCustomFields": [
                {"id": ACCOUNT_FIELD_OPENPATH_ID, "name": "OpenPathID", "value": str(ALTA_ID)}
            ]
        }
    }
    assert writes['update_groups'].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}
    assert writes['credentials'].last_request.json() == {
        "mobile": {"name": "Automatic Mobile Credential"},
        "credentialTypeId": 1,
    }
