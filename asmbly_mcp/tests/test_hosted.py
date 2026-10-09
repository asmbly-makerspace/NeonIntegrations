import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# The repo-wide test run doesn't install this folder's dependencies; skip there.
pytest.importorskip("fastmcp")

from fastmcp import Client
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from key_value.aio.stores.memory import MemoryStore
from starlette.testclient import TestClient

from neon_mocker import NeonUserMock, today_plus
from neonUtil import COWORKING_TYPE, N_baseURL

from asmbly_mcp import auth, aws_keys, hosted, tools

PUBLIC_URL = "https://mcp.example.test"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture(autouse=True)
def _undoHostedLogging():
    # hosted.setUpLogging() changes logging for the whole process; put it back after each test
    yield
    root = logging.getLogger()
    audit = logging.getLogger(tools.AUDIT_LOGGER)
    for f in [f for f in root.filters if isinstance(f, hosted.WithholdSharedCodeMessages)]:
        root.removeFilter(f)
    for logger in (root, audit):
        for handler in [h for h in logger.handlers if h.get_name() == "asmbly_mcp"]:
            logger.removeHandler(handler)
    audit.setLevel(logging.NOTSET)


##### hosted mode is parked until sign-in is built #####

def test_parked_server_refuses_to_start():
    with pytest.raises(RuntimeError, match="parked"):
        hosted.createApp()


def test_hosted_server_cannot_be_built_without_sign_in():
    with pytest.raises(ValueError, match="without sign-in"):
        hosted.buildApp(signIn=None)


##### who is allowed: Paid Staff only #####

def account(*typeNames):
    return {"individualTypes": [{"name": name} for name in typeNames]}


@pytest.mark.parametrize("neonAccount, allowed", [
    (account("Paid Staff"), True),
    (account("Instructor", "Paid Staff"), True),
    (account("Leader"), False),
    (account("Instructor", "Steward", "Volunteer"), False),
    (account("paid staff"), False),                  # names must match Neon exactly
    (account(), False),
    ({}, False),                                     # a member with no account type at all
])
def test_only_paid_staff_may_use_the_server(neonAccount, allowed):
    assert auth.mayUseServer(neonAccount, ["Paid Staff"]) is allowed


def test_an_empty_list_lets_nobody_in():
    assert auth.mayUseServer(account("Paid Staff"), []) is False


@pytest.mark.parametrize("setting, expected", [
    ("Paid Staff", ["Paid Staff"]),
    ("Paid Staff, Leader", ["Paid Staff", "Leader"]),
    (" Paid Staff ,, ", ["Paid Staff"]),
    ("", []),
])
def test_allowed_types_come_from_the_setting(monkeypatch, setting, expected):
    monkeypatch.setenv("ALLOWED_NEON_ACCOUNT_TYPES", setting)

    assert auth.allowedAccountTypes() == expected


def test_no_setting_means_nobody(monkeypatch):
    monkeypatch.delenv("ALLOWED_NEON_ACCOUNT_TYPES", raising=False)

    assert auth.allowedAccountTypes() == []


def test_the_template_default_is_paid_staff_only():
    template = (Path(__file__).resolve().parents[1] / "infra" / "template.yaml").read_text()
    setting = template.split("AllowedNeonAccountTypes:")[1].split("Description:")[0]

    assert "Default: Paid Staff\n" in setting


##### the parts that carry over, exercised with a stand-in sign-in #####

class NobodyVerifier(TokenVerifier):
    async def verify_token(self, token):
        return None


def standInSignIn():
    # Not a real login. It lets the tests check how the server treats requests
    # and which sites it lets sign-in send people back to.
    return OAuthProxy(
        upstream_authorization_endpoint="https://login.example.test/authorize",
        upstream_token_endpoint="https://login.example.test/token",
        upstream_client_id="stand-in-client",
        upstream_client_secret="stand-in-client-secret",
        token_verifier=NobodyVerifier(required_scopes=["openid"]),
        base_url=PUBLIC_URL,
        allowed_client_redirect_uris=auth.ALLOWED_CLIENT_REDIRECTS,
        client_storage=MemoryStore(),
    )


@pytest.fixture
def web():
    app = hosted.buildApp(signIn=standInSignIn())
    with TestClient(app, base_url=PUBLIC_URL, follow_redirects=False) as client:
        yield client


def test_health_needs_no_sign_in(web):
    assert web.get("/health").status_code == 200


def test_mcp_refuses_requests_without_sign_in(web):
    response = web.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response.status_code == 401
    # tells Claude where to find the sign-in details
    assert "resource_metadata" in response.headers["www-authenticate"]


