import json
import base64

from helpers.config import N_APIkey, N_APIuser
from helpers.api import apiCall

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type': 'application/json',
             'Authorization': f'Basic {N_signature}'}

CLASS_ID = '39102'

httpVerb = 'POST'
url = N_baseURL + f'''/events/{CLASS_ID}/tickets'''

with open('LeatherClassTicketInfo.json', encoding="utf-8") as f:
        ticketInfo = json.load(f)

for ticket in ticketInfo:
    data = json.dumps(ticket)
    response = apiCall(httpVerb, url, data, N_headers)