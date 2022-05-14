################# Asmbly OpenPath API Integrations ################
# OpenPath API docs - https://openpath.readme.io/docs             #
###################################################################

import requests
from pprint import pprint
from datetime import date
import json
import base64

from config import N_APIkey, N_APIuser
from util import apiCall

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}

dryRun = False

neonFilename = "Neon/memberAccounts.json"

neonAccounts = {}

# ##### NEON ######
#first off, check that we have a Neon account list before spending a bunch of time on the Discourse API
with open(neonFilename) as neonFile:
    neonAccountJson = json.load(neonFile)
    for account in neonAccountJson:
        neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

for account in neonAccounts:
    if (neonAccounts[account].get("validMembership") and not neonAccounts[account].get("AccessSuspended") and not neonAccounts[account].get("FacilityTourDate")):
        print(f'Populating FacilityTourDate for {neonAccounts[account].get("First Name")} {neonAccounts[account].get("Last Name")} ({neonAccounts[account].get("Account ID")})')
        if not dryRun:
            ##### NEON #####
            # Update part of an account
            # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
            httpVerb = 'PATCH'
            resourcePath = f'/accounts/{neonAccounts[account].get("Account ID")}'
            queryParams = '?category=Account'
            data = f'''
            {{
            "individualAccount": {{
                "accountCustomFields": [
                {{
                    "id": "182",
                    "name": "FacilityTourDate",
                    "value": "01/01/1970",
                    "status": "ACTIVE"
                }}
                ]
            }}
            }}
            '''
            url = N_baseURL + resourcePath + queryParams
            patch = apiCall(httpVerb, url, data, N_headers)
            pprint(patch)