def test_mcp_refuses_made_up_token(web):
    response = web.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                        headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def register(web, redirectUri):
    return web.post("/register", json={
        "client_name": "Claude",
        "redirect_uris": [redirectUri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })


def test_claude_can_register(web):
    assert register(web, CLAUDE_CALLBACK).status_code == 201


def test_claude_code_on_a_laptop_can_register(web):
    assert register(web, "http://localhost:5555/callback").status_code == 201


def test_only_claude_can_be_registered_as_the_place_to_send_people_back_to(web):
    registration = register(web, "https://evil.example/callback")

    assert registration.status_code == 400
    assert registration.json()["error"] == "invalid_redirect_uri"


##### the tools #####

async def test_server_offers_the_door_access_tools(monkeypatch):
    from asmbly_mcp import door_access
    monkeypatch.setattr(door_access, "lookUp", lambda member: (f"checked {member}", ["1234"]))

    async with Client(tools.buildServer()) as client:
        names = {tool.name for tool in await client.list_tools()}
        result = await client.call_tool("check_door_access", {"member": "jane@example.com"})

    assert names == {"check_door_access", "find_member"}
    assert result.content[0].text == "checked jane@example.com"


##### the audit trail #####

async def test_a_door_check_is_audited_by_account_number_only(monkeypatch, caplog):
    from asmbly_mcp import door_access
    monkeypatch.setattr(door_access, "lookUp", lambda member: ("the report for Jane Doe", ["1234"]))

    with caplog.at_level(logging.INFO, logger=tools.AUDIT_LOGGER):
        async with Client(tools.buildServer()) as client:
            await client.call_tool("check_door_access", {"member": "jane@example.com"})

    lines = [r.getMessage() for r in caplog.records if r.name == tools.AUDIT_LOGGER]
    assert lines == ["AUDIT tool=check_door_access by=local neon_accounts=1234"]
    # what was typed, and anything from the report, stays out of the log
    assert "jane" not in lines[0].lower()


async def test_a_search_is_audited_with_every_account_it_showed(monkeypatch, caplog):
    from asmbly_mcp import door_access
    monkeypatch.setattr(door_access, "findMembers", lambda query: [
        {"Account ID": "11", "First Name": "Jane", "Last Name": "Doe", "Email 1": "a@x.com"},
        {"Account ID": "22", "First Name": "Jane", "Last Name": "Doer", "Email 1": "b@x.com"},
    ])

    with caplog.at_level(logging.INFO, logger=tools.AUDIT_LOGGER):
        async with Client(tools.buildServer()) as client:
            await client.call_tool("find_member", {"query": "Jane"})

    lines = [r.getMessage() for r in caplog.records if r.name == tools.AUDIT_LOGGER]
    assert lines == ["AUDIT tool=find_member by=local neon_accounts=11,22"]


async def test_a_lookup_that_finds_nobody_is_still_audited(monkeypatch, caplog):
    from asmbly_mcp import door_access
    monkeypatch.setattr(door_access, "findMembers", lambda query: [])

    with caplog.at_level(logging.INFO, logger=tools.AUDIT_LOGGER):
        async with Client(tools.buildServer()) as client:
            await client.call_tool("find_member", {"query": "nobody"})

    lines = [r.getMessage() for r in caplog.records if r.name == tools.AUDIT_LOGGER]
    assert lines == ["AUDIT tool=find_member by=local neon_accounts=none"]


def test_the_hosted_server_turns_the_audit_log_on():
    hosted.buildApp(signIn=standInSignIn())

    audit = logging.getLogger(tools.AUDIT_LOGGER)
    assert audit.isEnabledFor(logging.INFO)
    assert audit.handlers


##### no personal details in the logs #####

async def test_the_person_looking_is_recorded_by_id_never_name_or_email(monkeypatch, caplog):
    from asmbly_mcp import door_access
    monkeypatch.setattr(door_access, "lookUp", lambda member: ("report", ["1234"]))
    monkeypatch.setattr(tools, "get_access_token", lambda: SimpleNamespace(
        claims={"sub": "abc-123", "email": "sam.staffer@asmbly.org", "name": "Sam Staffer"}))

    with caplog.at_level(logging.INFO, logger=tools.AUDIT_LOGGER):
        async with Client(tools.buildServer()) as client:
            await client.call_tool("check_door_access", {"member": "1234"})

    assert "AUDIT tool=check_door_access by=abc-123 neon_accounts=1234" in caplog.text
    assert "sam" not in caplog.text.lower() and "staffer" not in caplog.text.lower()


async def test_errors_are_logged_by_kind_not_by_message(monkeypatch, caplog):
    from asmbly_mcp import door_access

    def neonQuotesTheSearchBack(member):
        raise ValueError("Post https://api.neoncrm.com/v2/accounts/search returned status code 400: "
                         "no match for jane.doe@example.com")
    monkeypatch.setattr(door_access, "lookUp", neonQuotesTheSearchBack)

    with caplog.at_level(logging.DEBUG):
        async with Client(tools.buildServer()) as client:
            result = await client.call_tool("check_door_access", {"member": "jane.doe@example.com"})

    assert "check_door_access failed: ValueError (status 400)" in caplog.text
    assert "jane" not in caplog.text.lower()
    # the person asking still gets the full explanation
    assert "jane.doe@example.com" in result.content[0].text


def test_shared_code_messages_are_withheld(caplog):
    hosted.setUpLogging()

    with caplog.at_level(logging.DEBUG):
        # the door sync's code logs like this, straight to the root logger
        logging.warning("Cowrking subscriber %s has access despite a lapsed membership.", "Jane Doe")
        logging.debug("{'firstName': 'Jane', 'email1': 'jane.doe@example.com'}")
        # other libraries use their own named loggers; those are left alone
        logging.getLogger("some.library").warning("connection %s", "reset")

    assert "jane" not in caplog.text.lower()
    assert caplog.text.count("message withheld") == 2
    assert "connection reset" in caplog.text


def test_setting_up_hosted_logging_twice_changes_nothing():
    hosted.setUpLogging()
    hosted.setUpLogging()

    root = logging.getLogger()
    assert len([f for f in root.filters if isinstance(f, hosted.WithholdSharedCodeMessages)]) == 1
    assert len(logging.getLogger(tools.AUDIT_LOGGER).handlers) == 1


async def test_a_real_door_check_leaves_no_member_details_in_the_logs(requests_mock, caplog):
    # A CoWorking tenant with a lapsed membership makes the shared code log the member's
    # full name. Run a whole check through the tool and look at everything that was logged.
    member = NeonUserMock(firstName="Zelda", lastName="Quixote", email="zelda.quixote@example.com",
                          waiver_date=today_plus(-30), facility_tour_date=today_plus(-29),
                          individualTypes=[COWORKING_TYPE])
    member.mock(requests_mock)
    requests_mock.post(f"{N_baseURL}/accounts/search", json={"searchResults": [member.search_result()]})
    hosted.setUpLogging()

    with caplog.at_level(logging.DEBUG):
        async with Client(tools.buildServer()) as client:
            result = await client.call_tool("check_door_access", {"member": "zelda.quixote@example.com"})

    # the person asking sees the member's details; that's the point of the tool
    assert "Zelda Quixote" in result.content[0].text

    logged = caplog.text.lower()
    assert "zelda" not in logged and "quixote" not in logged
    assert f"AUDIT tool=check_door_access by=local neon_accounts={member.account_id}" in caplog.text
    assert "message withheld" in caplog.text      # the shared code did try to log something


def test_logs_are_kept_for_90_days():
    template = (Path(__file__).resolve().parents[1] / "infra" / "template.yaml").read_text()

    assert "RetentionInDays: 90\n" in template


##### loading keys on AWS #####

PARAM_ENV = {
    "NEON_API_USER_PARAM": "/asmbly-mcp/neon_api_user",
    "NEON_API_KEY_PARAM": "/asmbly-mcp/neon_api_key",
    "ALTA_API_USER_PARAM": "/asmbly-mcp/altaopen_api_user",
    "ALTA_API_KEY_PARAM": "/asmbly-mcp/altaopen_api_key",
}


def fakeParameterStore(monkeypatch, stored):
    asked = {}

    def get_parameters(Names, WithDecryption):
        asked["names"], asked["decrypt"] = Names, WithDecryption
        # returned in a different order than asked, like the real thing can
        return {"Parameters": [{"Name": n, "Value": stored[n]} for n in reversed(Names) if n in stored]}

    monkeypatch.setattr(aws_keys.boto3, "client", lambda service: SimpleNamespace(get_parameters=get_parameters))
    for env, name in PARAM_ENV.items():
        monkeypatch.setenv(env, name)
    return asked


def test_keys_are_loaded_by_name(monkeypatch):
    asked = fakeParameterStore(monkeypatch, {name: f"value of {name}" for name in PARAM_ENV.values()})

    keys = aws_keys.load()

    assert keys == {
        "N_APIuser": "value of /asmbly-mcp/neon_api_user",
        "N_APIkey": "value of /asmbly-mcp/neon_api_key",
        "O_APIuser": "value of /asmbly-mcp/altaopen_api_user",
        "O_APIkey": "value of /asmbly-mcp/altaopen_api_key",
    }
    assert sorted(asked["names"]) == sorted(PARAM_ENV.values())
    assert asked["decrypt"] is True


def test_missing_key_is_named_in_the_error(monkeypatch):
    stored = {name: "x" for name in PARAM_ENV.values() if name != "/asmbly-mcp/altaopen_api_key"}
    fakeParameterStore(monkeypatch, stored)

    with pytest.raises(RuntimeError, match="/asmbly-mcp/altaopen_api_key"):
        aws_keys.load()


def test_shared_code_gets_only_neon_and_alta_keys(monkeypatch):
    monkeypatch.setitem(sys.modules, "aws_ssm", None)
    monkeypatch.setitem(sys.modules, "config", None)

    aws_keys.installForSharedCode({"N_APIkey": "nk", "N_APIuser": "nu", "O_APIkey": "ok", "O_APIuser": "ou"})

    for name in ("aws_ssm", "config"):
        standIn = sys.modules[name]
        assert (standIn.N_APIkey, standIn.N_APIuser, standIn.O_APIkey, standIn.O_APIuser) == ("nk", "nu", "ok", "ou")
        assert standIn.G_user is None and standIn.G_password is None
