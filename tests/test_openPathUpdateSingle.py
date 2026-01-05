from openPathUpdateSingle import openPathUpdateSingle
from tests.neon_mocker import NeonMock, today_plus, assert_history
from neonUtil import MEMBERSHIP_ID_REGULAR, ACCOUNT_FIELD_OPENPATH_ID, N_baseURL
from openPathUtil import GROUP_SUBSCRIBERS, O_baseURL
from datetime import datetime, timezone


NEON_ID = 123
ALTA_ID = 456
CRED_ID = 789
REGULAR = MEMBERSHIP_ID_REGULAR


start = today_plus(-365)
tour = today_plus(-364)
end = today_plus(365)
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_does_not_create_invalid_user(requests_mock, mocker):
    # Test invalid accounts (no waiver, tour, or membership)
    invalid_accounts = [
        NeonMock(NEON_ID),
        NeonMock(NEON_ID, waiver_date=start),
        NeonMock(NEON_ID, facility_tour_date=tour),
        NeonMock(NEON_ID, facility_tour_date=tour).add_membership(REGULAR, start, end, fee=100.0),
        NeonMock(NEON_ID, waiver_date=start).add_membership(REGULAR, start, end, fee=100.0),
    ]
    for account in invalid_accounts:
        account.mock(requests_mock)
        # No valid membership --> only fetch from Neon, do nothing else
        assert_history(requests_mock, lambda: openPathUpdateSingle(NEON_ID), [
            ('GET', f'{N_baseURL}/accounts/{NEON_ID}'),             # get account
            ('GET', f'{N_baseURL}/accounts/{NEON_ID}/memberships'), # get memberships
        ])


def test_does_not_update_existing_user(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)\
        .mock(requests_mock)

    # Return correct OpenPath groups
    get_groups = requests_mock.get(
        f'{O_baseURL}/users/{ALTA_ID}/groups',
        json={"data": [{"id": GROUP_SUBSCRIBERS}]},
    )

    # Existing OpenPathID with valid groups --> fetch info, but do nothing
    assert_history(requests_mock, lambda: openPathUpdateSingle(NEON_ID), [
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}'),             # get account
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}/memberships'), # get memberships
        (get_groups._method, get_groups._url),  # get existing groups
    ])


def test_updates_existing_user_with_missing_groups(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)\
        .mock(requests_mock)

    # Return empty list for groups to check whether they're updated correctly
    get_groups = requests_mock.get(f'{O_baseURL}/users/{ALTA_ID}/groups', json={"data": []})
    update_groups = requests_mock.put(f'{O_baseURL}/users/{ALTA_ID}/groupIds', status_code=204)

    # Existing OpenPathID --> update groups, not create
    assert_history(requests_mock, lambda: openPathUpdateSingle(NEON_ID), [
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}'),              # get account
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}/memberships'),  # get memberships
        (get_groups._method, get_groups._url),        # get existing groups
        (update_groups._method, update_groups._url),  # updateGroups
    ])

    # Verify groups updated correctly
    assert update_groups.last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_creates_user(requests_mock, mocker):
    rm = requests_mock

    # Setup valid account with valid membership but no OpenPathID
    account = NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(rm)

    # Mock each write in the order it should be called
    writes = dict(
        create_alta=rm.post(
            f'{O_baseURL}/users',
            status_code=201, json={"data": {"id": ALTA_ID, "createdAt": now}},
        ),
        update_neon=rm.patch(
            f'{N_baseURL}/accounts/{NEON_ID}',
            status_code=200
        ),
        update_groups=rm.put(
           f'{O_baseURL}/users/{ALTA_ID}/groupIds', 
           status_code=204
        ),
        credentials=rm.post(
            f'{O_baseURL}/users/{ALTA_ID}/credentials',
            status_code=201, json={"data": {"id": CRED_ID}},
        ),
        setup_mobile=rm.post(
            f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile',
            status_code=204,
        )
    )

    # New user --> create user, update groups, update neon, create mobile credential
    assert_history(rm, lambda: openPathUpdateSingle(NEON_ID), [
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}'),              # get account
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}/memberships'),  # get memberships
        *[(m._method, m._url) for m in writes.values()] # writes happen in expected order
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
    assert writes['update_groups'].last_request.json() == {
        "groupIds": [GROUP_SUBSCRIBERS],
    }
    assert writes['credentials'].last_request.json() == {
        "mobile": {"name": "Automatic Mobile Credential"},
        "credentialTypeId": 1,
    }
