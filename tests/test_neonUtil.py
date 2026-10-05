import datetime
from types import SimpleNamespace

import pytest
import pytz

import neonUtil
from neon_mocker import NeonUserMock, today_plus


today = today_plus(0)

REGULAR = neonUtil.MEMBERSHIP_ID_REGULAR
CERAMICS = neonUtil.MEMBERSHIP_ID_CERAMICS


def test_appendMemberships_active_regular_paid(requests_mock):
    account = NeonUserMock().add_membership(REGULAR, '2025-01-01', today, fee=50)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': today,
        'Membership Start Date': '2025-01-01',
        'membershipDates': {'2025-01-01': [today, 1]},
        'paidRegular': True,
        'validMembership': True,
    }


def test_appendMemberships_ceramics_comped(requests_mock):
    start = today_plus(-6 * 30)
    end = today_plus(6 * 30)

    account = NeonUserMock().add_membership(CERAMICS, start, end)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': end,
        'Ceramics Start Date': start,
        'ceramicsMembership': True,
        'compedCeramics': True,
        'Membership Expiration Date': end,
        'Membership Start Date': start,
        'membershipDates': {start: [end, 7]},
        'validMembership': True,
    }


def test_appendMemberships_expired_yesterday_auto_renew(requests_mock):
    yesterday = today_plus(-1)

    account = NeonUserMock().add_membership(REGULAR, '2024-01-01', yesterday, autoRenewal=True)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': True,
        'ceramicsMembership': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': yesterday,
        'Membership Start Date': '2024-01-01',
        'membershipDates': {'2024-01-01': [yesterday, 1]},
        'validMembership': True,
    }


def test_appendMemberships_overlapping_and_earliest_start(requests_mock):
    start0 = today_plus(-90)
    end0 = today_plus(-30)
    start1 = today_plus(-365)
    end1 = today_plus(365)

    account = NeonUserMock()\
        .add_membership(REGULAR, start0, end0, fee=20.0)\
        .add_membership(REGULAR, start1, end1, fee=20.0)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': end1,
        'Membership Start Date': start1,
        'membershipDates': {
            start0: [end0, 1],
            start1: [end1, 1],
        },
        'paidRegular': True,
        'validMembership': True,
    }


def test_appendMemberships_concurrent_paid_regular_and_ceramics(requests_mock):
    account = NeonUserMock()\
        .add_membership(REGULAR, '2025-01-01', today, fee=50.0)\
        .add_membership(CERAMICS, '2025-02-01', today, fee=60.0)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'ceramicsMembership': True,
        'Ceramics Expiration Date': today,
        'Ceramics Start Date': today,
        'Membership Expiration Date': today,
        'Membership Start Date': '2025-01-01',
        'membershipDates': {
            '2025-01-01': [today, 1],
            '2025-02-01': [today, 7],
        },
        'paidCeramics': True,
        'paidRegular': True,
        'validMembership': True,
    }


def test_appendMemberships_future_start_not_active(requests_mock):
    future_start = today_plus(10)
    future_end = today_plus(40)

    account = NeonUserMock().add_membership(REGULAR, future_start, future_end, fee=30.0)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': future_end,
        'Membership Start Date': today,
        'membershipDates': {future_start: [future_end, 1]},
        'validMembership': False,
    }


def test_appendMemberships_non_succeeded_status_ignored(requests_mock):
    start = today_plus(-1)
    end = today_plus(1)

    account = NeonUserMock().add_membership(REGULAR, start, end, status='FAILED', fee=40.0)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'membershipDates': {},
        'validMembership': False,
    }


def test_appendMemberships_comped_regular(requests_mock):
    start = today_plus(-10)
    end = today_plus(20)

    account = NeonUserMock().add_membership(REGULAR, start, end, fee=0.0)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'compedRegular': True,
        'Membership Expiration Date': end,
        'Membership Start Date': start,
        'membershipDates': {start: [end, 1]},
        'validMembership': True,
    }


def test_appendMemberships_auto_renew_not_yesterday(requests_mock):
    two_days_ago = today_plus(-2)

    account = NeonUserMock().add_membership(REGULAR, '2024-01-01', two_days_ago, fee=25.0, autoRenewal=True)
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': True,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': two_days_ago,
        'Membership Start Date': '2024-01-01',
        'membershipDates': {'2024-01-01': [two_days_ago, 1]},
        'validMembership': False,
    }


