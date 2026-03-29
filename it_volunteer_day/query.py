#!/usr/bin/env python3
########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################
#################################################################
#  This helper script is a work in progress...                  #
#################################################################

from pprint import pprint
import requests
import json
import base64
import time
from datetime import date, timedelta, datetime

# Ensure project root is on sys.path so project imports work from subfolders
import sys
from pathlib import Path
projectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(projectRoot))

import helpers.neon as neon

filename = 'output'


########################################################################
# EXAMPLE SEARCH FIELDS (dict) - Populate with user's info
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

########################################################################
# EXAMPLE OUTPUT FIELDS (list) - Populate with user's info
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



########################################################################
# QUERIES TO RUN
########################################################################

# GET EVENT/CLASS LIST
response = neon.postEventSearch(searchFields, outputFields)


# GET - ACCOUNT LIST
# response = neon.postAccountSearch(searchFields, outputFields)



########################################################################
# WRITE TO JSON FILE
########################################################################

# Create output directory if it doesn't exist
outdir = Path('./it_volunteer_day/responses')
outdir.mkdir(parents=True, exist_ok=True)

jsonPath = outdir / f'{filename}.json'
with open(jsonPath, 'w') as f:
    json.dump(response, f)


