########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

###### NEED TO FIX NEON WORKFLOW ISSUE BEFORE THIS CAN ROLLOUT

import requests
from pprint import pprint
import json
import base64
import csv
from datetime import date

from config import N_APIkey, N_APIuser, D_APIkey, D_APIuser


### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

### Discourse Account Info
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
    #pprint(response)

    return response


#today = date.today()
#print("Today's date:", today)


# ##### NEON ######
# for now we're working from local cache
neonAccounts = {}
with open('activeAccounts.csv', mode='r') as csv_file:
    neonReader = csv.DictReader(csv_file)
    for account in neonReader:
        neonAccounts[account["Account ID"]] = account


# ##### Freshbooks #####
# load the "freshbooks exceptions" accounts
freshbooksAccounts = {}
with open('freshbooksAccounts.csv', mode='r') as csv_file:
    fbReader = csv.DictReader(csv_file)
    for account in fbReader:
        freshbooksAccounts[account["DiscourseID"]] = account


# ##### DISCOURSE #####
# retrieve all members of hax0r group
haxors = {}

httpVerb = 'GET'
resourcePath = '/groups/haxor/members.json'
limit = 20
offset = 0
total = 0
data = ''
while offset + limit <= total+limit:
    url = D_baseURL + resourcePath + "?limit="+str(limit)+"&offset="+str(offset)
    response = apiCall(httpVerb, url, data, D_headers)
    offset += limit
    pprint(response["meta"])
    total = int(response["meta"]["total"])
    for member in response["members"]:
        #print(haxor["username"]+" is a haxor")
        haxors[member["username"]] = member


# ##### DISCOURSE #####
# retrieve all members of Members2B group
members2B = {}

httpVerb = 'GET'
resourcePath = '/groups/Members2B/members.json'
limit = 50
offset = 0
total = 0
data = ''

while offset + limit <= total+limit:
    url = D_baseURL + resourcePath + "?limit="+str(limit)+"&offset="+str(offset)
    response = apiCall(httpVerb, url, data, D_headers)
    offset += limit
    pprint(response["meta"])
    total = int(response["meta"]["total"])
    for member in response["members"]:
        #print(member["username"]+" is a member2B")
        members2B[member["username"]] = member


##### AUDIT OPERATIONS #####
print()
print("Neon active member audit results")
for account in neonAccounts:
    #pprint(neonAccounts[account])
    if neonAccounts[account]["DiscourseID"] == "":
        #step one : neon accounts missing a DiscourseID
        print(neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+" ("+neonAccounts[account]["Account ID"]+") has no Discourse ID")
    elif haxors.get(neonAccounts[account]["DiscourseID"]) is None:
        #step 1.5 : neon accounts not in Haxor group
        print(neonAccounts[account]["DiscourseID"]+" ("+neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+") Should be in Haxors, but isn't")

print()
print("Haxor Discourse Group audit results")
#step two : hax0rs without an active membership
matchedAccounts = 0
fbExceptionAccounts = 0
for haxor in haxors:
    match = False
    if freshbooksAccounts.get(haxor):
        match = True
        fbExceptionAccounts += 1
    else:
        for account in neonAccounts:
            if haxor == neonAccounts[account].get("DiscourseID"):
                matchedAccounts += 1
                match = True
    if match == False:
        print(haxor+" ("+haxors[haxor]["name"]+") is not an active ATXHS member")

print("Found Neon matches for "+str(matchedAccounts)+" Haxors")
print("Found FB exception matches for "+str(fbExceptionAccounts)+" Haxors")

print()
print("Members2B Discourse Group audit results")
#step three - members2B that are now members
for account in members2B:
    if haxors.get(account):
        print(account+" ("+members2B[account]["name"]+") is a haxor now, so should be removed from Members2B")
exit()


# ##### DISCOURSE #####
# retrieve all members of _hax0rcommunity group
haxorCommunity = {}

httpVerb = 'GET'
resourcePath = '/groups/_hax0rcommunity/members.json'
limit = 50
offset = 0
total = 0
data = ''
while offset + limit <= total+limit:
    url = D_baseURL + resourcePath + "?limit="+str(limit)+"&offset="+str(offset)
    response = apiCall(httpVerb, url, data, D_headers)
    offset += limit
    pprint(response["meta"])
    total = int(response["meta"]["total"])
    for member in response["members"]:
        #print(member["username"]+" is in hax0rCommunity")
        haxorCommunity[member["username"]] = member

#Active members - add to haxor, remove from hax0rcommunity and/or Members2B
#Inactive members - remove from haxor, add to hax0rcommunity

#Discourse APIs seem to randomly identify groups by name or by ID
#"id":45,"name":"_hax0rcommunity"
#"id":42,"name":"haxor"
#"id":52,"name":"Members2B"

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