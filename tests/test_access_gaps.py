"""
Paths through the webhook -> Neon -> OpenPath sync that can leave a member who
qualifies for access locked out, or let one keep access too long.

- Section 1 covers the date lookup: a warm Lambda container can span midnight,
  so membership checks must read the date on every call rather than reuse one
  cached at import.
- Sections 2-4 characterize current behavior. Sections 2 and 3 can delay
  access until another webhook arrives for the account or the next full sync
  (dailyMaintenance.py) runs. Section 4 is never corrected by either sync.

Time is frozen with freezegun on a fixed date, so these tests don't depend on
when the suite runs.
"""

import datetime
import json
import sys
from pathlib import Path

import pytest
from freezegun import freeze_time

from neon_mocker import NeonUserMock
from neonUtil import getMemberById
from openPathUpdateSingle import openPathUpdateSingle
from openPathUtil import O_baseURL

# lambda_function lives in alta_open_lambda/, which is not a package
sys.path.insert(0, str(Path(__file__).parent.parent / "alta_open_lambda"))

import lambda_function as lf

# Stand-ins for neonUtil.MEMBERSHIP_ID_REGULAR and openPathUtil.GROUP_SUBSCRIBERS
REGULAR = 9001
SUBSCRIBERS = 9002
ALTA_ID = 456

# Arbitrary fixed date that every test treats as "today"
TODAY = datetime.date(2025, 3, 14)


def days(offset):
    return str(TODAY + datetime.timedelta(days=offset))


def at(day_offset, hour, minute):
    return datetime.datetime.combine(
        TODAY + datetime.timedelta(days=day_offset),
        datetime.time(hour, minute),
        tzinfo=lf.TZ,
    )


@pytest.fixture(autouse=True)
def fake_ids(mocker):
    mocker.patch("neonUtil.MEMBERSHIP_ID_REGULAR", REGULAR)
    mocker.patch("openPathUtil.GROUP_SUBSCRIBERS", SUBSCRIBERS)


@pytest.fixture(autouse=True)
def clock():
    # Midday by default, clear of midnight and the Lambda's 2:30-5:00 AM skip
    with freeze_time(at(0, 12, 0)) as frozen:
        yield frozen


def qualified_member():
    return NeonUserMock(
        waiver_date=days(-400), facility_tour_date=days(-399), open_path_id=ALTA_ID
    )


def mock_openpath_groups(requests_mock, current_groups):
    requests_mock.get(
        f"{O_baseURL}/users/{ALTA_ID}/groups",
        json={"data": [{"id": group} for group in current_groups]},
    )
    return requests_mock.put(f"{O_baseURL}/users/{ALTA_ID}/groupIds", status_code=204)


def is_active(account):
    return getMemberById(account.account_id).get("validMembership")


def webhook(event_trigger, data):
    """Lambda Function URL envelope around a Neon webhook body, in the current
    (non-legacy) format."""
    return {
        "body": json.dumps(
            {
                "eventTrigger": event_trigger,
                "data": data,
                "customParameters": None,
            }
        )
    }


def update_membership_event(account_id=12345):
    return webhook("updateMembership", {"accountId": str(account_id)})


def rejoin_event(account_id, term_start, term_end):
    return webhook(
        "createMembership",
        {
            "accountId": str(account_id),
            "membershipLevel": {"id": str(REGULAR), "name": "Regular Membership"},
            "enrollType": "REJOIN",
            "status": "SUCCEEDED",
            "termStartDate": term_start,
            "termEndDate": term_end,
            "fee": 95.0,
        },
    )


# ===========================================================================
# 1. The date is read on every call, not cached across midnight
# ===========================================================================


def test_renewal_starting_today_is_active(requests_mock):
    # Baseline: a member who lapsed a week ago and renewed today has access
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-37), days(-7), fee=95.0)
        .add_membership(REGULAR, days(0), days(29), fee=95.0)
    )
    account.mock(requests_mock)
    assert is_active(account) is True


def test_membership_starting_today_counts_once_past_midnight(requests_mock, clock):
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-32), days(-2), fee=95.0)
        .add_membership(REGULAR, days(0), days(30), fee=95.0)
    )
    account.mock(requests_mock)

    clock.move_to(at(-1, 23, 50))
    assert is_active(account) is False

    clock.move_to(at(0, 0, 36))
    assert is_active(account) is True


def test_membership_ending_yesterday_stops_counting_once_past_midnight(
    requests_mock, clock
):
    account = qualified_member().add_membership(
        REGULAR, days(-30), days(-1), fee=95.0
    )
    account.mock(requests_mock)

    clock.move_to(at(-1, 23, 50))
    assert is_active(account) is True

    clock.move_to(at(0, 0, 10))
    assert is_active(account) is False


def test_auto_renewal_stays_active_across_midnight(requests_mock, clock):
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-30), days(-1), fee=95.0, autoRenewal=True)
        .add_membership(REGULAR, days(0), days(29), fee=95.0, autoRenewal=True)
    )
    account.mock(requests_mock)

    clock.move_to(at(-1, 23, 50))
    assert is_active(account) is True

    clock.move_to(at(0, 0, 10))
    assert is_active(account) is True


