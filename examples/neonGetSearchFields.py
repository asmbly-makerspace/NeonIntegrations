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
# Get possible search fields for POST to /accounts/search
httpVerb = 'GET'
resourcePath = '/accounts/search/searchFields'
queryParams = ''
data = ''
url = N_baseURL + resourcePath + queryParams
response = apiCall(httpVerb, url, data, N_headers)
print("### SEARCH FIELDS ###\n")
pprint(response)
