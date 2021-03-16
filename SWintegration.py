################# ATXHS Smartwaiver API Integrations #################
# Smartwaiver API docs - https://api.smartwaiver.com/docs/v4/#api-_ #
#       Neon API docs - https://developer.neoncrm.com/api-v2/      #
###################################################################

from pprint import pprint
from datetime import date
from dateutil.relativedelta import relativedelta
import requests
import json
import base64
import pandas as pd

from config import N_APIkey, N_APIuser, S_APIkey


### Smartwaiver Info
S_baseURL = 'https://api.smartwaiver.com'
S_headers = {'Content-Type':'application/json','sw-api-key': S_APIkey}

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}


## Helper function for API calls
def apiCall(httpVerb, url, data, headers):
    # Make request
    if httpVerb == 'GET':
        response = requests.get(url, data=data, headers=headers)
    elif httpVerb == 'POST':
        response = requests.post(url, data=data, headers=headers)
    elif httpVerb == 'PUT':
        response = requests.put(url, data=data, headers=headers)
    elif httpVerb == 'PATCH':
        response = requests.patch(url, data=data, headers=headers)
    elif httpVerb == 'DELETE':
        response = requests.delete(url, data=data, headers=headers)
    else:
        print(f"HTTP verb {httpVerb} not recognized")

    if (response.status_code == 200):
        print(f"Success - URL: {url}")

    response = response.json()
    ## Uncomment the following line to see the full response
    # pprint(response)

    return response


##### SMARTWAIVER #####
# Get a list of waivers filled out
# https://api.smartwaiver.com/docs/v4/#api-Waivers-WaiverList
httpVerb = 'GET'
resourcePath = '/v4/waivers'
# Dates previously run left commented out for reference
# startDate = date(2020, 5, 1).isoformat()
# endDate = date(2020, 9, 1).isoformat()
# startDate = date(2020, 9, 1).isoformat()
# endDate = date(2020, 11, 20).isoformat()
# startDate = date(2020, 11, 20).isoformat()
# endDate = date(2020, 12, 5).isoformat()
# startDate = date(2020, 12, 5).isoformat()
# endDate = date.today()
endDate = date.today()
startDate = endDate - relativedelta(months=3) # Past 3 months
queryParams = f'?templateId=5f037d852d421&limit=100&fromDts={startDate}&toDts={endDate}'
data = ''
url = S_baseURL + resourcePath + queryParams

## Uncomment the following three lines to do a command line query for a specific name
# firstName = input("First name: ")
# lastName = input("Last name: ")
# url = baseURL + resourcePath + queryParams + f'&firstName={firstName}&lastName={lastName}'

# Make request
response = apiCall(httpVerb, url, data, S_headers)
print(f"Signed waivers retrieved: {len(response['waivers'])}")

# Smartwaiver returns a max of 100 waivers and does not indicate when there is additional data to retrieve
# Print warning to the console to alert users there may be missing data.
if len(response['waivers']) == 100:
    print("WARNING - Max responses received.  Results may not be complete.  Try resubmitting query with tighter date range.")

# Convert to pandas DataFrame for data cleaning and merging with Neon info
jsonSigned = json.dumps(response['waivers'])
signed = pd.read_json(jsonSigned)
signed = signed.rename(columns={"firstName": "First Name", "lastName": "Last Name"})


##### NEON #####
# Get accounts where custom field WaiverCompleted != Yes
# Accounts with unverified waiver status
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = '''
{
    "searchFields": [
        {
            "field": "WaiverCompleted",
            "operator": "NOT_EQUAL",
            "value": 30
        }
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Account ID",
        120
    ],
    "pagination": {
    "currentPage": 0,
    "pageSize": 200
    }
}
'''
# Custom field info
#   ‘id’: ‘120’,
#   ‘name’: ‘WaiverCompleted’,
#   ‘optionValues’: [{‘code’: ‘’,
#                     ‘id’: ‘30’,
#                     ‘name’: ‘Yes’},
#                    {‘code’: ‘’,
#                     ‘id’: ‘31’,
#                     ‘name’: ‘No’}]
url = N_baseURL + resourcePath + queryParams
neonResponse = apiCall(httpVerb, url, data, N_headers)

print(f"Accounts with unverified waiver: {len(neonResponse['searchResults'])}")

# Convert to pandas DataFrame for data cleaning and merging with Smartwaiver info
neonAccts = json.dumps(neonResponse['searchResults'])
unacked = pd.read_json(neonAccts)
# Merge with signed waivers data, only keep rows that exist in Smartwaiver data
merged = signed.merge(unacked, how="left", on=["First Name", "Last Name"])
# Drop rows without an Account ID to use for updating Neon
merged = merged.dropna(subset=["Account ID"])
# Change Account ID to integer
merged = merged.astype({"Account ID": int})
# Convert Account IDs to list for iterating
acctIDs = merged['Account ID'].tolist()

# Print number of accounts that will be updated (i.e. found name match in Smartwaiver response and Neon)
print(f"Accounts to update: {len(acctIDs)}")


# Base variables for account update
##### NEON #####
# Update part of an account
# https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
httpVerb = 'PATCH'
resourcePath = f'/accounts/{id}'
queryParams = '?category=Account'
data = '''
{
  "individualAccount": {
    "accountCustomFields": [
      {
        "id": "120",
        "name": "WaiverCompleted",
        "optionValues": [
          {
            "id": "30",
            "name": "Yes",
            "status": "ACTIVE"
          }
        ]
      }
    ]
  }
}
'''

# Loop through IDs and update resource path to make call for each iteration
for id in acctIDs:
    resourcePath = f'/accounts/{id}'
    url = N_baseURL + resourcePath + queryParams
    patch = apiCall(httpVerb, url, data, N_headers)


# Second check for accounts without a waiver signed
# See what's left after update
##### NEON #####
# Get accounts where custom field WaiverCompleted != Yes
# Accounts with unverified waiver status
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = '''
{
    "searchFields": [
        {
            "field": "WaiverCompleted",
            "operator": "NOT_EQUAL",
            "value": 30
        }
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Account ID",
        120
    ],
    "pagination": {
    "currentPage": 0,
    "pageSize": 200
    }
}
'''
# Custom field info
#   ‘id’: ‘120’,
#   ‘name’: ‘WaiverCompleted’,
#   ‘optionValues’: [{‘code’: ‘’,
#                     ‘id’: ‘30’,
#                     ‘name’: ‘Yes’},
#                    {‘code’: ‘’,
#                     ‘id’: ‘31’,
#                     ‘name’: ‘No’}]
url = N_baseURL + resourcePath + queryParams
neonResponse = apiCall(httpVerb, url, data, N_headers)

print(f"{len(neonResponse['searchResults'])} accounts in Neon remaining with unverified waiver status.")