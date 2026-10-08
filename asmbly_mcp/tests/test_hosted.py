import sys
from types import SimpleNamespace

import pytest

# The repo-wide test run doesn't install this folder's dependencies; skip there.
pytest.importorskip("fastmcp")

from fastmcp import Client
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from key_value.aio.stores.memory import MemoryStore
from starlette.testclient import TestClient

from asmbly_mcp import auth, aws_keys, hosted, tools

PUBLIC_URL = "https://mcp.example.test"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


##### hosted mode is parked until sign-in is built #####

def test_parked_server_refuses_to_start():
    with pytest.raises(RuntimeError, match="parked"):
        hosted.createApp()


def test_hosted_server_cannot_be_built_without_sign_in():
    with pytest.raises(ValueError, match="without sign-in"):
        hosted.buildApp(signIn=None)


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
    monkeypatch.setattr(door_access, "checkMember", lambda member: f"checked {member}")

    async with Client(tools.buildServer()) as client:
        names = {tool.name for tool in await client.list_tools()}
        result = await client.call_tool("check_door_access", {"member": "jane@example.com"})

    assert names == {"check_door_access", "find_member"}
    assert result.content[0].text == "checked jane@example.com"


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
