############### ATXHS Discourse API Integrations #################
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import requests
import json

from config import D_APIkey, D_APIuser


### Discourse Account Info
D_baseURL = 'https://yo.asmbly.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}


### Helper function for API calls
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
    # pprint(response)

    return response


# # Request Info
# # Get a list of all active members on Discourse
# httpVerb ='GET'
# resourcePath = '/admin/users/list/active.json'
# data = ''
# url = D_baseURL + resourcePath
# usersResponse = apiCall(httpVerb, url, data, D_headers)

# # # Print to file
# # with open('./Discourse/users.json', 'w') as outfile:
# #     json.dump(usersResponse, outfile, indent=4)


# print(usersResponse[0]["username"])
# print(usersResponse[0]["name"])



# # Request Info
# httpVerb ='GET'
# resourcePath = '/groups/haxor.json' # id 42
# # resourcePath = '/groups/members2B.json' # id 52
# data = ''


# # Request Info
# httpVerb ='PUT'
# resourcePath = '/groups/42/members.json'
# data = {'usernames': 'Cuca'}
# # usernames should be listed as a single string with commas separating them


# # Request Info
# httpVerb ='DELETE'
# resourcePath = '/groups/42/members.json' 
# data = {'username': 'valerie'}


# # Construct URL 
# url = D_baseURL + resourcePath
# usersResponse = apiCall(httpVerb, url, data, D_headers)
# pprint(usersResponse)


# # Pretty Print version (Not true json format)
# pp = pprint.PrettyPrinter(stream=open('users.json', 'w'),indent=2)
# pp.pprint(response)

# # Print to file
# with open('../private/groups.json', 'w') as outfile:
#     json.dump(response, outfile, indent=4)