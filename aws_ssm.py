import boto3


def _get_parameters(names: list[str]) -> dict[str, str]:
    """Fetch decrypted SSM parameters as {name: value}. Raises if any are missing."""
    # GetParameters accepts at most 10 names
    response = boto3.client("ssm").get_parameters(Names=names, WithDecryption=True)
    values = {p["Name"]: p["Value"] for p in response["Parameters"]}
    missing = [name for name in names if name not in values]
    if missing:
        raise RuntimeError("SSM parameter(s) not found: " + ", ".join(missing))
    return values


ssm_creds = _get_parameters(
    [
        "/altaopen/api_key",
        "/altaopen/api_user",
        "/discourse/api_key",
        "/discourse/api_user",
        "/gmail/user",
        "/gmail/password",
        "/neon/api_key",
        "/neon/api_user",
    ]
)

N_APIkey = ssm_creds["/neon/api_key"]
N_APIuser = ssm_creds["/neon/api_user"]

G_user = ssm_creds["/gmail/user"]
G_password = ssm_creds["/gmail/password"]

O_APIkey = ssm_creds["/altaopen/api_key"]
O_APIuser = ssm_creds["/altaopen/api_user"]

D_APIkey = ssm_creds["/discourse/api_key"]
D_APIuser = ssm_creds["/discourse/api_user"]
