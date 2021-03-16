########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import requests
import json
import base64

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
    ## Uncomment the following line to see the full response
    # pprint(response)

    return response

## Helper function to find the index of a list based on specified key and value
def findI(list, key, value):
    for i, dict in enumerate(list):
        if dict[key] == value:
            return i
    return -1


##### DISCOURSE #####
# Get a list of all active users on Discourse
httpVerb ='GET'
resourcePath = '/admin/users/list/active.json'
data = ''
url = D_baseURL + resourcePath
memberResponse = apiCall(httpVerb, url, data, D_headers)

# Assign variable to hold full response starting with a value from the first call
fullDlist = memberResponse
print(f'{len(fullDlist)} active users retrieved from Discourse. Querying for more data...')

# Set page variable to start at 2 and increment with each call
# This is used as an additional parameter in subsequent calls 
page = 2
# Response is limited to a max of 100 entries, if the response returns 100, keep trying to get more data
while len(memberResponse) == 100:
    newPath = f'{resourcePath}?page={page}'
    url = D_baseURL + newPath
    memberResponse = apiCall(httpVerb, url, data, D_headers)
    print(f'Getting page {page}...')
    fullDlist = fullDlist + memberResponse
    print(f'{len(fullDlist)} users collected.')
    page += 1

# Print to file
with open('./Discourse/usersFull.json', 'w') as outfile:
    json.dump(fullDlist, outfile, indent=4)

print(f'{len(fullDlist)} active users on Discourse. Records saved to file as ./Discourse/usersFull.json')

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
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = '''
{
    "searchFields": [
        {
            "field": "DiscourseID",
            "operator": "BLANK",
            "value": ""
        }
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        83,
        85
    ],
    "pagination": {
    "currentPage": 0,
    "pageSize": 200
    }
}
'''
# outputFiels 83 = KeyAccess, 85 = DiscourseID
### Custom field info about DiscourseID
# {'component': 'Account',
#   'constituentReadOnly': False,
#   'dataType': 'Text',
#   'displayType': 'OneLineText',
#   'groupId': '3',
#   'id': '85',
#   'name': 'DiscourseID',
#   'status': 'ACTIVE'}
url = N_baseURL + resourcePath + queryParams
dIDmissingResponse = apiCall(httpVerb, url, data, N_headers)
print(f'{len(dIDmissingResponse["searchResults"])} accounts in Neon missing Discourse IDs. Checking user list from Discourse to update accounts in Neon...')


# Loop through response from Neon and update accounts where there is a matching name in Discourse
for acct in dIDmissingResponse["searchResults"]:
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


# Second check for accounts without DiscourseID
# See what's left after update
##### NEON #####
# Get accounts where custom field DiscourseID is blank
# members without DiscourseID saved in their account
httpVerb = 'POST'
resourcePath = '/accounts/search'
queryParams = ''
data = '''
{
    "searchFields": [
        {
            "field": "DiscourseID",
            "operator": "BLANK",
            "value": ""
        }
    ],
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        83,
        85
    ],
    "pagination": {
    "currentPage": 0,
    "pageSize": 200
    }
}
'''
# outputFiels 83 = KeyAccess, 85 = DiscourseID
### Custom field info about DiscourseID
# {'component': 'Account',
#   'constituentReadOnly': False,
#   'dataType': 'Text',
#   'displayType': 'OneLineText',
#   'groupId': '3',
#   'id': '85',
#   'name': 'DiscourseID',
#   'status': 'ACTIVE'}
url = N_baseURL + resourcePath + queryParams
dIDmissingResponse = apiCall(httpVerb, url, data, N_headers)

print(f'{len(dIDmissingResponse["searchResults"])} accounts in Neon still missing Discourse IDs. Report saved to file as ./Neon/dIDmissing.json for further review.')

# Print to file
with open('./Neon/dIDmissing.json', 'w') as outfile:
    json.dump(fullDlist, outfile, indent=4)