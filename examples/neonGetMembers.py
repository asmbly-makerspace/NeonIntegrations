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

    #If Neon thinks the expiration date is in the past, it's surely in the past.  don't bother checking details.
    #NOTE that Neon sets "Membership Start Date" to start of the most recent membership term, not the oldest.  This means
    #     expired members that had a renewal will show incorrect start dates by our counting.
    #     I figure we won't need that data, so don't bother pulling membership details to correct it.
    if datetime.datetime.strptime(neon_accounts[account]["Membership Expiration Date"], '%Y-%m-%d').date() < today:
        expiredMemberships += 1
        continue

    #Neon counts a failed renewal as a valid subscription so long as automatic renewal is enabled.
    #WE only think a subscription is valid if the subscriber actually paid for it, so check for a successful payment.
    resourcePath="/accounts/"+account+"/memberships"
    url = N_baseURL + resourcePath
    memberships = apiCall(httpVerb, url, data, N_headers)
    latestMembershipExpiration = datetime.date(1970, 1, 1)
    firstMembershipStart = today
    failedRenewal = False

    for membership in memberships["memberships"]:
        membershipExpiration = datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date()
        membershipStart = datetime.datetime.strptime(membership["termStartDate"], '%Y-%m-%d').date()
        if membership["status"] == "SUCCEEDED":
            if membershipExpiration > latestMembershipExpiration:
                latestMembershipExpiration = membershipExpiration
            if membershipStart < firstMembershipStart:
                firstMembershipStart = membershipStart
        elif membership["status"] == "FAILED":
            #there SHOULD only be one failed membership (renewal) that expires in the future
            if membershipExpiration > today:
                failedRenewal = True
                #BUT don't break here just in case something weird is going on (like, a failed monthly renewal replaced by an annual purchase)
                #if there's a valid membership, we don't technically care if there's also an expired one
        elif membership["status"] == "DEFERRED" or membership["status"] == "CANCELED" or membership["status"] == "REFUNDED":
            #DEFERRED, CANCELED, and REFUNDED memberships aren't paid and don't allow access to the space.  Just ignore them.
            pass
        else:
            print(f'''MEMBER {neon_accounts[account]["Account ID"]} UNKNOWN STATUS EXCEPTION: "{membership["status"]}"''')


    if  latestMembershipExpiration >= today:
        successfulMemberships += 1
        neon_accounts[account]["validMembership"] = True
    else:
        #if we made it this far, it means we didn't find a valid membership
        if failedRenewal:
            failedMemberships += 1

        #print(f'''Correcting expiration date on account {neon_accounts[account]["Account ID"]} {neon_accounts[account]["Membership Expiration Date"]} to {latestMembershipExpiration} ''')
        neon_accounts[account]["Membership Expiration Date"] = str(latestMembershipExpiration)

print (f"In {accountCount} Neon accounts we found {successfulMemberships} paid memberships, {expiredMemberships} expired memberships, and {failedMemberships} failed renewals")

#write out to the file we opened up top
json.dump(neon_accounts, outfile, indent=4)

