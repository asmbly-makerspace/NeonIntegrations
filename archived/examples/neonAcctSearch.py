########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from pprint import pprint
import json
import base64
import datetime
from datetime import date

from config import N_APIkey, N_APIuser
from util import apiCall

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}


##### NEON #####
# Get list of custom fields for events
# httpVerb = 'GET'
# resourcePath = '/customFields'
# queryParams = '?category=Account'
# data = ''
# url = N_baseURL + resourcePath + queryParams
# print("### CUSTOM FIELDS ###\n")
# responseFields = apiCall(httpVerb, url, data, N_headers)


##### NEON #####
# Get possible search fields for POST to /accounts/search
# httpVerb = 'GET'
# resourcePath = '/accounts/search/searchFields'
# queryParams = ''
# data = ''
# url = N_baseURL + resourcePath + queryParams
# print("### SEARCH FIELDS ###\n")
# responseSearchFields = apiCall(httpVerb, url, data, N_headers)

##### NEON #####
# Get possible output fields for POST to /accounts/search
# httpVerb = 'GET'
# resourcePath = '/accounts/search/outputFields'
# queryParams = ''
# data = ''
# url = N_baseURL + resourcePath + queryParams
# print("### OUTPUT FIELDS ###\n")
# responseOutputFields = apiCall(httpVerb, url, data, N_headers)

# # Membership related output fields:
# 'Membership Amount Paid',
# 'Membership Change Type',
# 'Membership Cost',
# 'Membership Coupon Code',
# 'Membership Discount',
# 'Membership Enrollment Date',
# 'Membership Enrollment Type',
# 'Membership Name',
# 'Membership Start Date' - specific to most current membership (not a reflection of when they first joined)
# 'Membership Expiration Date' - specific to most current membership

##### NEON #####
# Start by getting list of members who expire in the future
# outputFields 83 = KeyAccess, 85 = DiscourseID TODO = keycard number
# TODO handle pagination for >200 accounts
today = date.today()
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = f'''
{{
    "searchFields": [
        {{
            "field": "Membership Expiration Date",
            "operator": "GREATER_AND_EQUAL",
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
        85
    ],
    "pagination": {{
    "currentPage": 0,
    "pageSize": 200
    }}
}}
'''

url = N_baseURL + resourcePath + queryParams
neon_accounts = {}
responseAccounts = apiCall(httpVerb, url, data, N_headers)

# exit()

#re-shuffle the data into a format that's a little easier to work with
for acct in responseAccounts["searchResults"]:
    neon_accounts[acct["Account ID"]] = acct

#Because Neon API is dumb, the "expiration date" of an account might not be real -- 
#The API counts failed renewals as valid as long as automatic renewal is enabled
httpVerb = 'GET'
resourcePath = '/accounts/search'
queryParams = ''
data = ''

for account in neon_accounts:
    #An account is valid if it posesses at least one membership record with an
    #end date >= today and a transaction status of SUCCEEDED
    neon_accounts[account]["validMembership"] = False

    resourcePath="/accounts/"+account+"/memberships"
    url = N_baseURL + resourcePath + queryParams
    memberships = apiCall(httpVerb, url, data, N_headers)

    for membership in memberships["memberships"]:
        if datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date() >= today:
            if membership["status"] == "SUCCEEDED":
                #print(membership["id"]+" expires in the future and it SUCCEEDED")
                neon_accounts[account]["validMembership"] = True
            elif membership["status"] == "FAILED":
                #print(membership["id"]+" expires in the future and it FAILED")
                pass
            else:
                print(membership["id"]+" STATUS EXCEPTION WTF "+membership["status"])

print("Account ID,DiscourseID,Preferred Name,First Name,Last Name,Expiration Date")
for account in neon_accounts:
    if neon_accounts[account]["validMembership"] == True:
        discourseIdStr = ""
        if neon_accounts[account]["DiscourseID"] is not None:
            discourseIdStr = neon_accounts[account]["DiscourseID"]
        print(neon_accounts[account]["Account ID"]+","+discourseIdStr+","+neon_accounts[account]["Preferred Name"]+
            ","+neon_accounts[account]["First Name"]+","+neon_accounts[account]["Last Name"]+","+neon_accounts[account]["Membership Expiration Date"])