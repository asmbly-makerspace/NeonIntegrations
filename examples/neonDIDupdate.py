########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import json
import base64
import os

from config import N_APIkey, N_APIuser, D_APIkey, D_APIuser
from util import apiCall

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

### Discourse Account Info
D_baseURL = 'https://yo.atxhs.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}

##### DISCOURSE #####
# Get a list of all active users on Discourse
# Discourse queries return max 100 results, so if we get 100 try for another page
httpVerb ='GET'
page = 0
data = ''
fullDlist = []

#testing flag.  this should probably be a command-line arguement
dryRun = False

discourseFilename = "Discourse/usersFull.json"
neonFilename = "Neon/memberAccounts.json"
neonDImissingFilename = "Neon/dIDmissing.json"

neonAccountList = []
noDIDlist = []
matchedDiscourseIDs = 0
fixedDiscourseIDs = 0

#first off, check that we have a Neon account list before spending a bunch of time on the Discourse API
with open(neonFilename) as neonFile:
    neonAccountJson = json.load(neonFile)
    for account in neonAccountJson:
        neonAccountList.append(neonAccountJson.get(account))


#check if we have user data cached.  If we do, use it.
if os.path.exists(discourseFilename) and os.access(discourseFilename, os.R_OK):
    with open(discourseFilename) as discourseFile:
        fullDlist = json.load(discourseFile)
else:
    #before doing all the Discourse-fetching, make sure we can write our output file
    outfile = open(neonFilename, 'w')

    while True:
        resourcePath = f'/admin/users/list/active.json?page={page}'
        url = D_baseURL + resourcePath
        memberResponse = apiCall(httpVerb, url, data, D_headers)
        fullDlist = fullDlist + memberResponse
        if len(memberResponse) < 100:
            break
        else:
            print(f'{len(fullDlist)} active users retrieved from Discourse... Querying for more data.')
            page += 1

    # Fetching emails and checking for weirdness (the weirdness is not coming from here.)
    # this email check is janky somehow - sometimes we get "email":null for accounts with valid emails in their Discourse profile
    # so far the error count has been low enough I've just been updating them in Neon manually
    for i, response in enumerate(fullDlist):
        dID = response['username']
        resourcePath = f'/users/{dID}/emails.json'
        url = D_baseURL + resourcePath
        emailResponse = apiCall(httpVerb, url, data, D_headers)
        fullDlist[i]["email"]=emailResponse.get("email")
        fullDlist[i]["secondary_emails"]=emailResponse.get("secondary_emails")
        if " " in dID:
            print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {i}.')
        elif "|" in dID:
            print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {i}.')
        else:
            # print("All good")
            continue

    print(f'{len(fullDlist)} active users retrieved from Discourse... saving to file as {discourseFilename}')
    json.dump(fullDlist, outfile, indent=4)

# Loop through response from Neon and update accounts where there is a matching name in Discourse
for acct in neonAccountList:
    fullname = f'{acct["First Name"]} {acct["Last Name"]}'
    email = acct["Email 1"]
    neonID = acct.get('Account ID')
    if acct.get("DiscourseID") is not None:
        dID = acct.get("DiscourseID")
        if any(dUser.get("username") == dID for dUser in fullDlist):
            matchedDiscourseIDs += 1
            continue
        else:
            print(f"{fullname}'s dID {dID} doesn't actually exist in Discourse (Neon ID {neonID})")
    else:
        print(f"{fullname} doesn't have a DiscourseID (Neon ID {neonID})")

    dID = ""
    for Daccount in fullDlist:
        if Daccount.get("email") and Daccount.get("email").casefold() == email.casefold():
            dID = Daccount.get("username")
            #print(f'{fullname} (Neon Acct #{neonID}) matches email with Discourse ID {dID}')
            break
        elif Daccount.get("name") and Daccount.get("name").casefold() == fullname.casefold():
            dID = Daccount.get("username")
            #print(f'{fullname} (Neon Acct #{neonID}) matches name with Discourse ID {dID}')
            break

    if dID != "":
        fixedDiscourseIDs += 1
        if dryRun == True:
            print(f'   Could update DiscourseID to {dID} for Neon account #{neonID} - {fullname} {email}')
        else:
            print(f'   Updating DiscourseID to {dID} for Neon account #{neonID} - {fullname} {email}')
            ##### NEON #####
            # Update part of an account
            # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
            httpVerb = 'PATCH'
            resourcePath = f'/accounts/{neonID}'
            queryParams = '?category=Account'
            data = f'''
            {{
            "individualAccount": {{
                "accountCustomFields": [
                {{
                    "id": "85",
                    "name": "DiscourseID",
                    "value": "{dID}"
                }}
                ]
            }}
            }}
            '''
            url = N_baseURL + resourcePath + queryParams
            patch = apiCall(httpVerb, url, data, N_headers)
    else:
        print(f'   No DiscourseID found for Neon account #{neonID} - {fullname} {email}')
        noDIDlist.append(acct)

print("-------------------")
print(f'{len(neonAccountList)} Neon accounts were checked')
print(f'{matchedDiscourseIDs} had valid Discourse IDs')
print(f'{fixedDiscourseIDs} were updated based on name or email matching' )
print(f'{len(noDIDlist)} accounts still need Discourse IDs.')

# Print to file.  Do this open at the very end so Neon updates
# complete even if the report can't be saved
with open(neonDImissingFilename, 'w') as outfile:
    print(f'Report saved to file as {neonDImissingFilename} for further review.')
    json.dump(noDIDlist, outfile, indent=4)