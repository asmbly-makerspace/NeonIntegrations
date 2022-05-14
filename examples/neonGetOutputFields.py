########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from pprint import pprint
import base64

from config import N_APIkey, N_APIuser
from util import apiCall

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}


##### NEON #####
# Get list of custom fields for events
# httpVerb = 'GET'
# resourcePath = '/customFields'
# queryParams = '?category=Account'
# data = ''
# url = N_baseURL + resourcePath + queryParams
# response = apiCall(httpVerb, url, data, N_headers)
# print("### CUSTOM FIELDS ###\n")
# pprint(response)

##### NEON #####
# Get possible output fields for POST to /accounts/search
httpVerb = 'GET'
resourcePath = '/accounts/search/outputFields'
queryParams = ''
data = ''
url = N_baseURL + resourcePath + queryParams
response = apiCall(httpVerb, url, data, N_headers)
print("### OUTPUT FIELDS ###\n")
pprint(response)
