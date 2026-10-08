###############################################################################
# Loads API keys from AWS Parameter Store when the server is hosted on AWS.
#
# NO KEY VALUES LIVE IN THIS REPO. The server is told the *names* of the
# parameters through environment variables (set in infra/template.yaml), and
# reads the values at startup using the Lambda's own permissions.
###############################################################################

import os
import sys
from types import SimpleNamespace

import boto3

# environment variable holding the parameter name -> what the value is used for
KEY_PARAMS = {
    "NEON_API_USER_PARAM": "N_APIuser",
    "NEON_API_KEY_PARAM": "N_APIkey",
    "ALTA_API_USER_PARAM": "O_APIuser",
    "ALTA_API_KEY_PARAM": "O_APIkey",
    "GOOGLE_CLIENT_ID_PARAM": "googleClientId",
    "GOOGLE_CLIENT_SECRET_PARAM": "googleClientSecret",
}


def load() -> dict:
    unset = [env for env in KEY_PARAMS if not os.environ.get(env)]
    if unset:
        raise RuntimeError(f"Missing environment variables: {', '.join(unset)}")

    nameToKey = {os.environ[env]: key for env, key in KEY_PARAMS.items()}
    response = boto3.client("ssm").get_parameters(Names=list(nameToKey), WithDecryption=True)

    # match by name: the order Parameter Store returns them in isn't guaranteed
    keys = {nameToKey[p["Name"]]: p["Value"] for p in response["Parameters"]}
    missing = sorted(name for name, key in nameToKey.items() if key not in keys)
    if missing:
        raise RuntimeError(f"Not found in Parameter Store (or no permission to read): {', '.join(missing)}")
    return keys


def installForSharedCode(keys: dict):
    # neonUtil and openPathUtil read their keys from a module named aws_ssm (on AWS)
    # or config (elsewhere) the moment they're imported. The repo's aws_ssm.py loads
    # every key the door sync uses, including Gmail and Discourse, which this server
    # has no permission to read and no use for. So hand them a stand-in that holds
    # only the Neon and Alta Open keys. Must run before neonUtil is imported.
    standIn = SimpleNamespace(
        N_APIkey=keys["N_APIkey"],
        N_APIuser=keys["N_APIuser"],
        O_APIkey=keys["O_APIkey"],
        O_APIuser=keys["O_APIuser"],
        G_user=None,
        G_password=None,
        D_APIkey=None,
        D_APIuser=None,
    )
    sys.modules["aws_ssm"] = standIn
    sys.modules["config"] = standIn
