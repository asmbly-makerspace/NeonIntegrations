################# ATXHS Smartwaiver API Integrations #################
# Smartwaiver API docs - https://api.smartwaiver.com/docs/v4/#api-_ #
####################################################################

import requests
import json
from pprint import pprint


# Request Info
swAPIkey = ''
baseURL = 'https://api.smartwaiver.com'

resourcePath = '/v4/search'
queryParams = '?templateId=5f037d852d421'
firstName = input("First name: ")
lastName = input("Last name: ")
data = ''

# Construct URL 
url = baseURL + resourcePath + queryParams + f'&firstName={firstName}&lastName={lastName}'

# Construct headers
headers = {'Content-Type':'application/json','sw-api-key': swAPIkey}

# Make request
response = requests.get(url, data=data, headers=headers)

# #Print status and body of response
# print ('Response Status:',response.status_code)
# print ('Response Body:',response.content)

responseJSON = json.loads(response.content)

update = false

if responseJSON['search']['count'] > 0:
    print(f'Waiver completed for {firstName} {lastName}')
    update = true
else:
    print(f'ERROR:  Waiver not found for {firstName} {lastName}. Please check spelling and try again.')

# @TODO - Integrate in full script with Neon to update custom account field    