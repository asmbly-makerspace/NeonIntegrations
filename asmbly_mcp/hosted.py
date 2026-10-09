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


def turnOnAuditLog():
    # Lambda sends what the server prints to CloudWatch, log group /aws/lambda/asmbly-mcp,
    # which infra/template.yaml keeps for 90 days. Give the audit lines their own handler
    # so they are recorded whatever the rest of the logging is set to.
    from asmbly_mcp.tools import AUDIT_LOGGER

    audit = logging.getLogger(AUDIT_LOGGER)
    audit.setLevel(logging.INFO)
    if not audit.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit.addHandler(handler)


def buildApp(*, signIn):
    # This server reaches member data over a public address. Never build it without sign-in.
    if signIn is None:
        raise ValueError("Refusing to build the hosted server without sign-in.")

    from asmbly_mcp.tools import buildServer

    turnOnAuditLog()
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
