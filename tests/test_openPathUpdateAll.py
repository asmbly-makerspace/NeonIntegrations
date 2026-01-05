from datetime import datetime, timezone

from openPathUpdateAll import openPathUpdateAll
from neonUtil import MEMBERSHIP_ID_REGULAR, MEMBERSHIP_ID_CERAMICS, ACCOUNT_FIELD_OPENPATH_ID, N_baseURL, LEAD_TYPE
from openPathUtil import GROUP_SUBSCRIBERS, GROUP_CERAMICS, GROUP_MANAGEMENT, O_baseURL

from tests.neon_mocker import NeonMock, today_plus, assert_history


NEON_ID = 123
ALTA_ID = 456
CRED_ID = 789
REGULAR = MEMBERSHIP_ID_REGULAR
CERAMICS = MEMBERSHIP_ID_CERAMICS


start = today_plus(-365)
tour = today_plus(-364)
end = today_plus(365)
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def mock_get_all_users(rm, users):
    """Helper to mock getAllUsers endpoint with paginated response"""
    return rm.get(
        f'{O_baseURL}/users',
        json={"data": users, "totalCount": len(users)},
    )


def mock_empty_groups(rm, accounts):
    # Return empty groups for all existing users
    return mock_get_all_users(rm, [
        {"id": act["OpenPathID"], "groups": []}
        for act in accounts.values()
        if "OpenPathID" in act
    ])


def test_updates_existing_users_with_missing_groups(requests_mock):
    rm = requests_mock

    updated_accounts = [
        NeonMock(NEON_ID, open_path_id=ALTA_ID, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID+1, open_path_id=ALTA_ID+1, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonMock(NEON_ID+2, open_path_id=ALTA_ID+2, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonMock(NEON_ID+3, open_path_id=ALTA_ID+3, waiver_date=start, facility_tour_date=tour,\
            individualTypes=[LEAD_TYPE]),
        NeonMock(NEON_ID+4, open_path_id=ALTA_ID+4, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=0.0), # zero-fee
    ]

    skipped_accounts = [
        NeonMock(NEON_ID+10, open_path_id=ALTA_ID+10, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID+11, open_path_id=ALTA_ID+11, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonMock(NEON_ID+12, open_path_id=ALTA_ID+12, waiver_date=start, facility_tour_date=tour)\
            .add_membership(CERAMICS, start, end, fee=100.0), # no csi tour date
        NeonMock(NEON_ID+13, open_path_id=ALTA_ID+13, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=0.0), # zero-fee
    ]

    get_all_users = mock_get_all_users(rm, [
        {"id": updated_accounts[0].open_path_id, "groups": []},
        {"id": updated_accounts[1].open_path_id, "groups": []},
        {"id": updated_accounts[2].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": updated_accounts[3].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": updated_accounts[4].open_path_id, "groups": []},

        {"id": skipped_accounts[0].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": skipped_accounts[1].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}, {"id": GROUP_CERAMICS}]},
        # This user doesn't get update - they have SUBSCRIBERS but won't get CERAMICS (no CsiDate)
        {"id": skipped_accounts[2].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": skipped_accounts[3].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
    ])

    # Mock update endpoints for first 3 users' updates. 
    # The other two should be skipped since they are already in sync 
    updates = [
        rm.put(f'{O_baseURL}/users/{act.open_path_id}/groupIds', status_code=204)
        for act in updated_accounts
    ]

    # Verify that only users with out-of-sync groups were updated
    accounts = {act.account_id: act.mock(rm) for act in [*updated_accounts, *skipped_accounts]}
    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
        *[(u._method, u._url) for u in updates]
    ])

    # Verify correct groups were assigned
    assert updates[0].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}
    assert updates[1].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_CERAMICS]}
    assert updates[2].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_CERAMICS]}
    assert updates[3].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_MANAGEMENT]}
    assert updates[4].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_bulk_update_mixed_accounts(requests_mock):
    rm = requests_mock

    accounts = {}
    updates = []

    # Create 50 users with varying membership statuses
    for i in range(50):
        neon_id = 10 + i
        alta_id = 100 + i

        # Alternate between invalid, ceramic, and regular members
        if i % 3 < 2:
            account = NeonMock(neon_id, open_path_id=alta_id, waiver_date=start, facility_tour_date=tour)\
                .add_membership(CERAMICS if i % 3 == 0 else REGULAR, start, end, fee=100.0)
            updates.append(rm.put(f'{O_baseURL}/users/{alta_id}/groupIds', status_code=204))
        else:
            account = NeonMock(neon_id, open_path_id=alta_id)
        accounts[neon_id] = account.mock(rm)

    get_all_users = mock_empty_groups(rm, accounts)

    # only valid accounts are updated
    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
        *[(u._method, u._url) for u in updates]
    ])


def test_skips_invalid_accounts(requests_mock):
    rm = requests_mock

    accounts = [
        # accounts must have waivers+tour date+payment to be valid
        NeonMock(NEON_ID),
        NeonMock(NEON_ID+1, open_path_id=ALTA_ID),
        NeonMock(NEON_ID+2).add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID+3).add_membership(CERAMICS, start, end, fee=100.0),
        NeonMock(NEON_ID+4, waiver_date=start),
        NeonMock(NEON_ID+5, facility_tour_date=tour),
        NeonMock(NEON_ID+6, facility_tour_date=tour).add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID+7, waiver_date=start).add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID+8, waiver_date=start).add_membership(CERAMICS, start, end, fee=100.0),

        # suspended users are ignored
        NeonMock(NEON_ID+9, open_path_id=ALTA_ID+1, waiver_date=start, facility_tour_date=tour,
            custom_fields={'AccessSuspended': 'Yes'})\
            .add_membership(REGULAR, start, end, fee=100.0),

        #NeonMock(NEON_ID+10, open_path_id=ALTA_ID+2, waiver_date=start, facility_tour_date=tour)\
        #.add_membership(REGULAR, start, end, fee=0.0),

        #NeonMock(1003, open_path_id=2003, waiver_date=start, facility_tour_date=tour)\
        #    .add_membership(REGULAR, start, end, fee=0.0),
    ]

    accounts = {act.account_id: act.mock(rm) for act in accounts}
    get_all_users = mock_empty_groups(rm, accounts)

    # users are fetched, and no accounts are updated
    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
    ])


def test_creates_user(requests_mock):
    """Test creating a new OpenPath user for account without OpenPathID"""
    rm = requests_mock

    # Setup Neon account with valid membership no OpenPathID
    account = NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)

    # Mock each write in the order it should be called
    updates = dict(
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

    accounts = {NEON_ID: account.mock(rm)}
    get_all_users = mock_empty_groups(rm, accounts)

    # New user --> get all users, create user, update neon, update groups, create mobile credential
    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),  # getAllUsers
        *[(u._method, u._url) for u in updates.values()]  # updates happen in expected order
    ])

    # Verify body of each write
    assert updates['create_alta'].last_request.json() == {
        "identity": {
            "email": account.email,
            "firstName": account.firstName,
            "lastName": account.lastName,
        },
        "externalId": NEON_ID,
        "hasRemoteUnlock": False,
    }
    assert updates['update_neon'].last_request.json() == {
        "individualAccount": {
            "accountCustomFields": [
                {"id": str(ACCOUNT_FIELD_OPENPATH_ID), "name": "OpenPathID", "value": str(ALTA_ID)}
            ]
        }
    }
    assert updates['update_groups'].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}
    assert updates['credentials'].last_request.json() == {
        "mobile": {"name": "Automatic Mobile Credential"},
        "credentialTypeId": 1,
    }
