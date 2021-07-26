############### ATXHS Discourse API Integrations #################
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import requests
import json

from config import D_APIkey, D_APIuser
from util import apiCall

### Discourse Account Info
D_baseURL = 'https://yo.atxhs.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}


# Request Info
# Get a list of all active members on Discourse
httpVerb ='GET'
resourcePath = '/admin/users/list/active.json'
data = ''
url = D_baseURL + resourcePath
usersResponse = apiCall(httpVerb, url, data, D_headers)

# # Print to file
# with open('./Discourse/users.json', 'w') as outfile:
#     json.dump(usersResponse, outfile, indent=4)


print(usersResponse[0]["username"])
print(usersResponse[0]["name"])



# # Request Info
# httpVerb ='GET'
# # resourcePath = '/groups/haxor.json' # id 42
# # resourcePath = '/groups/members2B.json' # id 52
# data = ''


# # Request Info
# httpVerb ='PUT'
# resourcePath = '/groups/42/members.json'
# data = {'usernames': 'valerie'}


# # Request Info
# httpVerb ='DELETE'
# resourcePath = '/groups/42/members.json' 
# data = {'username': 'valerie'}


# # Construct URL 
# url = D_baseURL + resourcePath
# usersResponse = apiCall(httpVerb, url, data, D_headers)


# Pretty Print version (Not true json format)
# pp = pprint.PrettyPrinter(stream=open('users.json', 'w'),indent=2)
# pp.pprint(response)

# # Print to file
# with open('../private/groups.json', 'w') as outfile:
#     json.dump(response, outfile, indent=4)