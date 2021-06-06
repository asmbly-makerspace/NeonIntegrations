########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import json
import base64

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


## Helper function to find the index of a list based on specified key and value
def findI(list, key, value):
    for i, dict in enumerate(list):
        if dict[key] == value:
            return i
    return -1


##### DISCOURSE #####
# Get a list of all active users on Discourse
# Discourse queries return max 100 results, so if we get 100 try for another page
httpVerb ='GET'
page = 0
data = ''
fullDlist = []

while True:
    resourcePath = f'/admin/users/list/active.json?page={page}'
    url = D_baseURL + resourcePath
    memberResponse = apiCall(httpVerb, url, data, D_headers)
    fullDlist = fullDlist + memberResponse
    if len(memberResponse) < 100:
        print(f'{len(fullDlist)} active users retrieved from Discourse... saving to file as ./Discourse/usersFull.json')
        # Print to file
        #TODO create directory if it doesn't exist
        with open('./Discourse/usersFull.json', 'w') as outfile:
            json.dump(fullDlist, outfile, indent=4)
        break
    else:
        print(f'{len(fullDlist)} active users retrieved from Discourse... Querying for more data.')
        page += 1

# Checking for weirdness... the weirdness is not coming from here.
for i, response in enumerate(fullDlist):
    dID = response['username']
    if " " in dID:
        print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {index}.')
    elif "|" in dID:
        print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {index}.')
    else:
        # print("All good")
        continue


##### NEON #####
# Get accounts where custom field DiscourseID is blank
# members without DiscourseID saved in their account

page = 0
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
fullSearchResults = []

while True:
    # Neon does pagination as a data parameter, so need to update data for each page
    # outputFiels 85 = DiscourseID
    data = f'''
{{
    "searchFields": [
        {{
            "field": "DiscourseID",
            "operator": "BLANK",
            "value": ""
        }}
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        85
    ],
    "pagination": {{
    "currentPage": {page},
    "pageSize": 100
    }}
}}
'''
    url = N_baseURL + resourcePath + queryParams
    dIDmissingResponse = apiCall(httpVerb, url, data, N_headers)
    pprint(dIDmissingResponse.get("pagination"))
    fullSearchResults = fullSearchResults + dIDmissingResponse.get("searchResults")
    #intentionally incrementing page before checking totalPages 
    #"page" is 0-based, "totalPages" is 1-based
    page += 1
    if page >= dIDmissingResponse.get("pagination").get("totalPages"):
        break

print(f'{len(fullSearchResults)} accounts in Neon missing Discourse IDs. Checking user list from Discourse to update accounts in Neon...')

noDIDlist = []

# Loop through response from Neon and update accounts where there is a matching name in Discourse
for acct in fullSearchResults:
    # Combine fields from Neon response to variable for fullname
    fullname = f'{acct["First Name"]} {acct["Last Name"]}'
    acctID = acct["Account ID"]
    # Check if any names from Discourse response match names in Neon
    if any(name.get("name") == fullname for name in fullDlist):
        # Find the index of the item in the Discourse response object that matches the name
        index = findI(fullDlist, "name", fullname)
        print(f'{fullname} (Neon Acct #{acctID}) has a Discourse ID at index {index}')
        # Set the Discourse username at this index to variable to use in PATCH to update Neon
        dID = fullDlist[index]["username"]
        # Check for invalid formatting on responses (found weirdness in Neon)
        if " " in dID:
            print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {index}.')
        elif "|" in dID:
            print(f'WARNING! Discourse username found is not in a valid format. Value: {dID}\nCheck response at index {index}.')
        # Update accounts if formatting errors not detected
        else:
            print(f'Updating DiscourseID to {dID} for Neon account #{acctID} - {fullname}')

            ##### NEON #####
            # Update part of an account
            # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
            httpVerb = 'PATCH'
            resourcePath = f'/accounts/{acctID}'
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
        #couldn't match a DiscourseID for this Neon account
        noDIDlist.append(acct)


print(f'{len(noDIDlist)} accounts in Neon still missing Discourse IDs. Report saved to file as ./Neon/dIDmissing.json for further review.')

# Print to file
with open('./Neon/dIDmissing.json', 'w') as outfile:
    json.dump(noDIDlist, outfile, indent=4)