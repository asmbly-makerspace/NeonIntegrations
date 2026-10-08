"""
Paths through the webhook -> Neon -> OpenPath sync that can leave a member who
qualifies for access locked out, or let one keep access too long.

- Section 1 is a regression suite: the Lambda reuses imported modules across
  invocations, so membership checks must read the date on every call. When
  neonUtil cached it at import, a member who rejoined shortly after midnight
  got no access until the overnight full sync.
- Sections 2-4 characterize current behavior. Sections 2 and 3 can delay
  access until the next full sync (dailyMaintenance.py). Section 4 is never
  corrected by either sync.

The clock seen by neonUtil and lambda_function is frozen on a fixed date, so
these tests don't depend on when the suite runs.
"""

import datetime
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import neonUtil
from neon_mocker import NeonUserMock
from neonUtil import MEMBERSHIP_ID_REGULAR
from openPathUpdateSingle import openPathUpdateSingle
from openPathUtil import GROUP_SUBSCRIBERS, O_baseURL

# lambda_function lives in alta_open_lambda/, which is not a package
sys.path.insert(0, str(Path(__file__).parent.parent / "alta_open_lambda"))

import lambda_function as lf

REGULAR = MEMBERSHIP_ID_REGULAR
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


class FrozenClock:
    """Replaces the `datetime` module seen by the given modules with one whose
    datetime.now() returns a controllable time. Everything else in the module
    (strptime, timedelta, date, ...) is the real thing. Call set() to move the
    clock, e.g. across midnight within one test."""

    def __init__(self, mocker, modules, at):
        self.current = at
        clock = self

        class FrozenDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return clock.current.replace(tzinfo=None)
                return clock.current.astimezone(tz)

        fake_module = SimpleNamespace(
            **{
                name: getattr(datetime, name)
                for name in dir(datetime)
                if not name.startswith("__")
            }
        )
        fake_module.datetime = FrozenDatetime
        for module in modules:
            mocker.patch.object(module, "datetime", fake_module)

    def set(self, at):
        self.current = at


@pytest.fixture(autouse=True)
def clock(mocker):
    # Midday by default, clear of midnight and the Lambda's 2:30-5:00 AM skip
    return FrozenClock(mocker, [neonUtil, lf], at=at(0, 12, 0))


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
    return neonUtil.getMemberById(account.account_id).get("validMembership")


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
            "membershipLevel": {"id": "1", "name": "Regular Membership"},
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

    clock.set(at(-1, 23, 50))
    assert is_active(account) is False

    clock.set(at(0, 0, 36))
    assert is_active(account) is True


def test_membership_ending_yesterday_stops_counting_once_past_midnight(
    requests_mock, clock
):
    account = qualified_member().add_membership(
        REGULAR, days(-30), days(-1), fee=95.0
    )
    account.mock(requests_mock)

    clock.set(at(-1, 23, 50))
    assert is_active(account) is True

    clock.set(at(0, 0, 10))
    assert is_active(account) is False


def test_auto_renewal_stays_active_across_midnight(requests_mock, clock):
    account = (
        qualified_member()
        .add_membership(REGULAR, days(-30), days(-1), fee=95.0, autoRenewal=True)
        .add_membership(REGULAR, days(0), days(29), fee=95.0, autoRenewal=True)
    )
    account.mock(requests_mock)

    clock.set(at(-1, 23, 50))
    assert is_active(account) is True

    clock.set(at(0, 0, 10))
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

    clock.set(at(-1, 23, 50))
    lf.lambda_handler(update_membership_event(account.account_id), {})
    assert not put_groups.called

    clock.set(at(0, 0, 36))
    lf.lambda_handler(rejoin_event(account.account_id, days(0), days(30)), {})

    assert put_groups.last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}
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

    clock.set(at(-1, 23, 50))
    lf.lambda_handler(update_membership_event(account.account_id), {})
    assert not put_groups.called

    clock.set(at(0, 0, 36))
    lf.lambda_handler(update_membership_event(account.account_id), {})

    assert put_groups.last_request.json() == {"groupIds": [GROUP_SUBSCRIBERS]}


def test_auto_renew_grace_applies_the_day_after_expiry(requests_mock, clock):
    # The one-day grace for a pending auto-renewal ("expired yesterday") is
    # measured from the current date: it applies the day after the term ends
    # and not the day after that.
    account = qualified_member().add_membership(
        REGULAR, days(-30), days(-1), fee=95.0, autoRenewal=True
    )
    account.mock(requests_mock)

    clock.set(at(0, 0, 10))
    assert is_active(account) is True

    clock.set(at(1, 0, 10))
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
    clock.set(at(0, hour, minute))
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
    # apply), no access is granted. Access then depends on another webhook
    # once the payment succeeds, or on the next full sync.
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
    mock_openpath_groups(requests_mock, current_groups=[GROUP_SUBSCRIBERS])
    requests_mock.reset_mock()

    openPathUpdateSingle(account.account_id)

    openpath_calls = [
        r.url.split("?")[0]
        for r in requests_mock.request_history
        if r.url.startswith(O_baseURL)
    ]
    assert openpath_calls == [f"{O_baseURL}/users/{ALTA_ID}/groups"]
