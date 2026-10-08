import doorAccessCheck
from doorAccessCheck import PASS, FAIL, WARN, SKIP
from neon_mocker import NeonUserMock, today_plus
from neonUtil import MEMBERSHIP_ID_REGULAR, N_baseURL, STAFF_TYPE
from openPathUtil import GROUP_SUBSCRIBERS, GROUP_SPECIAL_EVENT, O_baseURL


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

    result = doorAccessCheck.diagnose(account.account_id)

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

    result = doorAccessCheck.diagnose(account.account_id)
    s = statuses(result)

    assert s["Access not suspended"] == FAIL
    assert s["Alta Open groups correct"] == WARN
    assert result["verdict"].startswith("Problem found: Access not suspended")
    assert "may keep working" in result["verdict"]


def test_missing_waiver_and_tour_without_alta_account(requests_mock):
    account = NeonUserMock().add_membership(MEMBERSHIP_ID_REGULAR, start, end, fee=100.0)
    account.mock(requests_mock)

    result = doorAccessCheck.diagnose(account.account_id)
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

    result = doorAccessCheck.diagnose(account.account_id)
    membership = result["checks"][0]

    assert membership["status"] == FAIL
    assert "FAILED" in membership["detail"]


def test_valid_member_missing_group_and_credential(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[{"id": GROUP_SPECIAL_EVENT, "name": "Special Event"}])

    result = doorAccessCheck.diagnose(account.account_id)
    s = statuses(result)

    assert s["Alta Open groups correct"] == FAIL
    assert s["Has a door credential"] == FAIL
    assert "openPathUpdateSingle.py" in doorAccessCheck.formatReport(result)


def test_valid_member_without_alta_account(requests_mock):
    account = good_member(open_path_id=None)
    account.mock(requests_mock)

    result = doorAccessCheck.diagnose(account.account_id)

    assert statuses(result)["Alta Open account exists"] == FAIL


def test_inactive_alta_user(requests_mock):
    account = good_member()
    account.mock(requests_mock)
    mock_alta(requests_mock, status="I", groups=[{"id": GROUP_SUBSCRIBERS}], creds=MOBILE)

    result = doorAccessCheck.diagnose(account.account_id)

    assert statuses(result)["Alta Open account active"] == FAIL


def test_staff_override_noted(requests_mock):
    account = NeonUserMock(open_path_id=ALTA_ID, individualTypes=[STAFF_TYPE])
    account.mock(requests_mock)
    mock_alta(requests_mock, groups=[], creds=MOBILE)

    result = doorAccessCheck.diagnose(account.account_id)

    assert statuses(result)["Account type override"] == PASS
    assert result["shouldHaveFacilityAccess"]


def test_check_member_asks_when_several_match(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", json={"searchResults": [
        {"Account ID": "1", "First Name": "Jane", "Last Name": "Doe", "Email 1": "a@x.com"},
        {"Account ID": "2", "First Name": "Jane", "Last Name": "Doer", "Email 1": "b@x.com"},
    ]})

    report = doorAccessCheck.checkMember("Jane Doe")

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

    report = doorAccessCheck.checkMember(account.email)

    assert search.last_request.json()["searchFields"][0]["field"] == "Email"
    assert "Verdict: Everything checks out" in report


def test_check_member_none_found(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", json={"searchResults": []})

    assert "No Neon account found" in doorAccessCheck.checkMember("nobody@example.com")


def test_bad_api_key_explained(requests_mock):
    requests_mock.post(f"{N_baseURL}/accounts/search", status_code=401, text="Unauthorized")
    doorAccessCheck.neonUtil._neon_search.retry.sleep = lambda _: None

    assert "API key" in doorAccessCheck.checkMember("someone@example.com")
