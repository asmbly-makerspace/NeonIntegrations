import boto3

ssm_creds = boto3.client("ssm").get_parameters(
    Names=[
        "/altaopen/api_key",
        "/altaopen/api_user",
        "/discourse/api_key",
        "/discourse/api_user",
        "/gmail/user",
        "/gmail/password",
        "/neon/api_key",
        "/neon/api_user",
    ],
    WithDecryption=True,
)

N_APIkey = ssm_creds["Parameters"][6]["Value"]
N_APIuser = ssm_creds["Parameters"][7]["Value"]

G_user = ssm_creds["Parameters"][5]["Value"]
G_password = ssm_creds["Parameters"][4]["Value"]

O_APIkey = ssm_creds["Parameters"][0]["Value"]
O_APIuser = ssm_creds["Parameters"][1]["Value"]

D_APIkey = ssm_creds["Parameters"][2]["Value"]
D_APIuser = ssm_creds["Parameters"][3]["Value"]
