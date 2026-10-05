import logging

import pytest
import requests
from tenacity import wait_none

import neonUtil
from neonUtil import N_baseURL
from neon_mocker import NeonUserMock, today_plus, build_account_api_response, build_memberships_api_response


today = today_plus(0)

REGULAR = neonUtil.MEMBERSHIP_ID_REGULAR
CERAMICS = neonUtil.MEMBERSHIP_ID_CERAMICS


@pytest.fixture(autouse=True)
def _no_retry_wait():
    """Skip the retry backoff so tests don't sleep."""
    original_wait = neonUtil._neon_get.retry.wait
    neonUtil._neon_get.retry.wait = wait_none()
    yield
    neonUtil._neon_get.retry.wait = original_wait


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


# retries on the per-account GETs

@pytest.mark.parametrize('first_response', [
    {'status_code': 429, 'text': 'Too Many Requests'},
    {'status_code': 503, 'text': 'Service Unavailable'},
    {'exc': requests.exceptions.ConnectionError},
], ids=['429', '503', 'connection-error'])
def test_appendMemberships_retries_transient_error(requests_mock, caplog, first_response):
    account = NeonUserMock().add_membership(REGULAR, '2025-01-01', today, fee=50)
    account.mock(requests_mock)
    memberships = requests_mock.get(
        f'{N_baseURL}/accounts/{account.account_id}/memberships',
        [first_response, {'json': build_memberships_api_response(account.memberships)}],
    )

    with caplog.at_level(logging.WARNING):
        result = neonUtil.appendMemberships({'Account ID': account.account_id})

    assert result['validMembership'] is True
    assert memberships.call_count == 2
    assert 'retrying' in caplog.text


@pytest.mark.parametrize('response, expected_error, message', [
    ({'status_code': 503, 'text': 'Service Unavailable'}, ValueError, 'returned status code 503'),
    ({'exc': requests.exceptions.ConnectionError('reset')}, requests.exceptions.ConnectionError, 'reset'),
], ids=['503', 'connection-error'])
def test_appendMemberships_gives_up_after_three_attempts(requests_mock, response, expected_error, message):
    account = NeonUserMock().add_membership(REGULAR, '2025-01-01', today, fee=50)
    account.mock(requests_mock)
    memberships = requests_mock.get(
        f'{N_baseURL}/accounts/{account.account_id}/memberships', **response
    )

    # the original error, not a tenacity RetryError
    with pytest.raises(expected_error, match=message):
        neonUtil.appendMemberships({'Account ID': account.account_id})

    assert memberships.call_count == 3


def test_appendMemberships_does_not_retry_404(requests_mock):
    account = NeonUserMock().add_membership(REGULAR, '2025-01-01', today, fee=50)
    account.mock(requests_mock)
    memberships = requests_mock.get(
        f'{N_baseURL}/accounts/{account.account_id}/memberships',
        status_code=404, text='Not Found',
    )

    with pytest.raises(ValueError, match='returned status code 404'):
        neonUtil.appendMemberships({'Account ID': account.account_id})

    assert memberships.call_count == 1


def test_neon_get_does_not_retry_222(requests_mock):
    # 222 (merged account) isn't transient; getMemberById checks the status itself
    url = f'{N_baseURL}/accounts/123'
    merged = requests_mock.get(url, status_code=222, json=build_account_api_response(123))

    assert neonUtil._neon_get(url).status_code == 222
    assert merged.call_count == 1


def test_getMemberById_retries_transient_account_error(requests_mock):
    account = NeonUserMock().add_membership(REGULAR, '2025-01-01', today, fee=50)
    account.mock(requests_mock)
    account_get = requests_mock.get(
        f'{N_baseURL}/accounts/{account.account_id}',
        [
            {'status_code': 502, 'text': 'Bad Gateway'},
            {'json': build_account_api_response(accountId=account.account_id)},
        ],
    )

    result = neonUtil.getMemberById(account.account_id)

    assert result['Account ID'] == account.account_id
    assert result['validMembership'] is True
    assert account_get.call_count == 2


def _mock_real_accounts(requests_mock, count):
    accounts = [
        NeonUserMock(account_id=i).add_membership(REGULAR, '2025-01-01', today_plus(30), fee=50)
        for i in range(1, count + 1)
    ]
    NeonUserMock.mock_search(requests_mock, accounts)
    return accounts


def test_getRealAccounts_survives_one_429(requests_mock):
    accounts = _mock_real_accounts(requests_mock, 5)
    throttled = accounts[2]
    memberships = requests_mock.get(
        f'{N_baseURL}/accounts/{throttled.account_id}/memberships',
        [
            {'status_code': 429, 'text': 'Too Many Requests'},
            {'json': build_memberships_api_response(throttled.memberships)},
        ],
    )

    result = neonUtil.getRealAccounts()

    assert memberships.call_count == 2
    assert sorted(result) == [str(a.account_id) for a in accounts]
    assert all(account['validMembership'] for account in result.values())


def test_getRealAccounts_still_raises_when_an_account_keeps_failing(requests_mock):
    # treating the account as a non-member would revoke a paying member's door access
    accounts = _mock_real_accounts(requests_mock, 5)
    requests_mock.get(
        f'{N_baseURL}/accounts/{accounts[2].account_id}/memberships',
        status_code=503, text='Service Unavailable',
    )

    with pytest.raises(ValueError, match='returned status code 503'):
        neonUtil.getRealAccounts()
