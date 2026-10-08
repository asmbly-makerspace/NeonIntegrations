###############################################################################
# Hosted server: meant to run on AWS Lambda so the whole org can use it from
# claude.ai.
#
# PARKED. It has no sign-in yet, so it refuses to start. It waits on the
# Asmbly Login Service (see DEPLOY.md). Use local.py in the meantime.
#
# What's already here and carries over:
#   - Reached over HTTPS at  <public url>/mcp
#   - API keys come from AWS Parameter Store (aws_keys.py), never from this repo
#   - The AWS resources are defined in infra/template.yaml
# The container starts it with:  uvicorn asmbly_mcp.hosted:createApp --factory
###############################################################################

import os

import boto3
from starlette.responses import PlainTextResponse

MCP_PATH = "/mcp"

PARKED = (
    "Hosted mode is parked: it has no sign-in yet, so it will not start. "
    "It waits on the Asmbly Login Service. See asmbly_mcp/DEPLOY.md. "
    "Use the local server (asmbly_mcp/local.py) in the meantime."
)


def lookUpPublicUrl() -> str:
    # Set this only if the server sits behind a custom domain
    configured = os.environ.get("ASMBLY_MCP_PUBLIC_URL")
    if configured:
        return configured.rstrip("/")

    # Otherwise ask Lambda for this function's own public URL. (It can't be passed in
    # as a setting: the URL doesn't exist until after the function is created.)
    functionName = os.environ["AWS_LAMBDA_FUNCTION_NAME"]
    url = boto3.client("lambda").get_function_url_config(FunctionName=functionName)["FunctionUrl"]
    return url.rstrip("/")


def buildApp(*, signIn):
    # This server reaches member data over a public address. Never build it without sign-in.
    if signIn is None:
        raise ValueError("Refusing to build the hosted server without sign-in.")

    from asmbly_mcp.tools import buildServer

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
    # and returns buildApp(signIn=...), using lookUpPublicUrl() and auth.buildStorage().
    raise RuntimeError(PARKED)
