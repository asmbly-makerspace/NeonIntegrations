import pytest

import neonUtil


class TestNeonUtil:
    def test_one(self):
        assert 1 == 1


def _fake_response(mocker, memberships):
    resp = mocker.Mock()
    resp.status_code = 200
    resp.json.return_value = {'memberships': memberships}
    return resp


def test_appendMemberships_active_regular_paid(mocker):
    acct = {'Account ID': 123}
    memberships = [
        {
            'termStartDate': '2025-01-01',
            'termEndDate': '2025-12-31',
            'status': 'SUCCEEDED',
            'fee': 50.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('paidRegular') is True
    assert updated.get('Membership Expiration Date') == '2025-12-31'
    assert '2025-01-01' in updated.get('membershipDates')
    assert updated['membershipDates']['2025-01-01'][0] == '2025-12-31'


def test_appendMemberships_ceramics_comped(mocker):
    acct = {'Account ID': 124}
    memberships = [
        {
            'termStartDate': '2025-06-01',
            'termEndDate': '2026-05-31',
            'status': 'SUCCEEDED',
            'fee': 0.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_CERAMICS},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('ceramicsMembership') is True
    assert updated.get('compedCeramics') is True
    assert updated.get('Ceramics Expiration Date') == '2026-05-31'


def test_appendMemberships_expired_yesterday_auto_renew(mocker):
    acct = {'Account ID': 125}
    yesterday = neonUtil.yesterday.strftime('%Y-%m-%d')
    memberships = [
        {
            'termStartDate': '2024-01-01',
            'termEndDate': yesterday,
            'status': 'SUCCEEDED',
            'fee': 25.0,
            'autoRenewal': True,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    # expired yesterday but autoRenewal True and no current membership status -> treated as valid
    assert updated.get('Membership Expiration Date') == yesterday
    assert updated.get('validMembership') is True


def test_appendMemberships_overlapping_and_earliest_start(mocker):
    acct = {'Account ID': 126}
    memberships = [
        {
            'termStartDate': '2025-03-01',
            'termEndDate': '2025-08-31',
            'status': 'SUCCEEDED',
            'fee': 20.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        },
        {
            'termStartDate': '2024-07-01',
            'termEndDate': '2026-06-30',
            'status': 'SUCCEEDED',
            'fee': 20.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    # earliest start should be 2024-07-01
    assert updated.get('Membership Start Date') == '2024-07-01'
    # latest expiration should be 2026-06-30
    assert updated.get('Membership Expiration Date') == '2026-06-30'


def test_appendMemberships_concurrent_paid_regular_and_ceramics(mocker):
    acct = {'Account ID': 127}
    memberships = [
        {
            'termStartDate': '2025-01-01',
            'termEndDate': '2025-12-31',
            'status': 'SUCCEEDED',
            'fee': 50.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        },
        {
            'termStartDate': '2025-02-01',
            'termEndDate': '2025-12-31',
            'status': 'SUCCEEDED',
            'fee': 60.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_CERAMICS},
        },
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('paidRegular') is True
    assert updated.get('paidCeramics') is True
    assert updated.get('ceramicsMembership') is True


def test_appendMemberships_future_start_not_active(mocker):
    acct = {'Account ID': 128}
    import datetime
    future_start = (neonUtil.today + datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    future_end = (neonUtil.today + datetime.timedelta(days=40)).strftime('%Y-%m-%d')
    memberships = [
        {
            'termStartDate': future_start,
            'termEndDate': future_end,
            'status': 'SUCCEEDED',
            'fee': 30.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    # Membership starts in future -> not currently valid
    assert updated.get('validMembership') is False


def test_appendMemberships_non_succeeded_status_ignored(mocker):
    acct = {'Account ID': 129}
    # membership covers today but status is FAILED -> shouldn't count
    import datetime
    start = (neonUtil.today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    end = (neonUtil.today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    memberships = [
        {
            'termStartDate': start,
            'termEndDate': end,
            'status': 'FAILED',
            'fee': 40.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is False
    # membershipDates dict should be empty because only SUCCEEDED statuses are recorded
    assert updated.get('membershipDates') == {}


def test_appendMemberships_comped_regular(mocker):
    acct = {'Account ID': 130}
    # comped regular membership
    memberships = [
        {
            'termStartDate': (neonUtil.today - __import__('datetime').timedelta(days=10)).strftime('%Y-%m-%d'),
            'termEndDate': (neonUtil.today + __import__('datetime').timedelta(days=20)).strftime('%Y-%m-%d'),
            'status': 'SUCCEEDED',
            'fee': 0.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('compedRegular') is True


def test_appendMemberships_auto_renew_not_yesterday(mocker):
    acct = {'Account ID': 131}
    # expired two days ago with autoRenewal True -> should NOT be treated as valid
    import datetime
    two_days_ago = (neonUtil.yesterday - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    memberships = [
        {
            'termStartDate': '2024-01-01',
            'termEndDate': two_days_ago,
            'status': 'SUCCEEDED',
            'fee': 25.0,
            'autoRenewal': True,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is False


def test_appendMemberships_membershipDates_mapping_multiple(mocker):
    acct = {'Account ID': 132}
    memberships = [
        {
            'termStartDate': '2025-01-01',
            'termEndDate': '2025-03-31',
            'status': 'SUCCEEDED',
            'fee': 10.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_REGULAR},
        },
        {
            'termStartDate': '2025-04-01',
            'termEndDate': '2025-06-30',
            'status': 'SUCCEEDED',
            'fee': 10.0,
            'autoRenewal': False,
            'membershipLevel': {'id': neonUtil.MEMBERSHIP_ID_CERAMICS},
        }
    ]

    mocker.patch('neonUtil.requests.get', return_value=_fake_response(mocker, memberships))

    updated = neonUtil.appendMemberships(acct)

    assert '2025-01-01' in updated.get('membershipDates')
    assert '2025-04-01' in updated.get('membershipDates')
    assert updated['membershipDates']['2025-04-01'][1] == neonUtil.MEMBERSHIP_ID_CERAMICS

