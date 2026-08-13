import neonUtil
from neon_mocker import (
    NeonUserMock,
    today_plus,
    build_account_api_response,
    build_memberships_api_response,
)
from neonUtil import N_baseURL


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


# ---------------------------------------------------------------------------
# getMemberById custom-field flattening
#
# getMemberById raises the account's custom fields to top-level keys.  Neon
# returns option-type fields (checkbox/dropdown/radio) as an ``optionValues``
# list, one entry per selected option.  These tests cover that branch, which
# previously had no coverage.
# ---------------------------------------------------------------------------

def _mock_account_with_custom_fields(requests_mock, custom_fields, account_id=4242):
    requests_mock.get(
        f"{N_baseURL}/accounts/{account_id}",
        json=build_account_api_response(
            accountId=account_id,
            accountCustomFields=custom_fields,
        ),
    )
    requests_mock.get(
        f"{N_baseURL}/accounts/{account_id}/memberships",
        json=build_memberships_api_response([]),
    )
    return account_id


def test_getMemberById_plain_value_custom_field(requests_mock):
    account_id = _mock_account_with_custom_fields(
        requests_mock, [{"id": "1", "name": "DiscourseID", "value": "someuser"}]
    )
    account = neonUtil.getMemberById(account_id)
    assert account["DiscourseID"] == "someuser"


def test_getMemberById_single_option_field(requests_mock):
    # A checked Yes/No checkbox returns a single selected option.
    account_id = _mock_account_with_custom_fields(
        requests_mock,
        [{"id": "120", "name": "AccessSuspended",
          "optionValues": [{"id": "30", "name": "Yes"}]}],
    )
    account = neonUtil.getMemberById(account_id)
    assert account["AccessSuspended"] == "Yes"


def test_getMemberById_multi_option_field_keeps_all_values(requests_mock):
    # A multi-select field reports every selected option; none may be dropped.
    account_id = _mock_account_with_custom_fields(
        requests_mock,
        [{"id": "95", "name": "Family Group Member Names",
          "optionValues": [
              {"id": "1", "name": "Jane Roe"},
              {"id": "2", "name": "John Roe"},
          ]}],
    )
    account = neonUtil.getMemberById(account_id)
    assert account["Family Group Member Names"] == "Jane Roe, John Roe"


def test_getMemberById_option_without_name_falls_back_to_value(requests_mock):
    account_id = _mock_account_with_custom_fields(
        requests_mock,
        [{"id": "92", "name": "FamilyGroupPrimaryMember",
          "optionValues": [{"id": "1", "value": "Yes"}]}],
    )
    account = neonUtil.getMemberById(account_id)
    assert account["FamilyGroupPrimaryMember"] == "Yes"


def test_getMemberById_empty_option_field_does_not_crash(requests_mock):
    # An option field with no selected option (e.g. an unchecked checkbox) must
    # not abort the whole account fetch.  The field is simply omitted, and the
    # rest of the account still loads.
    account_id = _mock_account_with_custom_fields(
        requests_mock,
        [
            {"id": "91", "name": "Family Group Sub Member", "optionValues": []},
            {"id": "1", "name": "DiscourseID", "value": "someuser"},
        ],
    )
    account = neonUtil.getMemberById(account_id)
    assert "Family Group Sub Member" not in account
    assert account["DiscourseID"] == "someuser"


def test_getMemberById_valueless_custom_field_does_not_crash(requests_mock):
    account_id = _mock_account_with_custom_fields(
        requests_mock,
        [
            {"id": "5", "name": "SomeBlankField"},
            {"id": "1", "name": "DiscourseID", "value": "someuser"},
        ],
    )
    account = neonUtil.getMemberById(account_id)
    assert "SomeBlankField" not in account
    assert account["DiscourseID"] == "someuser"
