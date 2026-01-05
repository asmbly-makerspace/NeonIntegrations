from datetime import datetime, timezone

from openPathUpdateAll import openPathUpdateAll
from neonUtil import MEMBERSHIP_ID_REGULAR, MEMBERSHIP_ID_CERAMICS, ACCOUNT_FIELD_OPENPATH_ID, N_baseURL, LEAD_TYPE
from openPathUtil import GROUP_SUBSCRIBERS, GROUP_CERAMICS, GROUP_MANAGEMENT, O_baseURL

from tests.neon_mocker import NeonUserMock, today_plus, assert_history


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
        NeonUserMock(1, open_path_id=101, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(2, open_path_id=102, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(3, open_path_id=103, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(4, open_path_id=104, waiver_date=start, facility_tour_date=tour,
            individualTypes=[LEAD_TYPE]),
        NeonUserMock(5, open_path_id=105, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=0.0),
    ]

    skipped_accounts = [
        NeonUserMock(11, open_path_id=111, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(12, open_path_id=112, waiver_date=start, facility_tour_date=tour,
                custom_fields={'CsiDate': start})\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(13, open_path_id=113, waiver_date=start, facility_tour_date=tour)\
            .add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(14, open_path_id=114, waiver_date=start, facility_tour_date=tour)\
            .add_membership(REGULAR, start, end, fee=0.0),
    ]

    get_all_users = mock_get_all_users(rm, [
        {"id": updated_accounts[0].open_path_id, "groups": []},
        {"id": updated_accounts[1].open_path_id, "groups": []},
        {"id": updated_accounts[2].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": updated_accounts[3].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": updated_accounts[4].open_path_id, "groups": []},

        {"id": skipped_accounts[0].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": skipped_accounts[1].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}, {"id": GROUP_CERAMICS}]},
        {"id": skipped_accounts[2].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
        {"id": skipped_accounts[3].open_path_id, "groups": [{"id": GROUP_SUBSCRIBERS}]},
    ])

    updates = [
        rm.put(f'{O_baseURL}/users/{act.open_path_id}/groupIds', status_code=204)
        for act in updated_accounts
    ]

    accounts = {act.account_id: act.mock(rm) for act in [*updated_accounts, *skipped_accounts]}
    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
        *[(u._method, u._url) for u in updates]
    ])

    assert updates[0].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}
    assert updates[1].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_CERAMICS]}
    assert updates[2].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_CERAMICS]}
    assert updates[3].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS, GROUP_MANAGEMENT]}
    assert updates[4].last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_bulk_update_mixed_accounts(requests_mock):
    rm = requests_mock

    accounts = {}
    updates = []

    for i in range(50):
        neon_id = 1000 + i
        alta_id = 2000 + i

        if i % 3 < 2:
            account = NeonUserMock(neon_id, open_path_id=alta_id, waiver_date=start, facility_tour_date=tour)\
                .add_membership(CERAMICS if i % 3 == 0 else REGULAR, start, end, fee=100.0)
            updates.append(rm.put(f'{O_baseURL}/users/{alta_id}/groupIds', status_code=204))
        else:
            account = NeonUserMock(neon_id, open_path_id=alta_id)
        accounts[neon_id] = account.mock(rm)

    get_all_users = mock_empty_groups(rm, accounts)

    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
        *[(u._method, u._url) for u in updates]
    ])


def test_skips_invalid_accounts(requests_mock):
    rm = requests_mock

    accounts = [
        NeonUserMock(1),
        NeonUserMock(2, open_path_id=ALTA_ID),
        NeonUserMock(3).add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(4).add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(5, waiver_date=start),
        NeonUserMock(6, facility_tour_date=tour),
        NeonUserMock(7, facility_tour_date=tour).add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(8, waiver_date=start).add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(9, waiver_date=start).add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(10, open_path_id=ALTA_ID+1, waiver_date=start, facility_tour_date=tour,
            custom_fields={'AccessSuspended': 'Yes'})\
            .add_membership(REGULAR, start, end, fee=100.0),
    ]

    accounts = {act.account_id: act.mock(rm) for act in accounts}
    get_all_users = mock_empty_groups(rm, accounts)

    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
    ])


def test_creates_user(requests_mock):
    """Test creating a new OpenPath user for account without OpenPathID"""
    rm = requests_mock

    account = NeonUserMock(waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)

    updates = dict(
        create_alta=rm.post(
            f'{O_baseURL}/users',
            status_code=201,
            json={"data": {"id": ALTA_ID, "createdAt": now}},
        ),
        update_neon=rm.patch(
            f'{N_baseURL}/accounts/{account.account_id}',
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

    accounts = {account.account_id: account.mock(rm)}
    get_all_users = mock_empty_groups(rm, accounts)

    assert_history(rm, lambda: openPathUpdateAll(accounts), [
        (get_all_users._method, get_all_users._url),
        *[(u._method, u._url) for u in updates.values()]
    ])

    assert updates['create_alta'].last_request.json() == {
        "identity": {
            "email": account.email,
            "firstName": account.firstName,
            "lastName": account.lastName,
        },
        "externalId": account.account_id,
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
