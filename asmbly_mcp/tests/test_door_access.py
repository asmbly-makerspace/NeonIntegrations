import itertools

import pytest

import neonUtil
import openPathUtil
from asmbly_mcp import door_access
from asmbly_mcp.door_access import PASS, FAIL, WARN, SKIP
from neon_mocker import NeonUserMock, today_plus
from neonUtil import (
    MEMBERSHIP_ID_REGULAR, N_baseURL, STAFF_TYPE, LEAD_TYPE, DIRECTOR_TYPE, SUPER_TYPE,
    COWORKING_TYPE, STEWARD_TYPE, INSTRUCTOR_TYPE, ONDUTY_TYPE,
)
from openPathUtil import GROUP_SUBSCRIBERS, GROUP_SPECIAL_EVENT, GROUP_MANAGEMENT, O_baseURL


ALTA_ID = 456
start = today_plus(-30)
tour = today_plus(-29)
end = today_plus(30)


def mock_alta(rm, status="A", groups=None, creds=None):
    rm.get(f"{O_baseURL}/users/{ALTA_ID}", json={"data": {"id": ALTA_ID, "status": status}})
    rm.get(f"{O_baseURL}/users/{ALTA_ID}/groups", json={"data": groups if groups is not None else []})
    rm.get(f"{O_baseURL}/users/{ALTA_ID}/credentials",
           json={"data": creds if creds is not None else []})


def statuses(result):
    return {c["check"]: c["status"] for c in result["checks"]}


def good_member(**kwargs):
    args = dict(waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)
    args.update(kwargs)
    return NeonUserMock(**args).add_membership(MEMBERSHIP_ID_REGULAR, start, end, fee=100.0)


MOBILE = [{"id": 1, "mobile": {"name": "Automatic Mobile Credential"}}]


def test_everything_ok(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SUBSCRIBERS, "name": "Subscribers"}], creds=MOBILE)

    result = door_access.diagnose(account.account_id)

    assert set(statuses(result).values()) == {PASS}
    assert "Everything checks out" in result["verdict"]
    # never writes anything
    assert all(r.method in ("GET", "POST") for r in requests_mock.request_history)
    assert all(r.method == "GET" or r.url.endswith("/accounts/search")
               for r in requests_mock.request_history)


def test_suspended_member_flags_suspension_and_extra_group(requests_mock):
    account = good_member(access_suspended=True)
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SUBSCRIBERS, "name": "Subscribers"}], creds=MOBILE)

    result = door_access.diagnose(account.account_id)
    s = statuses(result)

    assert s["Access not suspended"] == FAIL
    assert s["Alta Open groups correct"] == WARN
    assert result["verdict"].startswith("Problem found: Access not suspended")
    assert "may keep working" in result["verdict"]


def test_missing_waiver_and_tour_without_alta_account(requests_mock):
    account = NeonUserMock().add_membership(MEMBERSHIP_ID_REGULAR, start, end, fee=100.0)
    account.mock(requests_mock)

    result = door_access.diagnose(account.account_id)
    s = statuses(result)

    assert s["Membership paid and current"] == PASS
    assert s["Waiver signed"] == FAIL
    assert s["Orientation completed"] == FAIL
    assert s["Alta Open account exists"] == SKIP


def test_failed_payment_is_explained(requests_mock):
    account = NeonUserMock(waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID)\
        .add_membership(MEMBERSHIP_ID_REGULAR, today_plus(-60), today_plus(-31), fee=100.0)\
        .add_membership(MEMBERSHIP_ID_REGULAR, today_plus(-30), end, status="FAILED", fee=100.0)
    account.mock(requests_mock)
    mock_alta(requests_mock, creds=MOBILE)

    result = door_access.diagnose(account.account_id)
    membership = result["checks"][0]

    assert membership["status"] == FAIL
    assert "FAILED" in membership["detail"]


def test_valid_member_missing_group_and_credential(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SPECIAL_EVENT, "name": "Special Event"}])

    result = door_access.diagnose(account.account_id)
    s = statuses(result)

    assert s["Alta Open groups correct"] == FAIL
    assert s["Has a door credential"] == FAIL
    assert "openPathUpdateSingle.py" in door_access.formatReport(result)


def test_valid_member_without_alta_account(requests_mock):
    account = good_member(open_path_id=None)
    account.mock(requests_mock)

    result = door_access.diagnose(account.account_id)

    assert statuses(result)["Alta Open account exists"] == FAIL


def test_inactive_alta_user(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, status="I", groups=[{"id": GROUP_SUBSCRIBERS}], creds=MOBILE)

    result = door_access.diagnose(account.account_id)

    assert statuses(result)["Alta Open account active"] == FAIL


NEON_CHECKS = ["Membership paid and current", "Access not suspended", "Waiver signed", "Orientation completed"]


def mock_alta_with_expected_groups(rm, neonAccount):
    groups = [{"id": g} for g in openPathUtil.getOpGroups(neonAccount)]
    mock_alta(rm, groups=groups, creds=MOBILE)