def test_rejoin_after_midnight_restores_access_in_warm_lambda(
    requests_mock, clock, mocker
):
    # A member whose term lapsed two days ago rejoins just after midnight, and
    # the webhook lands in a Lambda container that already handled an event
    # the evening before. Access must be restored straight away rather than
    # at the next full sync.
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-32), days(-2), fee=95.0, autoRenewal=True)
        .add_membership(REGULAR, days(0), days(30), fee=95.0)
    )
    account.mock(requests_mock)
    put_groups = mock_openpath_groups(requests_mock, current_groups=[])
    add_to_mailjet = mocker.patch.object(lf, "add_member_to_mailjet")

    clock.move_to(at(-1, 23, 50))
    lf.lambda_handler(update_membership_event(account.account_id), {})
    assert not put_groups.called

    clock.move_to(at(0, 0, 36))
    lf.lambda_handler(rejoin_event(account.account_id, days(0), days(30)), {})

    assert put_groups.last_request.json() == {"groupIds": [SUBSCRIBERS]}
    # A rejoin two days after a lapse is not a new member
    add_to_mailjet.assert_not_called()


def test_renewal_webhook_after_midnight_restores_access_in_warm_lambda(
    requests_mock, clock
):
    # Same as above, but the renewal arrives as an updateMembership webhook
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-37), days(-7), fee=95.0)
        .add_membership(REGULAR, days(0), days(29), fee=95.0)
    )
    account.mock(requests_mock)
    put_groups = mock_openpath_groups(requests_mock, current_groups=[])

    clock.move_to(at(-1, 23, 50))
    lf.lambda_handler(update_membership_event(account.account_id), {})
    assert not put_groups.called

    clock.move_to(at(0, 0, 36))
    lf.lambda_handler(update_membership_event(account.account_id), {})

    assert put_groups.last_request.json() == {"groupIds": [SUBSCRIBERS]}


def test_auto_renew_grace_applies_the_day_after_expiry(requests_mock, clock):
    # The one-day grace for a pending auto-renewal ("expired yesterday") is
    # measured from the current date: it applies the day after the term ends
    # and not the day after that.
    account = qualified_member().add_membership(
        REGULAR, days(-30), days(-1), fee=95.0, autoRenewal=True
    )
    account.mock(requests_mock)

    clock.move_to(at(0, 0, 10))
    assert is_active(account) is True

    clock.move_to(at(1, 0, 10))
    assert is_active(account) is False


# ===========================================================================
# 2. Webhooks during the overnight quiet window are dropped
# ===========================================================================


@pytest.mark.parametrize(
    "hour,minute,handled",
    [
        (2, 29, True),
        (2, 30, False),
        (3, 0, False),
        (4, 59, False),
        (5, 0, True),
    ],
)
def test_webhooks_are_skipped_between_2_30_and_5_am(
    clock, mocker, hour, minute, handled
):
    # Nothing re-queues a skipped event, so a renewal in this window waits for
    # the next full sync.
    clock.move_to(at(0, hour, minute))
    update = mocker.patch.object(lf, "openPathUpdateSingle")

    lf.lambda_handler(update_membership_event(), {})

    assert update.called is handled


# ===========================================================================
# 3. Payment not settled when the webhook fires
# ===========================================================================


def test_pending_renewal_after_lapse_grants_no_access(requests_mock):
    # The Lambda re-reads memberships from Neon rather than trusting the
    # webhook payload. If Neon still reports the new term as PENDING (and the
    # old term ended more than a day ago, so the auto-renew grace does not
    # apply), no access is granted. Nothing checks the account again until
    # another webhook arrives for it or the next full sync runs.
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-37), days(-7), fee=95.0)
        .add_membership(REGULAR, days(0), days(29), fee=95.0, status="PENDING")
    )
    account.mock(requests_mock)
    put_groups = mock_openpath_groups(requests_mock, current_groups=[])

    openPathUpdateSingle(account.account_id)

    assert not put_groups.called


# ===========================================================================
# 4. Things the sync never checks on an existing OpenPath user
# ===========================================================================


def test_existing_user_status_and_credentials_are_never_checked(requests_mock):
    # For a member who already has an OpenPathID, the sync only compares and
    # sets group membership (openPathUpdateAll does the same). It never reads
    # the OpenPath user's status or credentials, so a user marked inactive in
    # OpenPath, or one whose mobile credential was deleted or never activated,
    # keeps the right groups but still cannot unlock a door.
    account = qualified_member().add_membership(
        REGULAR, days(-30), days(30), fee=95.0
    )
    account.mock(requests_mock)
    mock_openpath_groups(requests_mock, current_groups=[SUBSCRIBERS])
    requests_mock.reset_mock()

    openPathUpdateSingle(account.account_id)

    openpath_calls = [
        r.url.split("?")[0]
        for r in requests_mock.request_history
        if r.url.startswith(O_baseURL)
    ]
    assert openpath_calls == [f"{O_baseURL}/users/{ALTA_ID}/groups"]
