################## Asmbly Neon API Integrations ###################
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

import csv
import base64

from config import N_APIkey, N_APIuser
from helpers.api import apiCall

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}


# Import all data and read into memory
neonFilename   = "./misc/privateAllNeon.csv"
classFilename  = "./misc/privateClass.csv"
skeddaFilename = "./misc/privateSkedda.csv"

# Read in Neon Data as a dictionary of dictionaries with email as the outer lookup key
neonData = {}
with open(neonFilename) as neonFile:
    for line in csv.reader(neonFile):
        keyEmail = line[0].lower()
        valueDict = {
            "acctID" : line[2], 
            "fullname" : line[1].lower()
        }
        neonData[keyEmail] = valueDict

# Read in Class Data as a dictionary with email as the lookup key
classData = {}
with open(classFilename) as classFile:
    for line in csv.reader(classFile):
        classData[line[1].lower()] = line[0].lower()

# Read Skedda Data in as a list of emails
skeddaData = []
with open(skeddaFilename) as skeddaFile:
    for line in csv.reader(skeddaFile):
        skeddaData.append(line[0].lower())


# As we build out our list of accounts to update, store info about emails we can't associate with a Neon account
unknownEmail = []

print("Building list of accounts approved for recertification...")
# Build the list of Neon account IDs that are approved for recertification (must have booked CNC over last year)
recertApproved = []
for skeddaEmail in skeddaData:
    try:
        acctID = neonData[f"{skeddaEmail}"]["acctID"]
        recertApproved.append(acctID)
    except:
        print(f"\tERROR! No Neon account found for {skeddaEmail}")
        unknownEmail.append(skeddaEmail)
print()

print("Building list of accounts approved for refresher...")
# Build the list of Neon account IDs that are approved for refresher (must have taken a CNC class via Neon)
refreshApproved = []
for classEmail in classData:
    try:
        acctID = neonData[f"{classEmail}"]["acctID"]
        refreshApproved.append(acctID)
    except:
        print(f"\tERROR! No Neon account found for {classEmail}")
        unknownEmail.append(classEmail)
print()


# Store info about any API updates that fail
failed = []

# Update Recertification flag in Neon accounts
for id in recertApproved:
    try:
        ##### NEON #####
        # Update part of an account
        # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
        httpVerb = 'PATCH'
        resourcePath = f'/accounts/{id}'
        queryParams = ''
        data = f'''
        {{
        "individualAccount": {{
            "accountCustomFields": [
            {{
                "id": "437",
                "name": "CNC_Recertification",
                "value": "Approved",
                "status": "ACTIVE"
            }}
            ]
        }}
        }}
        '''
        url = N_baseURL + resourcePath + queryParams
        patch = apiCall(httpVerb, url, data, N_headers)
        print(f"{patch.status_code} SUCCESS!  Account ID {id}")
        if (patch.status_code != 200):
            print(f"\t{patch.status_code} FAILED!  Account ID {id}")
            failed.append(id)

        # Update Refresher field for anyone that qualifies for recertification
        # Recert is more restrictive than refresh; no one should have recert and not refresh
        httpVerb = 'PATCH'
        resourcePath = f'/accounts/{id}'
        queryParams = ''
        data = f'''
        {{
        "individualAccount": {{
            "accountCustomFields": [
            {{
                "id": "438",
                "name": "CNC_Refresher",
                "value": "Approved",
                "status": "ACTIVE"
            }}
            ]
        }}
        }}
        '''
        url = N_baseURL + resourcePath + queryParams
        patch = apiCall(httpVerb, url, data, N_headers)
        print(f"{patch.status_code} SUCCESS!  Account ID {id}")
        if (patch.status_code != 200):
            print(f"\t{patch.status_code} FAILED!  Account ID {id}")
            failed.append(id)
    except:
        print(f"\tUPDATE FAILED!  Account ID {id}")
        failed.append(id)


# Update Refresher flag in Neon accounts
for id in refreshApproved:
    try:
        ##### NEON #####
        # Update part of an account
        # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
        httpVerb = 'PATCH'
        resourcePath = f'/accounts/{id}'
        queryParams = ''
        data = f'''
        {{
        "individualAccount": {{
            "accountCustomFields": [
            {{
                "id": "438",
                "name": "CNC_Refresher",
                "value": "Approved",
                "status": "ACTIVE"
            }}
            ]
        }}
        }}
        '''
        url = N_baseURL + resourcePath + queryParams
        patch = apiCall(httpVerb, url, data, N_headers)
        print(f"{patch.status_code} SUCCESS!  Account ID {id}")
        if (patch.status_code != 200):
            print(f"\t{patch.status_code} FAILED!  Account ID {id}")
            failed.append(id)
    except:
        print(f"\tUPDATE FAILED!  Account ID {id}")
        failed.append(id)


# End script with items to follow up
print()
print()
print(f"The following emails were not found in Neon: ", end="\n\t")
print(*unknownEmail, sep="\n\t")
print()
print(f"The following accounts could not be updated: ", end="\n\t")
print(*failed, sep="\n\t")