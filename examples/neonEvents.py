########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

import requests
from pprint import pprint
import json
import hashlib
import base64
import time
import hmac


# Neon Account Info
N_APIkey = ''
N_APIuser = 'atxhs'
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

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


##### NEON #####
# Get list of custom fields for events
httpVerb = 'GET'
resourcePath = '/customFields'
queryParams = '?category=Events'
data = ''

url = N_baseURL + resourcePath + queryParams
print("### CUSTOM FIELDS ###\n")
responseFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get possible search fields for POST to /events/search
httpVerb = 'GET'
resourcePath = '/events/search/searchFields'
queryParams = ''
data = ''
# Event Category

url = N_baseURL + resourcePath + queryParams
print("### SEARCH FIELDS ###\n")
responseSearchFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get possible output fields for POST to /events/search
httpVerb = 'GET'
resourcePath = '/events/search/outputFields'
queryParams = ''
data = ''

url = N_baseURL + resourcePath + queryParams
print("### OUTPUT FIELDS ###\n")
responseOutputFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get events in the Woodworking Event Category
httpVerb = 'POST'
resourcePath = '/events/search'
queryParams = ''
data = '''
{
    "searchFields": [
        {
            "field": "Event Category",
            "operator": "EQUAL",
            "value": "Woodworking"
        }
    ],
    "outputFields": [
        "Event Name", 
        "Event Topic",
        "Event Start Date",
        "Event Start Time",
        "Event End Date",
        "Event End Time"
    ],
    "pagination": {
    "currentPage": 0,
    "pageSize": 200
    }
}
'''

url = N_baseURL + resourcePath + queryParams
print("### WOODWORKING EVENTS ###\n")
responseWoodworkingEvents = apiCall(httpVerb, url, data, N_headers)