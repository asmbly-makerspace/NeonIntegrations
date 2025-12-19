import neonUtil
from tests.neon_api_fixtures import NeonMembershipBuilder


class TestNeonUtil:
    def test_one(self):
        assert 1 == 1


def test_appendMemberships_active_regular_paid(neon_api_mock):
    acct = {'Account ID': 123}

    builder = NeonMembershipBuilder(account_id=123)
    builder.add_regular_membership('2025-01-01', '2025-12-31', fee=50.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/123/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('paidRegular') is True
    assert updated.get('Membership Expiration Date') == '2025-12-31'
    assert '2025-01-01' in updated.get('membershipDates')
    assert updated['membershipDates']['2025-01-01'][0] == '2025-12-31'


def test_appendMemberships_ceramics_comped(neon_api_mock):
    acct = {'Account ID': 124}

    builder = NeonMembershipBuilder(account_id=124)
    builder.add_ceramics_membership('2025-06-01', '2026-05-31', fee=0.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/124/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('ceramicsMembership') is True
    assert updated.get('compedCeramics') is True
    assert updated.get('Ceramics Expiration Date') == '2026-05-31'


def test_appendMemberships_expired_yesterday_auto_renew(neon_api_mock):
    acct = {'Account ID': 125}
    yesterday = neonUtil.yesterday.strftime('%Y-%m-%d')

    builder = NeonMembershipBuilder(account_id=125)
    builder.add_regular_membership(
        '2024-01-01',
        yesterday,
        fee=25.0,
        autoRenewal=True
    )

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/125/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    # expired yesterday but autoRenewal True and no current membership status -> treated as valid
    assert updated.get('Membership Expiration Date') == yesterday
    assert updated.get('validMembership') is True


def test_appendMemberships_overlapping_and_earliest_start(neon_api_mock):
    acct = {'Account ID': 126}

    builder = NeonMembershipBuilder(account_id=126)
    builder.add_regular_membership('2025-03-01', '2025-08-31', fee=20.0)
    builder.add_regular_membership('2024-07-01', '2026-06-30', fee=20.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/126/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    # earliest start should be 2024-07-01
    assert updated.get('Membership Start Date') == '2024-07-01'
    # latest expiration should be 2026-06-30
    assert updated.get('Membership Expiration Date') == '2026-06-30'


def test_appendMemberships_concurrent_paid_regular_and_ceramics(neon_api_mock):
    acct = {'Account ID': 127}

    builder = NeonMembershipBuilder(account_id=127)
    builder.add_regular_membership('2025-01-01', '2025-12-31', fee=50.0)
    builder.add_ceramics_membership('2025-02-01', '2025-12-31', fee=60.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/127/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('paidRegular') is True
    assert updated.get('paidCeramics') is True
    assert updated.get('ceramicsMembership') is True


def test_appendMemberships_future_start_not_active(neon_api_mock):
    acct = {'Account ID': 128}
    import datetime
    future_start = (neonUtil.today + datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    future_end = (neonUtil.today + datetime.timedelta(days=40)).strftime('%Y-%m-%d')

    builder = NeonMembershipBuilder(account_id=128)
    builder.add_regular_membership(future_start, future_end, fee=30.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/128/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    # Membership starts in future -> not currently valid
    assert updated.get('validMembership') is False


def test_appendMemberships_non_succeeded_status_ignored(neon_api_mock):
    acct = {'Account ID': 129}
    # membership covers today but status is FAILED -> shouldn't count
    import datetime
    start = (neonUtil.today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    end = (neonUtil.today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    builder = NeonMembershipBuilder(account_id=129)
    builder.add_membership(start, end, status='FAILED', fee=40.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/129/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is False
    # membershipDates dict should be empty because only SUCCEEDED statuses are recorded
    assert updated.get('membershipDates') == {}


def test_appendMemberships_comped_regular(neon_api_mock):
    acct = {'Account ID': 130}
    # comped regular membership
    import datetime
    start = (neonUtil.today - datetime.timedelta(days=10)).strftime('%Y-%m-%d')
    end = (neonUtil.today + datetime.timedelta(days=20)).strftime('%Y-%m-%d')

    builder = NeonMembershipBuilder(account_id=130)
    builder.add_regular_membership(start, end, fee=0.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/130/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is True
    assert updated.get('compedRegular') is True


def test_appendMemberships_auto_renew_not_yesterday(neon_api_mock):
    acct = {'Account ID': 131}
    # expired two days ago with autoRenewal True -> should NOT be treated as valid
    import datetime
    two_days_ago = (neonUtil.yesterday - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    builder = NeonMembershipBuilder(account_id=131)
    builder.add_regular_membership('2024-01-01', two_days_ago, fee=25.0, autoRenewal=True)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/131/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert updated.get('validMembership') is False


def test_appendMemberships_membershipDates_mapping_multiple(neon_api_mock):
    acct = {'Account ID': 132}

    builder = NeonMembershipBuilder(account_id=132)
    builder.add_regular_membership('2025-01-01', '2025-03-31', fee=10.0)
    builder.add_ceramics_membership('2025-04-01', '2025-06-30', fee=10.0)

    neon_api_mock.get(
        'https://api.neoncrm.com/v2/accounts/132/memberships',
        json=builder.build()
    )

    updated = neonUtil.appendMemberships(acct)

    assert '2025-01-01' in updated.get('membershipDates')
    assert '2025-04-01' in updated.get('membershipDates')
    assert updated['membershipDates']['2025-04-01'][1] == neonUtil.MEMBERSHIP_ID_CERAMICS
