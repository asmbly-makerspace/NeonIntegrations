import neonUtil
from tests.neon_account_builder import today_plus
from tests.neon_api_fixtures import NeonMembershipBuilder


NEON_ID = 123
today = today_plus(0)


def test_appendMemberships_active_regular_paid(neon_api_mock):
    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership('2025-01-01', today, fee=50.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': today,
        'Membership Start Date': '2025-01-01',
        'membershipDates': {'2025-01-01': [today, 1]},
        'paidRegular': True,
        'validMembership': True,
    }


def test_appendMemberships_ceramics_comped(neon_api_mock):
    start = today_plus(-6 * 30)
    end = today_plus(6 * 30)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_ceramics_membership(start, end, fee=0.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
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


def test_appendMemberships_expired_yesterday_auto_renew(neon_api_mock):
    # expired yesterday but autoRenewal True and no current membership status -> treated as valid
    yesterday = today_plus(-1)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership('2024-01-01', yesterday, fee=25.0, autoRenewal=True)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'autoRenewal': True,
        'ceramicsMembership': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': yesterday,
        'Membership Start Date': '2024-01-01',
        'membershipDates': {'2024-01-01': [yesterday, 1]},
        'validMembership': True,
    }


def test_appendMemberships_overlapping_and_earliest_start(neon_api_mock):
    start0 = today_plus(-90)
    end0 = today_plus(-30)
    start1 = today_plus(-365)
    end1 = today_plus(365)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership(start0, end0, fee=20.0)
            .add_regular_membership(start1, end1, fee=20.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
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


def test_appendMemberships_concurrent_paid_regular_and_ceramics(neon_api_mock):
    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership('2025-01-01', today, fee=50.0)
            .add_ceramics_membership('2025-02-01', today, fee=60.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
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


def test_appendMemberships_future_start_not_active(neon_api_mock):
    # Membership starts in future -> not currently valid
    future_start = today_plus(10)
    future_end = today_plus(40)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership(future_start, future_end, fee=30.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': future_end,
        'Membership Start Date': today,
        'membershipDates': {future_start: [future_end, 1]},
        'validMembership': False,
    }


def test_appendMemberships_non_succeeded_status_ignored(neon_api_mock):
    # membership covers today but status is FAILED -> shouldn't count
    start = today_plus(-1)
    end = today_plus(1)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_membership(start, end, status='FAILED', fee=40.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'membershipDates': {},
        'validMembership': False,
    }


def test_appendMemberships_comped_regular(neon_api_mock):
    # comped regular membership
    start = today_plus(-10)
    end = today_plus(20)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership(start, end, fee=0.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'autoRenewal': False,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'compedRegular': True,
        'Membership Expiration Date': end,
        'Membership Start Date': start,
        'membershipDates': {start: [end, 1]},
        'validMembership': True,
    }


def test_appendMemberships_auto_renew_not_yesterday(neon_api_mock):
    # expired two days ago with autoRenewal True -> should NOT be treated as valid
    two_days_ago = today_plus(-2)

    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership('2024-01-01', two_days_ago, fee=25.0, autoRenewal=True)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
        'autoRenewal': True,
        'Ceramics Expiration Date': '1970-01-01',
        'Ceramics Start Date': today,
        'Membership Expiration Date': two_days_ago,
        'Membership Start Date': '2024-01-01',
        'membershipDates': {'2024-01-01': [two_days_ago, 1]},
        'validMembership': False,
    }


def test_appendMemberships_membershipDates_mapping_multiple(neon_api_mock):
    neon_api_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{NEON_ID}/memberships',
        json=NeonMembershipBuilder(account_id=NEON_ID)
            .add_regular_membership('2025-01-01', '2025-03-31', fee=10.0)
            .add_ceramics_membership('2025-04-01', '2025-06-30', fee=10.0)
            .build(),
    )

    assert neonUtil.appendMemberships({'Account ID': NEON_ID}) == {
        'Account ID': NEON_ID,
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
