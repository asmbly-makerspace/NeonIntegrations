########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

import requests
from pprint import pprint
import json
import base64
from datetime import date

today = date.today()
print("Today's date:", today)


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
queryParams = '?category=Account'
data = ''

url = N_baseURL + resourcePath + queryParams
# print("### CUSTOM FIELDS ###\n")
# responseFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get possible search fields for POST to /accounts/search
httpVerb = 'GET'
resourcePath = '/accounts/search/searchFields'
queryParams = ''
data = ''

url = N_baseURL + resourcePath + queryParams
# print("### SEARCH FIELDS ###\n")
# responseSearchFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get possible output fields for POST to /accounts/search
httpVerb = 'GET'
resourcePath = '/accounts/search/outputFields'
queryParams = ''
data = ''

url = N_baseURL + resourcePath + queryParams
# print("### OUTPUT FIELDS ###\n")
# responseOutputFields = apiCall(httpVerb, url, data, N_headers)

# # Membership related output fields
# 'Membership Amount Paid',
# 'Membership Change Type',
# 'Membership Cost',
# 'Membership Coupon Code',
# 'Membership Discount',
# 'Membership Enrollment Date',
# 'Membership Enrollment Type',
# 'Membership Expiration Date',
# 'Membership Name',
# 'Membership Start Date',



##### NEON #####
# Get accounts where custom field KeyAccess equals Yes
# active members
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = f'''
{{
    "searchFields": [
        {{
            "field": "Membership Expiration Date",
            "operator": "GREATER_THAN",
            "value": "{today}"
        }},
        {{
            "field": "Membership Start Date",
            "operator": "LESS_THAN",
            "value": "{today}"
        }}
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        "Membership Expiration Date",
        "Membership Start Date",
        83,
        85
    ],
    "pagination": {{
    "currentPage": 0,
    "pageSize": 200
    }}
}}
'''
# data = '''
# {
#     "searchFields": [
#         {
#             "field": "KeyAccess",
#             "operator": "EQUAL",
#             "value": 13
#         }
#     ],
#     "outputFields": [
#         "First Name", 
#         "Last Name",
#         "Preferred Name",
#         "Account ID",
#         "Membership Expiration Date",
#         83,
#         85
#     ],
#     "pagination": {
#     "currentPage": 0,
#     "pageSize": 200
#     }
# }
# '''
# outputFields 83 = KeyAccess, 85 = DiscourseID

url = N_baseURL + resourcePath + queryParams
responseActive = apiCall(httpVerb, url, data, N_headers)