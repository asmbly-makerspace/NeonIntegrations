###############################################################################
# Sign-in for the hosted server.
#
# NOT BUILT YET. Hosted mode is parked until the Asmbly Login Service is live
# (see DEPLOY.md). The plan: people sign in with their Neon account through
# that service, and this server then checks that their Neon account type is
# one that's allowed to use it.
#
# What's here: the rule for who is allowed, and the parts that carry over
# once sign-in is added.
###############################################################################

import os

from key_value.aio.stores.dynamodb import DynamoDBStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper

# Where Claude is allowed to send people back to after sign-in.
# claude.ai / claude.com are the hosted apps; localhost is Claude Code on someone's computer.
ALLOWED_CLIENT_REDIRECTS = [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "http://localhost:*",
    "http://127.0.0.1:*",
]


def allowedAccountTypes() -> list:
    # The Neon account types ("Individual Type" in Neon) that may use the hosted server.
    # Set in infra/template.yaml, comma separated. Decided: Paid Staff only.
    setting = os.environ.get("ALLOWED_NEON_ACCOUNT_TYPES", "")
    return [name.strip() for name in setting.split(",") if name.strip()]


def mayUseServer(neonAccount: dict, allowedTypes: list) -> bool:
    # neonAccount is the signed-in person's own Neon member account, as neonUtil returns it.
    # An empty list lets nobody in.
    import neonUtil  # here, not at the top: neonUtil reads the API keys when it's imported

    return any(neonUtil.accountIsType(neonAccount, name) for name in allowedTypes)


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
