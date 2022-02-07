########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import json
import base64
#import csv

from config import N_APIkey, N_APIuser, D_APIkey, D_APIuser
from util import apiCall

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

### Discourse Account Info
D_baseURL = 'https://yo.asmbly.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}

#testing flag.  this should probably be a command-line arguement
dryRun = False

neonFilename = "Neon/memberAccounts.json"
neonAccounts = {}

# ##### NEON ######
#first off, check that we have a Neon account list before spending a bunch of time on the Discourse API
with open(neonFilename) as neonFile:
    neonAccountJson = json.load(neonFile)
    for account in neonAccountJson:
        neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

# ##### DISCOURSE #####
# retrieve all members of hax0r group
haxors = {}

httpVerb = 'GET'
resourcePath = '/groups/haxor/members.json'
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
        #print(haxor["username"]+" is a haxor")
        haxors[member["username"]] = member


##### AUDIT OPERATIONS #####
#Discourse Group IDs
# 42 = haxor
# 45 = haxorcommunity

print()
#this first loop adds people to haxors (or notes lack of DiscourseID)
httpVerb = 'POST'
resourcePath = '/groups/42/members.json'
url = D_baseURL + resourcePath
addHaxor = ""

#Step 1a: find all Neon accounts that are paid up, have a DiscourseID, and aren't in Hax0rs
for account in neonAccounts:
    if neonAccounts[account].get("validMembership") != True:
        continue
    #pprint(neonAccounts[account])
    if neonAccounts[account].get("DiscourseID") is None or neonAccounts[account].get("DiscourseID") == "":
        #neon accounts missing a DiscourseID
        #print(neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+" ("+neonAccounts[account]["Account ID"]+") is active but has no Discourse ID")
        pass
    elif haxors.get(neonAccounts[account]["DiscourseID"]) is None:
        dID = neonAccounts[account]["DiscourseID"]
        #neon accounts not in Haxor group
        print(dID+" ("+neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+") is active and will be added to Haxors")
        if addHaxor != "":
            addHaxor+= ','
        addHaxor += f'{dID}'

if addHaxor != "":
    #Step 1b: if we found any, add them to Hax0rs
    #use Discourse groups API to add missing members by username
    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    data = {'usernames': addHaxor}
    #print("Adding hax0rs: "+str(data))
    if not dryRun:
        httpVerb = 'PUT'
        updateResponse = apiCall(httpVerb, url, data, D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames - means we picked up an invalid discourse username somewhere

    #Step 2c: remove them from HaxorCommunity
    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    data = {'usernames': addHaxor}
    #print("Removing HaxorCommunity: "+str(data))
    if not dryRun:
        httpVerb = 'DELETE'
        updateResponse = apiCall(httpVerb, url, data, D_headers)
        #pprint(updateResponse)
        #don't bother with skipped usernames here - anyone who isn't a lapsed members will fail to remove from haxorcommunity


#until we decommission FreshBooks, hax0r auditing is weirded
#for now just remove people with valid neon accounts who let their subscriptions lapse
print()
#step 2 : find hax0rs without an active membership
removeHaxor = ""
matchedAccounts = 0
for haxor in haxors:
    expired = False
    match = False
    for account in neonAccounts:
        if haxor == neonAccounts[account].get("DiscourseID"):
            match = True
            if not neonAccounts[account].get("validMembership"):
                expired = True

    if expired:
        print(haxor+" ("+haxors[haxor]["name"]+") used to be a subscriber but is no longer")
        if removeHaxor != "":
            removeHaxor+= ','
        removeHaxor += f'{haxor}'
    if not match:
        #print(haxor+" ("+haxors[haxor]["name"]+") doesn't seem to have a Neon record")
        #this will happen must less often once we stop using Freshbooks
        pass

if removeHaxor != "":
    #Step 2b: if we found any, add them to Hax0rCommunity
    #use Discourse groups API to add missing members by username
    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    data = {'usernames': removeHaxor}
    #print("Adding hax0rCommunity: "+str(data))
    if not dryRun:
        httpVerb = 'PUT'
        updateResponse = apiCall(httpVerb, url, data, D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

    #Step 2c: remove them from Haxors
    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    data = {'usernames': removeHaxor}
    #print("Removing Haxors: "+str(data))
    if not dryRun:
        httpVerb = 'DELETE'
        updateResponse = apiCall(httpVerb, url, data, D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

exit()

# ... do we want to prune hax0rcommunity?
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

#Discourse APIs seem to randomly identify groups by name or by ID
#"id":45,"name":"_hax0rcommunity"
#"id":42,"name":"haxor"

