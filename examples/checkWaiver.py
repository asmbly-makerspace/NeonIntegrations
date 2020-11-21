################# ATXHS Smartwaiver API Integrations #################
# Smartwaiver API docs - https://api.smartwaiver.com/docs/v4/#api-_ #
####################################################################

import requests
from pprint import pprint
from datetime import date
import json
import hashlib
import base64
import time
import hmac
import pandas as pd


# Request Info
S_APIkey = ''
S_baseURL = 'https://api.smartwaiver.com'
S_headers = {'Content-Type':'application/json','sw-api-key': S_APIkey}


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

    response = response.json()
    pprint(response)

    return response

##### SMARTWAIVER #####
# Get a list of waivers filled out
# https://api.smartwaiver.com/docs/v4/#api-Waivers-WaiverList
httpVerb = 'GET'
resourcePath = '/v4/waivers'
startDate = date(2020, 5, 1).isoformat()
endDate = date(2020, 9, 1).isoformat()
# startDate = date(2020, 9, 1).isoformat()
# endDate = date(2020, 11, 20).isoformat()
queryParams = f'?templateId=5f037d852d421&limit=100&fromDts={startDate}&toDts={endDate}'
# firstName = input("First name: ")
# lastName = input("Last name: ")
data = ''

# url = baseURL + resourcePath + queryParams + f'&firstName={firstName}&lastName={lastName}'
url = S_baseURL + resourcePath + queryParams


# Make request
response = apiCall(httpVerb, url, data, S_headers)
print(len(response['waivers']))

if len(response['waivers']) == 100:
    print("WARNING - Max responses received.  Results may not be complete.  Try resubmitting query with tighter date range.")



# update = false

# if responseJSON['search']['count'] > 0:
#     print(f'Waiver completed for {firstName} {lastName}')
#     update = true
# else:
#     print(f'ERROR:  Waiver not found for {firstName} {lastName}. Please check spelling and try again.')

# @TODO - Integrate in full script with Neon to update custom account field    