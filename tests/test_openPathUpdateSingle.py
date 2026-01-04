from openPathUpdateSingle import openPathUpdateSingle
from tests.neon_mocker import NeonMock, today_plus
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
    # Setup account with invalid membership (no waiver or tour)
    NeonMock(NEON_ID).mock(requests_mock)

    requests_mock.reset_mock() # reset history
    openPathUpdateSingle(NEON_ID)

    # No valid membership --> only fetch from Neon, do nothing else
    history = [(r.method, r.path) for r in requests_mock.request_history]
    assert history == [
        ('GET', f'/v2/accounts/{NEON_ID}'),              # get account
        ('GET', f'/v2/accounts/{NEON_ID}/memberships'),  # get memberships
    ]


def test_does_not_update_existing_user(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)\
        .mock(requests_mock)

    # Return correct OpenPath groups
    requests_mock.get(f'{O_baseURL}/users/{ALTA_ID}/groups', json={"data": [{"id": GROUP_SUBSCRIBERS}]})

    requests_mock.reset_mock() # reset history
    openPathUpdateSingle(NEON_ID)

    # Existing OpenPathID with valid groups --> fetch info, but do nothing
    history = [(r.method, r.path) for r in requests_mock.request_history]
    assert history == [
        ('GET', f'/v2/accounts/{NEON_ID}'),              # get account
        ('GET', f'/v2/accounts/{NEON_ID}/memberships'),  # get memberships
        ('GET', f'/orgs/5231/users/{ALTA_ID}/groups'),   # get existing groups
    ]


def test_updates_existing_user_with_missing_groups(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    NeonMock(NEON_ID, waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)\
        .mock(requests_mock)

    # Return empty list for groups to check whether they're updated correctly
    requests_mock.get(f'{O_baseURL}/users/{ALTA_ID}/groups', json={"data": []})
    update_groupids = requests_mock.put(f'{O_baseURL}/users/{ALTA_ID}/groupIds', status_code=204)

    requests_mock.reset_mock() # reset history
    openPathUpdateSingle(NEON_ID)

    # Existing OpenPathID --> update groups, not create
    history = [(r.method, r.path) for r in requests_mock.request_history]
    assert history == [
        ('GET', f'/v2/accounts/{NEON_ID}'),              # get account
        ('GET', f'/v2/accounts/{NEON_ID}/memberships'),  # get memberships
        ('GET', f'/orgs/5231/users/{ALTA_ID}/groups'),   # get existing groups
        ('PUT', f'/orgs/5231/users/{ALTA_ID}/groupids'), # updateGroups
    ]

    # Verify groups updated correctly
    assert update_groupids.last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_create_new_user(requests_mock, mocker):
    rm = requests_mock

    # Setup valid account with membership, waiver, and tour, but no existing OpenPathID
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
        update_groupids=rm.put(
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

    rm.reset_mock() # clear history
    openPathUpdateSingle(NEON_ID)

    # New user --> create user, update groups, update neon, create mobile credential
    history = [(r.method, r.url) for r in rm.request_history]
    assert history == [
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}'),              # get account
        ('GET', f'{N_baseURL}/accounts/{NEON_ID}/memberships'),  # get memberships
        *[(m._method, m._url) for m in writes.values()] # writes happen in expected order
    ]

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
    assert writes['update_groupids'].last_request.json() == {
        "groupIds": [GROUP_SUBSCRIBERS],
    }
    assert writes['credentials'].last_request.json() == {
        "mobile": {"name": "Automatic Mobile Credential"},
        "credentialTypeId": 1,
    }

