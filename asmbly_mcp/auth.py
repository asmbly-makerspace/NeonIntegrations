###############################################################################
# Sign-in for the hosted server: "Sign in with Google", one domain only.
#
# Claude sends people through Google's login. This server then checks, on every
# request, that the Google account has a verified email in the allowed domain
# (asmbly.org). Anyone else is refused.
#
# The OAuth plumbing itself is fastmcp's maintained OAuthProxy. The only logic
# written here is the domain rule.
###############################################################################

import logging

from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from key_value.aio.stores.dynamodb import DynamoDBStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"

# Where Claude is allowed to send people back to after sign-in.
# claude.ai / claude.com are the hosted apps; localhost is Claude Code on someone's computer.
ALLOWED_CLIENT_REDIRECTS = [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "http://localhost:*",
    "http://127.0.0.1:*",
]


def emailAllowed(claims: dict, allowedDomain: str) -> bool:
    allowedDomain = allowedDomain.lower()
    email = (claims.get("email") or "").lower()
    # Google's two endpoints report this as "true" (text) or True
    verified = claims.get("email_verified") in (True, "true")
    _, _, emailDomain = email.rpartition("@")
    if not verified or emailDomain != allowedDomain:
        return False

    # hd is the Google Workspace the account belongs to. When Google reports it, it must match too.
    hostedDomain = (claims.get("google_user_data") or {}).get("hd")
    if hostedDomain is not None and hostedDomain.lower() != allowedDomain:
        return False
    return True


class DomainRestrictedGoogleVerifier(GoogleTokenVerifier):
    """Accepts a Google sign-in only if it's a verified account in the allowed domain."""

    def __init__(self, *, allowedDomain: str, **kwargs):
        super().__init__(**kwargs)
        self.allowedDomain = allowedDomain

    async def verify_token(self, token: str):
        accessToken = await super().verify_token(token)
        if accessToken is None:
            return None
        if not emailAllowed(accessToken.claims, self.allowedDomain):
            logging.warning(
                "Refused sign-in from %s: not a verified %s account",
                accessToken.claims.get("email") or "unknown email", self.allowedDomain)
            return None
        return accessToken


def buildStorage(tableName: str, encryptionSecret: str):
    # Sign-in state (registered Claude clients, tokens) has to outlive a single Lambda run.
    # The table itself is created by infra/template.yaml. Values are encrypted before they're stored.
    table = DynamoDBStore(table_name=tableName, auto_create=False)
    return FernetEncryptionWrapper(
        key_value=table,
        source_material=encryptionSecret,
        salt="asmbly-mcp-sign-in-state",
        # after a key change, old entries just read as missing and people sign in again
        raise_on_decryption_error=False,
    )


def buildGoogleAuth(*, clientId: str, clientSecret: str, publicUrl: str, allowedDomain: str, storage):
    return OAuthProxy(
        upstream_authorization_endpoint=GOOGLE_AUTHORIZE_URL,
        upstream_token_endpoint=GOOGLE_TOKEN_URL,
        upstream_client_id=clientId,
        upstream_client_secret=clientSecret,
        token_verifier=DomainRestrictedGoogleVerifier(
            allowedDomain=allowedDomain,
            required_scopes=["openid", EMAIL_SCOPE],
            # only accept Google tokens that were issued to our own Google client
            audience=clientId,
        ),
        base_url=publicUrl,
        allowed_client_redirect_uris=ALLOWED_CLIENT_REDIRECTS,
        client_storage=storage,
        extra_authorize_params={
            # needed for Google to hand back a refresh token, so people stay signed in
            "access_type": "offline",
            "prompt": "consent",
            # Google's account picker only offers accounts from this domain.
            # This is a convenience; the real check is DomainRestrictedGoogleVerifier.
            "hd": allowedDomain,
        },
    )
