#!/usr/bin/env python3
################# Asmbly NeonCRM API Integrations ##################
#       Neon API docs - https://developer.neoncrm.com/api-v2/      #
####################################################################
####################################################################
#  This helper script is a work in progress...                     #
####################################################################

# Update this file with the info relevant to your query, 
# then save to it_volunteer_day/requests/ with <yourName>.py, 
# then commit and push


####################################################################
# OPTIONAL
####################################################################

# Desired filename (if unspecified, filename will be output.json)
filename = '<DESIRED_FILENAME>'


####################################################################
# REQUIRED
####################################################################

# Email address to send results to when query is run
email = '<EMAIL_ADDRESS>'


####################################################################
# FOR SEARCHES (POST /events/search || POST /accounts/search)

# Specify query type (event or account)
type = 'EVENT || ACCOUNT'


# SEARCH FIELDS (dict)
searchFields = [
    # {
    #     'field':'Event Category',
    #     'operator':'EQUAL',
    #     'value':'Asmbly Events'
    # },
    # {
    #     'field':'Event Date',
    #     'operator':'GREATER_THAN',
    #     'value':str(date(2024,1,1))
    # }
]


# OUTPUT FIELDS (list)
outputFields = [
    # 'Account ID',
    # 'All Time Membership Enrollment Count',
    # 'First Name',
    # 'Last Name',
    # 'Email 1',
    # 'Membership Term',
    # 'Membership Level',
    # 'Membership Expiration Date',
    # 'Membership Start Date',
    # 'Individual Type',
    # 'Account Current Membership Status',
]



####################################################################
# FOR OTHER ENDPOINTS - See Neon API docs for options

method   = 'GET'
endpoint = 'ENDPOINT_NAME'
params   = 'PARAMS_DICT'
body     = 'BODY_DICT'