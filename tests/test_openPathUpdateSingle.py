from openPathUpdateSingle import openPathUpdateSingle
from neon_mocker import NeonUserMock, today_plus, assert_history
from neonUtil import MEMBERSHIP_ID_REGULAR, MEMBERSHIP_ID_CERAMICS, ACCOUNT_FIELD_OPENPATH_ID, N_baseURL, INSTRUCTOR_TYPE, ONDUTY_TYPE
from openPathUtil import GROUP_SUBSCRIBERS, GROUP_INSTRUCTORS, GROUP_ONDUTY, O_baseURL
import pytest
from datetime import datetime, timedelta, timezone


ALTA_ID = 456
CRED_ID = 789
REGULAR = MEMBERSHIP_ID_REGULAR
CERAMICS = MEMBERSHIP_ID_CERAMICS


start = today_plus(-365)
tour = today_plus(-364)
end = today_plus(365)


def alta_created_at(age=timedelta(0), fmt="%Y-%m-%dT%H:%M:%S.000Z"):
    """createdAt for a user created `age` ago. Call per test, not at import time."""
    return (datetime.now(timezone.utc) - age).strftime(fmt)


def test_skips_invalid_user(requests_mock, mocker):
    # Test invalid accounts (no waiver, tour, or membership)
    invalid_accounts = [
        NeonUserMock(),
        NeonUserMock().add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock().add_membership(CERAMICS, start, end, fee=100.0),
        NeonUserMock(waiver_date=start),
        NeonUserMock(facility_tour_date=tour),
        NeonUserMock(facility_tour_date=tour).add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(waiver_date=start).add_membership(REGULAR, start, end, fee=100.0),
        NeonUserMock(waiver_date=start).add_membership(CERAMICS, start, end, fee=100.0),
    ]
    for account in invalid_accounts:
        account.mock(requests_mock)
        # No valid membership --> only fetch from Neon, do nothing else
        assert_history(requests_mock, lambda: openPathUpdateSingle(account.account_id), [
            ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
            ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        ])


