###############################################################################
# Sign-in for the hosted server.
#
# NOT BUILT YET. Hosted mode is parked until the Asmbly Login Service is live
# (see DEPLOY.md). The plan: people sign in with their Neon account through
# that service, and this server then checks that their Neon account type is
# one that's allowed to use it.
#
# What's here is the part that carries over once sign-in is added.
###############################################################################

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
