########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################
#################################################################
#  This helper script assists in making bulk updates to events  #
#  in Neon.  If event details have changed and need to be       #
#  updated for a large number of events, change one the way     #
#  you want it in the UI, then use this script to pull the      #
#  changes and PATCH it to all other events.                    #
#################################################################

from pprint import pprint
import requests
import json
import base64
import time
import datetime

from config import N_APIkey, N_APIuser


# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}


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

    # These lines break the code for PATCH requests
    # response = response.json()
    # pprint(response)

    return response


# ##### NEON #####
# # Get list of custom fields for events
# httpVerb = 'GET'
# resourcePath = '/customFields'
# queryParams = '?category=Event'
# data = ''

# url = N_baseURL + resourcePath + queryParams
# print("### CUSTOM FIELDS ###\n")
# responseFields = apiCall(httpVerb, url, data, N_headers).json()
# pprint(responseFields)


# ##### NEON #####
# # Get possible search fields for POST to /events/search
# httpVerb = 'GET'
# resourcePath = '/events/search/searchFields'
# queryParams = ''
# data = ''
# # Event Category

# url = N_baseURL + resourcePath + queryParams
# print("### SEARCH FIELDS ###\n")
# responseSearchFields = apiCall(httpVerb, url, data, N_headers)

# response = responseSearchFields.json()
# pprint(response)


# ##### NEON #####
# # Get possible output fields for POST to /events/search
# httpVerb = 'GET'
# resourcePath = '/events/search/outputFields'
# queryParams = ''
# data = ''

# url = N_baseURL + resourcePath + queryParams
# print("### OUTPUT FIELDS ###\n")
# responseOutputFields = apiCall(httpVerb, url, data, N_headers)

# response = responseOutputFields.json()
# pprint(response)


# ##### NEON #####
# # Get event with correct details
# # today = datetime.date.today()
# # print(f"TODAY IS {today}")

# httpVerb = 'POST'
# resourcePath = '/events/search'
# queryParams = ''
# data = f'''
# {{
#     "searchFields": [
#         {{
#             "field": "Event Name",
#             "operator": "CONTAIN",
#             "value": "Orientation"
#         }},
#         {{
#             "field": "Event Start Date",
#             "operator": "EQUAL",
#             "value": "2021-05-11"
#         }}
#     ],
#     "outputFields": [
#         "Event Summary",
#         "Event Description"
#     ],
#     "pagination": {{
#     "currentPage": 0,
#     "pageSize": 200
#     }}
# }}
# '''

# url = N_baseURL + resourcePath + queryParams
# # print("### CORRECT EVENT ###\n")
# responseEvents = apiCall(httpVerb, url, data, N_headers).json()

# pprint(responseEvents)

### Testing revealed Neon does not support this :( 
# It is worthy of further investigation with their support team as this is a major limitation
# newSumm = responseEvents['searchResults'][0]['Event Summary']
# newDesc = responseEvents['searchResults'][0]['Event Description']

# print("\n********* INFO TO UPDATE WITH *********\n")
# print(newSumm)
# print(newDesc)


### NEON #####
# Get events that need this new info
today = datetime.date.today()
print(f"TODAY IS {today}")

httpVerb = 'POST'
resourcePath = '/events/search'
queryParams = ''
data = f'''
{{
    "searchFields": [
        {{
            "field": "Event End Date",
            "operator": "GREATER_THAN",
            "value": "{today}"
        }},
        {{
            "field": "Event Name",
            "operator": "CONTAIN",
            "value": "Woodshop Safety"
        }}
    ],
    "outputFields": [
        "Event Name", 
        "Event ID",
        "Event Category Name"
    ],
    "pagination": {{
    "currentPage": 0,
    "pageSize": 200
    }}
}}
'''

url = N_baseURL + resourcePath + queryParams
print("### EVENTS TO UPDATE ###\n")
responseEvents = apiCall(httpVerb, url, data, N_headers).json()

pprint(responseEvents["searchResults"][:])


# Iterate over response to archive each event
for event in responseEvents["searchResults"]:
    httpVerb = 'PATCH'
    resourcePath = f'/events/{event["Event ID"]}'
    queryParams = ''
    data = f'''
    {{
        "category": {{
            "id": "15",
            "name": "Woodshop Safety",
            "status": "ACTIVE"
        }}
    }}
    '''

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers)

    print(f'API response code for event {event["Event ID"]}: {responseEvents}')


### NOTE - Neon uses different keys for the body that must be sent for PATCHes than what is returned from field search queries
### Example schema for json structure when submitting PATCH:
# {
#   "archived": true,
#   "campaign": {
#     "id": "1234",
#     "name": "Example",
#     "status": "ACTIVE"
#   },
#   "category": {
#     "id": "1234",
#     "name": "Example",
#     "status": "ACTIVE"
#   },
#   "code": "string",
#   "createAccountsforAttendees": true,
#   "enableEventRegistrationForm": true,
#   "enableWaitListing": true,
#   "eventDates": {
#     "endDate": "2021-01-20 12:00:00",
#     "endTime": "string",
#     "registrationCloseDate": "2021-01-20 12:00:00",
#     "registrationOpenDate": "2021-01-20 12:00:00",
#     "startDate": "2021-01-20 12:00:00",
#     "startTime": "string",
#     "timeZone": {
#       "id": "1234",
#       "name": "Example",
#       "status": "ACTIVE"
#     }
#   },
#   "eventDescription": "string",
#   "financialSettings": {
#     "admissionFee": {
#       "craInfo": {
#         "advantageAmount": 12345,
#         "advantageDescription": "string"
#       },
#       "fee": 1.23,
#       "taxDeductiblePercent": 1.23
#     },
#     "donations": {
#       "label": "string",
#       "type": "None"
#     },
#     "feeType": "Free",
#     "fund": {
#       "id": "1234",
#       "name": "Example",
#       "status": "ACTIVE"
#     },
#     "taxDeductiblePortion": {
#       "fund": {
#         "id": "1234",
#         "name": "Example",
#         "status": "ACTIVE"
#       },
#       "purpose": {
#         "id": "1234",
#         "name": "Example",
#         "status": "ACTIVE"
#       }
#     },
#     "ticketsPerRegistration": {
#       "number": 0,
#       "operator": "Up_to"
#     }
#   },
#   "id": "string",
#   "location": {
#     "address": "string",
#     "buildingNumber": "string",
#     "city": "string",
#     "country": {
#       "id": "1234",
#       "name": "Example",
#       "status": "ACTIVE"
#     },
#     "name": "string",
#     "roomNumber": "string",
#     "stateProvince": {
#       "code": "CODE",
#       "name": "Name",
#       "status": "ACTIVE"
#     },
#     "zipCode": "string",
#     "zipCodeSuffix": "string"
#   },
#   "maximumAttendees": 0,
#   "name": "string",
#   "publishEvent": true,
#   "summary": "string",
#   "topic": {
#     "id": "1234",
#     "name": "Example",
#     "status": "ACTIVE"
#   }
# }