def test_appendMemberships_membershipDates_mapping_multiple(requests_mock):
    account = NeonUserMock()\
        .add_membership(REGULAR, '2025-01-01', '2025-03-31')\
        .add_membership(CERAMICS, '2025-04-01', '2025-06-30')
    account.mock(requests_mock)

    assert neonUtil.appendMemberships({'Account ID': account.account_id}) == {
        'Account ID': account.account_id,
        'autoRenewal': False,
        'Ceramics Expiration Date': '2025-06-30',
        'Ceramics Start Date': today,
        'Membership Expiration Date': '2025-06-30',
        'Membership Start Date': '2025-01-01',
        'membershipDates': {
            '2025-01-01': ['2025-03-31', 1],
            '2025-04-01': ['2025-06-30', 7],
        },
        'validMembership': False,
    }


CHICAGO = pytz.timezone("America/Chicago")


@pytest.fixture
def clock(monkeypatch):
    """Lets a test choose the current time that neonUtil sees.

    clock.set(t1, t2, ...) makes successive datetime.now() calls inside neonUtil
    return those Central times in order; the last one repeats.
    """
    readings = []

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            t = readings.pop(0) if len(readings) > 1 else readings[0]
            return CHICAGO.localize(t).astimezone(tz)

    def setTimes(*times):
        readings[:] = times
        # swap only neonUtil's reference to the datetime module, not the real module
        monkeypatch.setattr(neonUtil, 'datetime', SimpleNamespace(
            datetime=FakeDatetime, date=datetime.date, timedelta=datetime.timedelta))

    return SimpleNamespace(set=setTimes)


# The Lambda imports neonUtil once per container and reuses it for every warm
# invocation, so a container started before midnight keeps handling webhooks
# after it.  Here neonUtil was imported at 23:50 on 2026-10-05 and the webhook
# arrives at 00:10 on 2026-10-06, so memberships must be judged against the 6th.
@pytest.mark.parametrize('start, end, autoRenewal, expected', [
    ('2026-10-06', '2026-11-05', False, True),   # term starts today (member just paid)
    ('2026-09-05', '2026-10-05', False, False),  # term ended yesterday, no auto-renewal
    ('2026-09-05', '2026-10-05', True, True),    # term ended yesterday, renewal pending: grace day
    ('2026-09-04', '2026-10-04', True, False),   # term ended two days ago: grace day is over
])
def test_appendMemberships_uses_date_of_call_not_import(requests_mock, monkeypatch, clock,
                                                         start, end, autoRenewal, expected):
    # what neonUtil computed when the container imported it at 23:50 on the 5th
    monkeypatch.setattr(neonUtil, 'today', datetime.date(2026, 10, 5))
    monkeypatch.setattr(neonUtil, 'yesterday', datetime.date(2026, 10, 4))
    clock.set(datetime.datetime(2026, 10, 6, 0, 10))

    account = NeonUserMock().add_membership(REGULAR, start, end, fee=50.0, autoRenewal=autoRenewal)

    # mock() returns neonUtil.getMemberById(), which is what the Lambda calls
    assert account.mock(requests_mock)['validMembership'] is expected


# getRealAccounts reads the date once when it starts and judges every account
# against that day, even if the run (or a warm Lambda) crosses midnight.
def test_getRealAccounts_uses_one_date_for_the_whole_run(requests_mock, monkeypatch, clock):
    # neonUtil was imported the day before; that must not matter
    monkeypatch.setattr(neonUtil, 'today', datetime.date(2026, 10, 4))
    monkeypatch.setattr(neonUtil, 'yesterday', datetime.date(2026, 10, 3))

    startsToday = NeonUserMock(1).add_membership(REGULAR, '2026-10-05', '2026-11-04', fee=50.0)
    endedYesterday = NeonUserMock(2).add_membership(REGULAR, '2026-09-04', '2026-10-04', fee=50.0, autoRenewal=True)
    endedTwoDaysAgo = NeonUserMock(3).add_membership(REGULAR, '2026-09-03', '2026-10-03', fee=50.0, autoRenewal=True)
    NeonUserMock.mock_search(requests_mock, [startsToday, endedYesterday, endedTwoDaysAgo])

    # the run starts at 23:59 on the 5th; any later reading of the clock is past midnight
    clock.set(datetime.datetime(2026, 10, 5, 23, 59), datetime.datetime(2026, 10, 6, 0, 1))
    accounts = neonUtil.getRealAccounts()

    assert accounts['1']['validMembership'] is True    # term started today
    assert accounts['2']['validMembership'] is True    # grace day for the pending renewal
    assert accounts['3']['validMembership'] is False   # grace day is over
