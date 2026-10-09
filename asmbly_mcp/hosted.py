###############################################################################
# Hosted server: meant to run on AWS Lambda so the whole org can use it from
# claude.ai.
#
# PARKED. It has no sign-in yet, so it refuses to start. It waits on the
# Asmbly Login Service (see DEPLOY.md). Use local.py in the meantime.
#
# What's already here and carries over:
#   - Reached over HTTPS at  https://mcp.asmbly.org/mcp
#   - API keys come from AWS Parameter Store (aws_keys.py), never from this repo
#   - The AWS resources are defined in infra/template.yaml
# The container starts it with:  uvicorn asmbly_mcp.hosted:createApp --factory
###############################################################################

import logging
import os

from starlette.responses import PlainTextResponse

MCP_PATH = "/mcp"

PARKED = (
    "Hosted mode is parked: it has no sign-in yet, so it will not start. "
    "It waits on the Asmbly Login Service. See asmbly_mcp/DEPLOY.md. "
    "Use the local server (asmbly_mcp/local.py) in the meantime."
)


def publicUrl() -> str:
    # The address people reach the server at (https://mcp.asmbly.org), set in infra/template.yaml.
    # Sign-in links are built from it.
    return os.environ["ASMBLY_MCP_PUBLIC_URL"].rstrip("/")


class WithholdSharedCodeMessages(logging.Filter):
    # The door sync's shared code (neonUtil, openPathUtil) writes member names and emails
    # into its log messages. That is meant for the sync's own logs, not this server's.
    # Keep the fact that something was logged and where, and drop what it said.
    def filter(self, record):
        record.msg = "message withheld, it may contain member details (%s line %s)"
        record.args = (record.filename, record.lineno)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def setUpLogging():
    # Lambda sends what the server prints to CloudWatch, log group /aws/lambda/asmbly-mcp,
    # which infra/template.yaml keeps for 90 days. No personal details may end up there
    # (the rule is spelled out at the top of tools.py).
    from asmbly_mcp.tools import AUDIT_LOGGER

    # The shared code logs straight to the root logger, and a filter on the root logger
    # applies only to those messages. Other loggers' messages pass through untouched.
    root = logging.getLogger()
    if not any(isinstance(f, WithholdSharedCodeMessages) for f in root.filters):
        root.addFilter(WithholdSharedCodeMessages())
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.set_name("asmbly_mcp")
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)

    # Audit lines get their own handler, so they are recorded whatever else is set.
    audit = logging.getLogger(AUDIT_LOGGER)
    audit.setLevel(logging.INFO)
    if not audit.handlers:
        handler = logging.StreamHandler()
        handler.set_name("asmbly_mcp")
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit.addHandler(handler)


def buildApp(*, signIn):
    # This server reaches member data over a public address. Never build it without sign-in.
    if signIn is None:
        raise ValueError("Refusing to build the hosted server without sign-in.")

    from asmbly_mcp.tools import buildServer

    setUpLogging()
    mcp = buildServer(auth=signIn)

    # No sign-in needed. The Lambda Web Adapter polls this to know the server is up.
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):
        return PlainTextResponse("ok")

    # Lambda can freeze or replace the server between requests, so keep nothing in memory:
    # every request stands alone and gets a plain JSON answer.
    return mcp.http_app(path=MCP_PATH, stateless_http=True, json_response=True)


def createApp():
    # Once sign-in exists, this loads the keys (aws_keys.load, aws_keys.installForSharedCode)
    # and returns buildApp(signIn=...), using publicUrl() and auth.buildStorage().
    raise RuntimeError(PARKED)