def test_skips_existing_user(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    account = NeonUserMock(waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(requests_mock)

    # Return correct OpenPath groups
    get_groups = requests_mock.get(
        f'{O_baseURL}/users/{ALTA_ID}/groups',
        json={"data": [{"id": GROUP_SUBSCRIBERS}]},
    )

    # Existing OpenPathID with valid groups --> fetch info, but do nothing
    assert_history(requests_mock, lambda: openPathUpdateSingle(account.account_id), [
        ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
        ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        (get_groups._method, get_groups._url),
    ])


def test_updates_existing_user_with_missing_groups(requests_mock, mocker):
    # Setup valid account with existing OpenPathID
    account = NeonUserMock(waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(requests_mock)

    # Return empty list for groups to check whether they're updated correctly
    get_groups = requests_mock.get(f'{O_baseURL}/users/{ALTA_ID}/groups', json={"data": []})
    update_groups = requests_mock.put(f'{O_baseURL}/users/{ALTA_ID}/groupIds', status_code=204)

    # Existing OpenPathID --> update groups, not create
    assert_history(requests_mock, lambda: openPathUpdateSingle(account.account_id), [
        ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
        ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        (get_groups._method, get_groups._url),
        (update_groups._method, update_groups._url),
    ])

    # Verify groups updated correctly
    assert update_groups.last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_creates_user_with_correct_group(requests_mock, mocker):
    rm = requests_mock

    accounts = [
        (
            NeonUserMock(waiver_date=start, facility_tour_date=tour)\
                .add_membership(REGULAR, start, end, fee=100.0),
            [GROUP_SUBSCRIBERS],
        ),
        (
            NeonUserMock(individualTypes=[INSTRUCTOR_TYPE]),
            [GROUP_INSTRUCTORS],
        ),
        (
            NeonUserMock(individualTypes=[ONDUTY_TYPE]),
            [GROUP_ONDUTY],
        )
    ]

    for account, expected_groups in accounts:
        account.mock(rm)

        updates = dict(
            create_alta=rm.post(
                f'{O_baseURL}/users',
                status_code=201, json={"data": {"id": ALTA_ID, "createdAt": alta_created_at()}},
            ),
            update_neon=rm.patch(
                f'{N_baseURL}/accounts/{account.account_id}',
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

        assert_history(rm, lambda: openPathUpdateSingle(account.account_id), [
            ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
            ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
            *[(m._method, m._url) for m in updates.values()]
        ])

        # Verify body of each update
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
        assert updates['update_groups'].last_request.json() == {
            "groupIds": expected_groups,
        }
        assert updates['credentials'].last_request.json() == {
            "mobile": {"name": "Automatic Mobile Credential"},
            "credentialTypeId": 1,
        }


def test_handles_failed_user_creation(requests_mock):
    """When OpenPath returns 400 for user creation, log error and don't proceed."""
    rm = requests_mock

    account = NeonUserMock(waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(rm)

    create_alta = rm.post(f'{O_baseURL}/users', status_code=400, json={
        "message": "This user is already active in this organization."
    })

    assert_history(rm, lambda: openPathUpdateSingle(account.account_id), [
        ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
        ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        (create_alta._method, create_alta._url),
    ])


@pytest.mark.parametrize("age, fmt", [
    (timedelta(0), "%Y-%m-%dT%H:%M:%S.000Z"),
    (timedelta(0), "%Y-%m-%dT%H:%M:%S.123Z"),
    (timedelta(0), "%Y-%m-%dT%H:%M:%SZ"),
    (timedelta(0), "%Y-%m-%dT%H:%M:%S"),
    (timedelta(seconds=-5), "%Y-%m-%dT%H:%M:%S.000Z"),
], ids=["just-created", "nonzero-milliseconds", "no-milliseconds", "no-timezone", "alta-clock-5s-ahead"])
def test_new_alta_user_skips_stale_credential_cleanup(requests_mock, age, fmt):
    """A user Alta created moments ago is new: no credential cleanup and no user PATCH."""
    rm = requests_mock

    account = NeonUserMock(waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(rm)

    rm.post(
        f'{O_baseURL}/users',
        status_code=201, json={"data": {"id": ALTA_ID, "createdAt": alta_created_at(age, fmt)}},
    )
    rm.patch(f'{N_baseURL}/accounts/{account.account_id}', status_code=200)
    rm.put(f'{O_baseURL}/users/{ALTA_ID}/groupIds', status_code=204)
    rm.post(
        f'{O_baseURL}/users/{ALTA_ID}/credentials',
        status_code=201, json={"data": {"id": CRED_ID}},
    )
    rm.post(f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile', status_code=204)

    assert_history(rm, lambda: openPathUpdateSingle(account.account_id), [
        ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
        ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        ('POST', f'{O_baseURL}/users'),
        ('PATCH', f'{N_baseURL}/accounts/{account.account_id}'),
        ('PUT', f'{O_baseURL}/users/{ALTA_ID}/groupIds'),
        ('POST', f'{O_baseURL}/users/{ALTA_ID}/credentials'),
        ('POST', f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile'),
    ])


@pytest.mark.parametrize("age", [
    timedelta(minutes=10),
    timedelta(days=2, minutes=1),
], ids=["10-minutes-old", "2-days-1-minute-old"])
def test_resurrected_alta_user_is_refreshed(requests_mock, age):
    """An Alta user with an old createdAt has its credentials deleted and is PATCHed before the Neon save."""
    rm = requests_mock

    account = NeonUserMock(waiver_date=start, facility_tour_date=tour)\
        .add_membership(REGULAR, start, end, fee=100.0)
    account.mock(rm)

    stale_cred_ids = [11, 12]
    rm.post(
        f'{O_baseURL}/users',
        status_code=201, json={"data": {"id": ALTA_ID, "createdAt": alta_created_at(age)}},
    )
    rm.get(
        f'{O_baseURL}/users/{ALTA_ID}/credentials?offset=0&sort=id&order=asc',
        json={"data": [{"id": cred_id} for cred_id in stale_cred_ids]},
    )
    for cred_id in stale_cred_ids:
        rm.delete(f'{O_baseURL}/users/{ALTA_ID}/credentials/{cred_id}', status_code=204)
    refresh_alta = rm.patch(f'{O_baseURL}/users/{ALTA_ID}', status_code=200)
    update_neon = rm.patch(f'{N_baseURL}/accounts/{account.account_id}', status_code=200)
    rm.put(f'{O_baseURL}/users/{ALTA_ID}/groupIds', status_code=204)
    rm.post(
        f'{O_baseURL}/users/{ALTA_ID}/credentials',
        status_code=201, json={"data": {"id": CRED_ID}},
    )
    rm.post(f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile', status_code=204)

    assert_history(rm, lambda: openPathUpdateSingle(account.account_id), [
        ('GET', f'{N_baseURL}/accounts/{account.account_id}'),
        ('GET', f'{N_baseURL}/accounts/{account.account_id}/memberships'),
        ('POST', f'{O_baseURL}/users'),
        # stale cleanup
        ('GET', f'{O_baseURL}/users/{ALTA_ID}/credentials'),
        *[('DELETE', f'{O_baseURL}/users/{ALTA_ID}/credentials/{cred_id}') for cred_id in stale_cred_ids],
        ('PATCH', f'{O_baseURL}/users/{ALTA_ID}'),
        # then the same as a new user
        ('PATCH', f'{N_baseURL}/accounts/{account.account_id}'),
        ('PUT', f'{O_baseURL}/users/{ALTA_ID}/groupIds'),
        ('POST', f'{O_baseURL}/users/{ALTA_ID}/credentials'),
        ('POST', f'{O_baseURL}/users/{ALTA_ID}/credentials/{CRED_ID}/setupMobile'),
    ])

    assert refresh_alta.last_request.json() == {
        "identity": {
            "email": account.email,
            "firstName": account.firstName,
            "lastName": account.lastName,
        },
        "externalId": account.account_id,
        "hasRemoteUnlock": False,
    }
    assert update_neon.last_request.json() == {
        "individualAccount": {
            "accountCustomFields": [
                {"id": str(ACCOUNT_FIELD_OPENPATH_ID), "name": "OpenPathID", "value": str(ALTA_ID)}
            ]
        }
    }
