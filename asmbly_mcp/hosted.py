###############################################################################
# Hosted server: runs on AWS Lambda so the whole org can use it from claude.ai.
#
#   - Reached over HTTPS at  <public url>/mcp
#   - People sign in with Google; only the allowed domain gets in (auth.py)
#   - API keys come from AWS Parameter Store (aws_keys.py), never from this repo
#
# The AWS resources are defined in infra/template.yaml. See DEPLOY.md.
# The container starts it with:  uvicorn asmbly_mcp.hosted:createApp --factory
###############################################################################

import logging
import os

import boto3
from starlette.responses import PlainTextResponse

from asmbly_mcp import auth, aws_keys

MCP_PATH = "/mcp"


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


def buildApp(*, googleClientId: str, googleClientSecret: str, publicUrl: str, allowedDomain: str, storage):
    from asmbly_mcp.tools import buildServer

    mcp = buildServer(auth=auth.buildGoogleAuth(
        clientId=googleClientId,
        clientSecret=googleClientSecret,
        publicUrl=publicUrl,
        allowedDomain=allowedDomain,
        storage=storage,
    ))

    # No sign-in needed. The Lambda Web Adapter polls this to know the server is up.
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request):
        return PlainTextResponse("ok")

    # Lambda can freeze or replace the server between requests, so keep nothing in memory:
    # every request stands alone and gets a plain JSON answer.
    return mcp.http_app(path=MCP_PATH, stateless_http=True, json_response=True)


def createApp():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # basicConfig does nothing if the host already set up logging, so set the level too
    logging.getLogger().setLevel(logging.INFO)

    keys = aws_keys.load()
    aws_keys.installForSharedCode(keys)

    return buildApp(
        googleClientId=keys["googleClientId"],
        googleClientSecret=keys["googleClientSecret"],
        publicUrl=lookUpPublicUrl(),
        allowedDomain=os.environ["ALLOWED_EMAIL_DOMAIN"],
        storage=auth.buildStorage(os.environ["SIGN_IN_STATE_TABLE"], keys["googleClientSecret"]),
    )