def test_staff_without_membership_is_ok(requests_mock):
    account = NeonUserMock(open_path_id=ALTA_ID, individualTypes=[STAFF_TYPE])
    mock_alta_with_expected_groups(requests_mock, account.mock(requests_mock))

    result = door_access.diagnose(account.account_id)
    s = statuses(result)

    assert s["Membership paid and current"] == SKIP
    assert s["Waiver signed"] == SKIP
    assert s["Orientation completed"] == SKIP
    assert FAIL not in s.values()
    assert result["shouldHaveDoorAccess"]
    assert "Everything checks out" in result["verdict"]

    report = door_access.formatReport(result)
    assert f"Account type: {STAFF_TYPE}" in report
    assert f"a {STAFF_TYPE} account doesn't need a paid membership" in report


def test_leader_gets_management_without_membership(requests_mock):
    account = NeonUserMock(open_path_id=ALTA_ID, individualTypes=[DIRECTOR_TYPE])
    neonAccount = account.mock(requests_mock)
    assert openPathUtil.getOpGroups(neonAccount) == [GROUP_MANAGEMENT]
    mock_alta_with_expected_groups(requests_mock, neonAccount)

    result = door_access.diagnose(account.account_id)

    assert FAIL not in statuses(result).values()
    assert result["shouldHaveDoorAccess"]


def test_suspended_staff_is_a_warning_not_a_failure(requests_mock):
    account = NeonUserMock(open_path_id=ALTA_ID, individualTypes=[STAFF_TYPE], access_suspended=True)
    mock_alta_with_expected_groups(requests_mock, account.mock(requests_mock))

    result = door_access.diagnose(account.account_id)

    assert statuses(result)["Access not suspended"] == WARN
    assert "still have access" in result["checks"][1]["detail"]
    assert result["verdict"].startswith("Should work")


def test_coworking_tenant_can_have_lapsed_membership(requests_mock):
    account = NeonUserMock(waiver_date=start, facility_tour_date=tour, open_path_id=ALTA_ID,
                           individualTypes=[COWORKING_TYPE])\
        .add_membership(MEMBERSHIP_ID_REGULAR, today_plus(-90), today_plus(-60), fee=100.0)
    mock_alta_with_expected_groups(requests_mock, account.mock(requests_mock))

    result = door_access.diagnose(account.account_id)
    s = statuses(result)

    assert s["Membership paid and current"] == SKIP
    assert FAIL not in s.values()


def test_coworking_tenant_still_needs_waiver(requests_mock):
    account = NeonUserMock(facility_tour_date=tour, individualTypes=[COWORKING_TYPE])
    account.mock(requests_mock)

    s = statuses(door_access.diagnose(account.account_id))

    assert s["Membership paid and current"] == SKIP
    assert s["Waiver signed"] == FAIL


def test_regular_member_report_names_account_type(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SUBSCRIBERS}], creds=MOBILE)

    report = door_access.formatReport(door_access.diagnose(account.account_id))

    assert "Account type: regular member" in report


# The report's exemptions are written out by hand, so make sure they always agree with
# what the real sync would grant (neonUtil.accountHasFacilityAccess / openPathUtil.getOpGroups).
@pytest.mark.parametrize("accountType", [
    None, STAFF_TYPE, LEAD_TYPE, DIRECTOR_TYPE, SUPER_TYPE, COWORKING_TYPE,
    STEWARD_TYPE, INSTRUCTOR_TYPE, ONDUTY_TYPE,
])
def test_report_agrees_with_real_sync_rules(requests_mock, accountType):
    for paid, waiver, toured, suspended in itertools.product([True, False], repeat=4):
        account = NeonUserMock(
            waiver_date=start if waiver else None,
            facility_tour_date=tour if toured else None,
            access_suspended=suspended,
            individualTypes=[accountType] if accountType else None,
        )
        if paid:
            account.add_membership(MEMBERSHIP_ID_REGULAR, start, end, fee=100.0)
        neonAccount = account.mock(requests_mock)
        syncGrantsAccess = (neonUtil.accountHasFacilityAccess(neonAccount)
                            or GROUP_MANAGEMENT in openPathUtil.getOpGroups(neonAccount))

        s = statuses(door_access.diagnose(account.account_id))
        reportSaysOk = all(s[name] != FAIL for name in NEON_CHECKS)

        assert reportSaysOk == syncGrantsAccess, (accountType, paid, waiver, toured, suspended, s)


def test_check_member_asks_when_several_match(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", json={"searchResults": [
        {"Account ID": "1", "First Name": "Jane", "Last Name": "Doe", "Email 1": "a@x.com"},
        {"Account ID": "2", "First Name": "Jane", "Last Name": "Doer", "Email 1": "b@x.com"},
    ]})

    report = door_access.checkMember("Jane Doe")

    assert "Found 2" in report
    assert "Neon #1" in report and "Neon #2" in report
    sent = requests_mock.last_request.json()["searchFields"]
    assert {"field": "First Name", "operator": "CONTAIN", "value": "Jane"} in sent


def test_check_member_by_email_runs_full_check(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SUBSCRIBERS, "name": "Subscribers"}], creds=MOBILE)
    search = requests_mock.post(f"{N_baseURL}/accounts/search",
                                json={"searchResults": [account.search_result()]})

    report = door_access.checkMember(account.email)

    assert search.last_request.json()["searchFields"][0]["field"] == "Email"
    assert "Verdict: Everything checks out" in report


def test_check_member_none_found(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", json={"searchResults": []})

    assert "No Neon account found" in door_access.checkMember("nobody@example.com")


def test_bad_api_key_explained(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", status_code=401, text="Unauthorized")
    door_access.neonUtil._neon_search.retry.sleep = lambda _: None

    assert "API key" in door_access.checkMember("someone@example.com")
