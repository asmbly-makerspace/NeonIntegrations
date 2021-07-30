########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from pprint import pprint
import json
import base64
import datetime
from datetime import date
import os

today = date.today()

from config import N_APIkey, N_APIuser
from util import apiCall

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

#before doing all the Neon-fetching, make sure we can write our output file
#TODO filename should be a global config or command-line option or something
outfile = open('./Neon/memberAccounts.json', 'w')

##### NEON #####
# Step 1: Retrieve list of members who expire in the future
page = 0
httpVerb = 'POST'
resourcePath = '/accounts/search'
neon_accounts = {}

#85 is DiscourseId
#77 is OrientationDate
#179 is WaiverDate
#88 is KeyCardID
#178 is OpenPathID
#180 is AccessSuspended


while True:
    # Neon does pagination as a data parameter, so need to update data for each page
    data = f'''
{{
    "searchFields": [
        {{
            "field": "Membership Expiration Date",
            "operator": "NOT_BLANK"
        }}
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        "Email 1",
        "Email 2",
        "Email 3",
        "Membership Expiration Date",
        "Membership Start Date",
        85, 77, 179, 178, 88, 180, 182
    ],
    "pagination": {{
    "currentPage": {page},
    "pageSize": 100
    }}
}}
'''
    url = N_baseURL + resourcePath
    responseAccounts = apiCall(httpVerb, url, data, N_headers)
    pprint(responseAccounts.get("pagination"))
    #re-shuffle the data into a format that's a little easier to work with
    for acct in responseAccounts["searchResults"]:
        neon_accounts[acct["Account ID"]] = acct
    #intentionally incrementing page before checking totalPages 
    #"page" is 0-based, "totalPages" is 1-based
    page += 1
    if page >= responseAccounts.get("pagination").get("totalPages"):
        break


##### NEON #####
#Step 2: Because Neon API is dumb, the "expiration date" of an account might not be real -- 
#        The API counts failed renewals as valid as long as automatic renewal is enabled

httpVerb = 'GET'
data = ''
accountCount = 0
successfulMemberships = 0
failedMemberships = 0
expiredMemberships = 0

for account in neon_accounts:
    #TODO print some progress info so it doesn't look like the script hung
    
    #An account is valid if it posesses at least one membership record with an
    #end date >= today and a transaction status of SUCCEEDED
    neon_accounts[account]["validMembership"] = False
    accountCount += 1
    failedRenewal = False

    resourcePath="/accounts/"+account+"/memberships"
    url = N_baseURL + resourcePath
    memberships = apiCall(httpVerb, url, data, N_headers)

    for membership in memberships["memberships"]:
        #TODO fixup "Membership Expiration Date" field for accounts with failed renewals
        # subtract membership term from expiration date (I think?)
        #Right now, the config of failed renewals is expiration-in-the-future, with validMembership=false
        if datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date() >= today:
            if membership["status"] == "SUCCEEDED":
                successfulMemberships += 1
                #print(membership["id"]+" expires in the future and it SUCCEEDED")
                neon_accounts[account]["validMembership"] = True
            elif membership["status"] == "FAILED":
                failedRenewal = True
                failedMemberships += 1
                #print(membership["id"]+" expires in the future and it FAILED")
                pass
            elif membership["status"] == "DEFERRED":
                #known wonky Neon account - don't keep warning for it
                if membership["id"] != 999:
                    print("WARNING current subscription is DEFERRED for neon account "+membership["id"])
                pass
            else:
                print(membership["id"]+" STATUS EXCEPTION WTF "+membership["status"])
    
    if neon_accounts[account]["validMembership"] != True and failedRenewal != True:
        expiredMemberships += 1
        #print(membership["id"]+" expired in the past")

print (f"In {accountCount} Neon accounts we found {successfulMemberships} paid memberships, {expiredMemberships} expired memberships, and {failedMemberships} failed renewals")

#write out to the file we opened up top
json.dump(neon_accounts, outfile, indent=4)

