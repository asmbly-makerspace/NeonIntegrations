########### ATXHS NeonCRM API Integrations ############
# Neon API docs - https://developer.neoncrm.com/api/ #
#####################################################

import requests
import json
from pprint import pprint


# Request Info
neonApiKey = ''
baseURL = 'https://api.neoncrm.com/neonws/services/api'
# Neon API does not appear to use headers or support different HTTP methods like PUT or POST
# headers and data should be left as empty strings for this API
headers = ''
data = ''


# Log in to get userSessionId for all subsequent API calls
# https://developer.neoncrm.com/api/getting-started/login/
resourcePath = '/common/login'
queryParams = f'?login.apiKey={neonApiKey}&login.orgid=atxhs'

loginURL = baseURL + resourcePath + queryParams
response = requests.get(loginURL, data=data, headers=headers)

# # Print status and body of response
# print ('Response Status:',response.status_code)
# print ('Response Body:',response.content)

responseJSON = json.loads(response.content)

userSessionId = responseJSON['loginResponse']['userSessionId']


# Get list of custom fields for update
# https://developer.neoncrm.com/api/list-custom-fields/
resourcePath = '/common/listCustomFields'
queryParams = f'?userSessionId={userSessionId}&searchCriteria.component=Account'

customFieldURL = baseURL + resourcePath + queryParams
response = requests.get(customFieldURL, data=data, headers=headers)

# # Print status and body of response
# print ('Response Status:',response.status_code)
# print ('Response Body:',response.content)

CFresponseJSON = json.loads(response.content)
# pprint(CFresponseJSON)

# Response for WaiverCompleted custom field:
# {'component': 'ACCOUNT',
#  'dataType': 'RADIO',
#  'fieldId': 120,
#  'fieldName': 'WaiverCompleted',
#  'fieldOptions': {'fieldOption': [{'id': '30',
#                                    'name': 'Yes'},
#                                   {'id': '31',
#                                    'name': 'No'}]}}


##### WARNING - This API does not support HTTP PUT for making updates.
##### Any API calls that make "updates" are more accurately described as overwrites.
# To update an individual account, you must first get full account info.
# All info must be passed back as parameters in order to prevent overwriting fields to blank entries
# https://developer.neoncrm.com/api/accounts/retrieve-individual-account/
resourcePath = '/account/listAccountsByKeywordSearch'
queryParams = f'?userSessionId={userSessionId}&userType=Individual&keyword=valerie wilmot'
# Note:  keyword values passed can contain spaces as shown in this example

acctSearchURL = baseURL + resourcePath + queryParams
response = requests.get(acctSearchURL, data=data, headers=headers)

# # Print status and body of response
# print ('Response Status:',response.status_code)
# print ('Response Body:',response.content)

# Convert to JSON object and assign acctId from response
acctsResponseJSON = json.loads(response.content)
acctId = acctsResponseJSON['listAccountsByKeywordSearchResponse']['accountSearchResults']['accountSearchResult'][0]['accountId']



##### WARNING - This API does not support HTTP PUT for making updates.
##### Any API calls that make "updates" are more accurately described as overwrites.
# To update an individual account, you must first get full account info.
# All info must be passed back as parameters in order to prevent overwriting fields to blank entries
# https://developer.neoncrm.com/api/accounts/retrieve-individual-account/
resourcePath = '/account/retrieveIndividualAccount'
queryParams = f'?userSessionId={userSessionId}&accountId={acctId}'

acctInfoURL = baseURL + resourcePath + queryParams
response = requests.get(acctInfoURL, data=data, headers=headers)


acctInfoResponseJSON = json.loads(response.content)
acctInfoResponseJSON = acctInfoResponseJSON['retrieveIndividualAccountResponse']
# pprint(acctInfoResponseJSON)


# @TODO - Need to loop through data returned and build parameters for update to include all fields that are not empty


# individualAccount.customFieldDataList.customFieldData.fieldId	 	    # Retrieve possible account custom fields from the List Custom Fields request.
# individualAccount.customFieldDataList.customFieldData.fieldOptionId	# Required if the custom field type is not a text field. Possible values can be retrieved from the List Custom Fields request.
# individualAccount.customFieldDataList.customFieldData.fieldValue	 	# Required if the custom field type is a text field.

# fieldId = ['individualAccount']['customFieldDataList']['customFieldData']['fieldId']
# fieldValue = ['individualAccount']['customFieldDataList']['customFieldData']['fieldValue']
# fieldOptionId = ['individualAccount']['customFieldDataList']['customFieldData']['fieldOptionId']

contactId = acctInfoResponseJSON['individualAccount']['primaryContact']['contactId']
firstName = acctInfoResponseJSON['individualAccount']['primaryContact']['firstName']
lastName = acctInfoResponseJSON['individualAccount']['primaryContact']['lastName']

# To update WaiverCompleted to Yes
fieldId = 120
fieldOptionId = 30


##### WARNING - This API does not support HTTP PUT for making updates.
##### Any API calls that make "updates" are more accurately described as overwrites.
# To update an individual account, you must first get full account info.
# All info must be passed back as parameters in order to prevent overwriting fields to blank entries
# https://developer.neoncrm.com/api/accounts/update-individual-account/
resourcePath = '/account/updateIndividualAccount'
queryParams = f'?userSessionId={userSessionId}&individualAccount.accountId={acctId}&individualAccount.primaryContact.contactId={contactId}&individualAccount.primaryContact.firstName={firstName}&individualAccount.primaryContact.lastName={lastName}&individualAccount.customFieldDataList.customFieldData.fieldId={fieldId}&individualAccount.customFieldDataList.customFieldData.fieldOptionId={fieldOptionId}'

acctUpdateURL = baseURL + resourcePath + queryParams
##### Warning - This API call can be destructive.
##### Make sure you are passing all info previously retrieved before uncommenting and running the next line. 
# response = requests.get(acctUpdateURL, data=data, headers=headers)