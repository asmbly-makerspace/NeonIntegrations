from pprint import pprint
import json
import base64
import datetime
import logging
import traceback

import helpers.neon as neon
from helpers.api import apiCall
from config import N_APIkey, N_APIuser

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type': 'application/json',
             'Authorization': f'Basic {N_signature}'}

today = datetime.date.today()
deltaDays = today - datetime.timedelta(days = 7)

logging.basicConfig(
    format = '%(asctime)s %(levelname)-8s %(message)s',
    level = logging.INFO,
    datefmt= '%Y-%m-%d %H:%H:%S'
)

EVENT_FIELDS = {
    "Specialty Tools": "440",
    "Shaper Origin": "274",
    "Woodshop Safety": "84",
    "Metal Shop Safety": "520",
    "Big Lasers": "86",
    "CNC Router": "435",
    "Stationary Sanders": "675",
    "Metal Lathe": "676",
    "Wood Lathe": "677",
    "MIG Welding": "678",
    "TIG Welding": "679",
    "Small Lasers": "680",
    "Milling": "681",
    "Tormach": "682",
    "Filament": "683",
    "Resin": "684",
    "Sublimation": "685",
    "Vinyl": "686",
}

def toolTestingUpdate(className: str, neonId: int, inputDate: str):
    date = datetime.datetime.strftime(datetime.datetime.strptime(inputDate, '%Y-%m-%d'), '%m/%d/%Y')
    fieldId = None
    for name, id in EVENT_FIELDS.items():
        if name in className:
            fieldId = id
            shortName = name

    acctCustFields = neon.getAccountIndividual(neonId)['individualAccount']['accountCustomFields']

    customIdList = []
    for field in acctCustFields:
        customIdList.append(field['id'])
    if fieldId and fieldId not in customIdList:
        try:
            ##### NEON #####
            # Update part of an account
            # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
            httpVerb = 'PATCH'
            resourcePath = f'/accounts/{neonId}'
            queryParams = ''
            data = f'''
            {{
            "individualAccount": {{
                "accountCustomFields": [
                {{
                    "id": "{fieldId}",
                    "value": "{date}"
                }}
                ]
            }}
            }}
            '''
            url = N_baseURL + resourcePath + queryParams

            patch = apiCall(httpVerb, url, data, N_headers)
            if (patch.status_code == 200):
                logging.info(f"{patch.status_code} SUCCESS!  \n\tAccount ID {neonId} \n\tClass '{shortName}'")
            else:
                logging.error(f"{patch.status_code} FAILED!  \n\tAccount ID {neonId} \n\tClass '{shortName}'")

        except:
            logging.error(f"UPDATE FAILED FOR UNKNOWN REASON!  \n\tAccount ID {neonId} \n\tClass '{shortName}'")
    elif not fieldId:
        logging.info(f'{className} does not have a corresponding custom field')
    else:
        logging.debug(f'Account ID {neonId} already has {shortName} marked')


searchFields = f'''
[
    {{
        "field": "Event End Date",
        "operator": "GREATER_AND_EQUAL",
        "value": "{deltaDays}"
    }},
    {{
        "field": "Event End Date",
        "operator": "LESS_AND_EQUAL",
        "value": "{today}"
    }},
    {{
        "field": "Event Archived",
        "operator": "EQUAL",
        "value": "No"
    }}
]
'''
outputFields = '''
[
    "Event Name", 
    "Event ID",
    "Event End Date"
]
'''
logging.info(f'Starting Tool Testing update for {today}:')

try:
    eventSearch = neon.postEventSearch(searchFields, outputFields)
    if (responseEvents := eventSearch['searchResults']):
        for event in responseEvents:
            eventName = event['Event Name']
            eventId = event['Event ID']
            eventDate = event['Event End Date']
            registrants = neon.getEventRegistrants(eventId)['eventRegistrations']
            if type(registrants) is not type(None): 
                for registrant in registrants:
                    attended = registrant["tickets"][0]["attendees"][0]["markedAttended"]
                    if attended == True:
                        toolTestingUpdate(eventName, registrant['registrantAccountId'], eventDate)
    else:
        logging.info('Event Search contained no results')
except TypeError:
    pass 
except:
    logging.error('Event Search Failed')
    if traceback.format_exc():
        logging.error(traceback.format_exc())



                    
