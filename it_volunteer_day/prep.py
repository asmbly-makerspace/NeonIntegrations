#!/usr/bin/env python3
################# Asmbly NeonCRM API Integrations ##################
#       Neon API docs - https://developer.neoncrm.com/api-v2/      #
####################################################################
####################################################################
#  This helper script is a work in progress...                     #
####################################################################

from pprint import pprint
import requests
import json
import base64
import time
from datetime import date, timedelta, datetime

# Ensure project root is on sys.path so project imports work from subfolders
import sys
from pathlib import Path
projectRoot = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(projectRoot))

# Import Neon helper functions in this project for API calls
import helpers.neon as neon

filename = 'getAccountOutputFields_output'

########################################################################
# EVENT QUERY FIELDS

# response = neon.getEventCategories()
# response = neon.getEventSearchFields()
# response = neon.getEventCustomFields()
# response = neon.getEventOutputFields()


########################################################################
# ACCOUNT QUERY FIELDS

# response = neon.getAccountSearchFields()
response = neon.getAccountOutputFields()




########################################################################
# WRITE TO JSON FILE

# Create output directory if it doesn't exist
outdir = Path('./it_volunteer_day/responses')
outdir.mkdir(parents=True, exist_ok=True)

jsonPath = outdir / f'{filename}.json'
with open(jsonPath, 'w') as f:
    json.dump(response, f)