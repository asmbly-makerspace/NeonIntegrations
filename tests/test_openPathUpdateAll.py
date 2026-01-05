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


    def test_mixed_membership_types(self, requests_mock, mocker, setup_mocks):
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

    def test_skips_no_membership(self, requests_mock, mocker, setup_mocks):
        """Test that bulk update ignores users without membership and no OpenPathID"""
        neon_account = NeonMock(NEON_ID).mock(requests_mock)
        setup_mocks['getAllUsers'].return_value = {}

        openPathUpdateAll({NEON_ID: neon_account})

        # Verify no OpenPath operations are called
        setup_mocks['updateGroups'].assert_not_called()
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_skips_no_waiver(self, requests_mock, mocker, setup_mocks):
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

    def test_bulk_update_accounts(self, requests_mock, mocker, setup_mocks):
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

    def test_handles_access_suspended(self, requests_mock, mocker, setup_mocks):
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
