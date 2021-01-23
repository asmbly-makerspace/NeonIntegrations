########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

###### NEED TO FIX NEON WORKFLOW ISSUE BEFORE THIS CAN ROLLOUT

import requests
from pprint import pprint
import json
import base64


### Neon Account Info
N_APIkey    = ''
N_APIuser   = 'atxhs'
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

### Discourse Account Info
D_APIkey  = ''
D_APIuser = ''
D_baseURL = 'https://yo.atxhs.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}


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
# Get list of custom fields
httpVerb = 'GET'
resourcePath = '/customFields'
queryParams = '?category=Account'
data = ''
url = N_baseURL + resourcePath + queryParams
fields = apiCall(httpVerb, url, data, N_headers)


# ##### NEON #####
# # Get accounts where custom field KeyAccess equals Yes
# # active members
# httpVerb = 'POST'
# resourcePath = '/accounts/search'
# queryParams = ''
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
#         83,
#         85
#     ],
#     "pagination": {
#     "currentPage": 0,
#     "pageSize": 200
#     }
# }
# '''
# # outputFiels 83 = KeyAccess, 85 = DiscourseID

# url = baseURL + resourcePath + queryParams
# responseActive = apiCall(httpVerb, url, data, headers)


# ##### NEON #####
# # Get accounts where custom field KeyAccess equals No
# # inactive members
# httpVerb = 'POST'
# resourcePath = '/accounts/search'
# queryParams = ''
# data = '''
# {
#     "searchFields": [
#         {
#             "field": "KeyAccess",
#             "operator": "EQUAL",
#             "value": 14
#         }
#     ],
#     "outputFields": [
#         "First Name", 
#         "Last Name",
#         "Preferred Name",
#         "Account ID",
#         83, 
#         85
#     ],
#     "pagination": {
#     "currentPage": 0,
#     "pageSize": 200
#     }
# }
# '''
# # outputFiels 83 = KeyAccess, 85 = DiscourseID

# url = baseURL + resourcePath + queryParams
# responseInactive = apiCall(httpVerb, url, data, headers)


# # Build list of Discourse IDs for inactive & active members



# ##### DISCOURSE #####
# # Add active members to hax0r group
# # Request Info
# httpVerb = 'PUT'
# resourcePath = '/groups/42/members.json'
# queryParams = ''
# data = {'usernames': 'valerie'}   # Change value to list generated above
# url = baseURL + resourcePath + queryParams

# updateResponse = apiCall(httpVerb, url, data, D_headers)


# ##### DISCOURSE #####
# # Remove inactive members from hax0r group
# # Request Info
# httpVerb ='DELETE'
# resourcePath = '/groups/42/members.json'
# queryParams = ''
# data = {'usernames': 'valerie'}   # Change value to list generated above
# url = baseURL + resourcePath + queryParams

# removeResponse = apiCall(httpVerb, url, data, D_headers)