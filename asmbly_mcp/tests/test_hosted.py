import sys
from types import SimpleNamespace

import pytest

# The repo-wide test run doesn't install this folder's dependencies; skip there.
pytest.importorskip("fastmcp")

from fastmcp import Client
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from key_value.aio.stores.memory import MemoryStore
from starlette.testclient import TestClient

from asmbly_mcp import auth, aws_keys, hosted, tools

PUBLIC_URL = "https://mcp.example.test"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def claims(email="jane@asmbly.org", verified=True, hd="asmbly.org"):
    userData = {"hd": hd} if hd else {}
    return {"email": email, "email_verified": verified, "google_user_data": userData}


##### the asmbly.org rule #####

@pytest.mark.parametrize("who, allowed", [
    (claims(), True),
    (claims(email="Jane@ASMBLY.org"), True),
    (claims(verified="true"), True),                         # tokeninfo reports it as text
    (claims(hd=None), True),                                 # Google didn't report a workspace
    (claims(email="jane@gmail.com", hd=None), False),
    (claims(verified=False), False),
    (claims(verified="false"), False),
    (claims(hd="other.org"), False),                         # asmbly.org address on another workspace
    (claims(email="jane@evil-asmbly.org", hd=None), False),
    (claims(email="jane@asmbly.org.evil.com", hd=None), False),
    (claims(email="asmbly.org@evil.com", hd=None), False),
    (claims(email="", hd=None), False),
    ({}, False),
])
def test_only_verified_accounts_in_the_domain_are_allowed(who, allowed):
    assert auth.emailAllowed(who, "asmbly.org") is allowed


def googleSays(monkeypatch, tokenClaims):
    async def fakeVerify(self, token):
        if tokenClaims is None:
            return None
        return AccessToken(token=token, client_id="123", scopes=["openid"], claims=tokenClaims)
    monkeypatch.setattr(GoogleTokenVerifier, "verify_token", fakeVerify)


async def test_verifier_accepts_domain_account(monkeypatch):
    googleSays(monkeypatch, claims())
    verifier = auth.DomainRestrictedGoogleVerifier(allowedDomain="asmbly.org")

    assert (await verifier.verify_token("token")).claims["email"] == "jane@asmbly.org"


async def test_verifier_refuses_outside_account(monkeypatch):
    googleSays(monkeypatch, claims(email="jane@gmail.com", hd=None))
    verifier = auth.DomainRestrictedGoogleVerifier(allowedDomain="asmbly.org")

    assert await verifier.verify_token("token") is None


async def test_verifier_refuses_token_google_rejected(monkeypatch):
    googleSays(monkeypatch, None)
    verifier = auth.DomainRestrictedGoogleVerifier(allowedDomain="asmbly.org")

    assert await verifier.verify_token("token") is None


##### the hosted app #####

@pytest.fixture
def web():
    app = hosted.buildApp(
        googleClientId="fake-id.apps.googleusercontent.com",
        googleClientSecret="fake-google-client-secret",
        publicUrl=PUBLIC_URL,
        allowedDomain="asmbly.org",
        storage=MemoryStore(),
    )
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


def test_sign_in_details_are_published_the_way_claude_expects(web):
    resource = web.get("/.well-known/oauth-protected-resource/mcp").json()
    assert resource["resource"] == f"{PUBLIC_URL}/mcp"
    assert [s.rstrip("/") for s in resource["authorization_servers"]] == [PUBLIC_URL]

    server = web.get("/.well-known/oauth-authorization-server").json()
    assert server["issuer"].rstrip("/") == PUBLIC_URL
    assert "S256" in server["code_challenge_methods_supported"]
    assert server["registration_endpoint"].startswith(PUBLIC_URL)
    assert server["authorization_endpoint"].startswith(PUBLIC_URL)
    assert server["token_endpoint"].startswith(PUBLIC_URL)


def register(web, redirectUri):
    return web.post("/register", json={
        "client_name": "Claude",
        "redirect_uris": [redirectUri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })


def test_claude_can_register_and_start_sign_in(web):
    registration = register(web, CLAUDE_CALLBACK)
    assert registration.status_code == 201

    response = web.get("/authorize", params={
        "response_type": "code",
        "client_id": registration.json()["client_id"],
        "redirect_uri": CLAUDE_CALLBACK,
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
        "state": "abc",
        "resource": f"{PUBLIC_URL}/mcp",
    })

    # sent on to this server's own consent page, never straight back to the caller
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith(PUBLIC_URL)


def test_only_claude_can_be_registered_as_the_place_to_send_people_back_to(web):
    registration = register(web, "https://evil.example/callback")

    assert registration.status_code == 400
    assert registration.json()["error"] == "invalid_redirect_uri"


def test_claude_code_on_a_laptop_can_register(web):
    assert register(web, "http://localhost:5555/callback").status_code == 201


def test_google_is_told_to_offer_only_domain_accounts():
    provider = auth.buildGoogleAuth(
        clientId="fake-id", clientSecret="fake-google-client-secret", publicUrl=PUBLIC_URL,
        allowedDomain="asmbly.org", storage=MemoryStore())

    assert provider._extra_authorize_params["hd"] == "asmbly.org"


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
    "NEON_API_USER_PARAM": "/neon/api_user",
    "NEON_API_KEY_PARAM": "/neon/api_key",
    "ALTA_API_USER_PARAM": "/altaopen/api_user",
    "ALTA_API_KEY_PARAM": "/altaopen/api_key",
    "GOOGLE_CLIENT_ID_PARAM": "/asmbly-mcp/google_client_id",
    "GOOGLE_CLIENT_SECRET_PARAM": "/asmbly-mcp/google_client_secret",
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

    assert keys["N_APIkey"] == "value of /neon/api_key"
    assert keys["O_APIuser"] == "value of /altaopen/api_user"
    assert keys["googleClientSecret"] == "value of /asmbly-mcp/google_client_secret"
    assert sorted(asked["names"]) == sorted(PARAM_ENV.values())
    assert asked["decrypt"] is True


def test_missing_key_is_named_in_the_error(monkeypatch):
    stored = {name: "x" for name in PARAM_ENV.values() if name != "/altaopen/api_key"}
    fakeParameterStore(monkeypatch, stored)

    with pytest.raises(RuntimeError, match="/altaopen/api_key"):
        aws_keys.load()


def test_shared_code_gets_only_neon_and_alta_keys(monkeypatch):
    monkeypatch.setitem(sys.modules, "aws_ssm", None)
    monkeypatch.setitem(sys.modules, "config", None)

    aws_keys.installForSharedCode({"N_APIkey": "nk", "N_APIuser": "nu", "O_APIkey": "ok", "O_APIuser": "ou",
                                   "googleClientId": "gid", "googleClientSecret": "gsecret"})

    for name in ("aws_ssm", "config"):
        standIn = sys.modules[name]
        assert (standIn.N_APIkey, standIn.N_APIuser, standIn.O_APIkey, standIn.O_APIuser) == ("nk", "nu", "ok", "ou")
        assert standIn.G_user is None and standIn.G_password is None
        assert not hasattr(standIn, "googleClientSecret")
