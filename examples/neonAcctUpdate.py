################# ATXHS NeonCRM API Integrations ##################
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from pprint import pprint
import requests
import json
import base64

from config import N_APIkey, N_APIuser
from util import apiCall

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}


##### NEON #####
# Update part of an account
# https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
httpVerb = 'PATCH'
resourcePath = f'/accounts/14'
queryParams = '?category=Account'
data = '''
{
  "individualAccount": {
    "accountCustomFields": [
      {
        "id": "120",
        "name": "WaiverCompleted",
        "optionValues": [
          {
            "id": "30",
            "name": "Yes",
            "status": "ACTIVE"
          }
        ]
      }
    ]
  }
}
'''
url = N_baseURL + resourcePath + queryParams
patch = apiCall(httpVerb, url, data, N_headers)