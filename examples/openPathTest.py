################# Asmbly OpenPath API Integrations ################
# OpenPath API docs - https://openpath.readme.io/docs             #
###################################################################

import requests
from pprint import pprint
from datetime import datetime
import json
import base64

from config import O_APIkey, O_APIuser, N_APIkey, N_APIuser
from util import apiCall

### OpenPath Account Info
O_auth      = f'{O_APIuser}:{O_APIkey}'
#Asmbly is OpenPath org ID 5231
O_baseURL   = 'https://api.openpath.com/orgs/5231'
O_signature = base64.b64encode(bytearray(O_auth.encode())).decode()
O_headers   = {'Authorization': f'Basic {O_signature}', 'Accept': 'application/json', "Content-Type": "application/json"}

### Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}

#dryRun means we do queries but don't write any changes to Neon or OP
dryRun = True

neonFilename = "Neon/memberAccounts.json"

neonAccounts = {}

# ##### NEON ######
#first off, check that we have a Neon account list before spending a bunch of time on the Discourse API
with open(neonFilename) as neonFile:
    neonAccountJson = json.load(neonFile)
    for account in neonAccountJson:
        neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

opExists = 0
opSuspended = 0
opMissingWaiver = 0
opMissingTour = 0
opNotReady = 0
opReady = 0

for account in neonAccounts:
    #manage existing OP accounts
    if neonAccounts[account].get("OpenPathID"):
        #I exist in both OpenPath and Neon 
        #    - TODO update KeyFobID in Neon if necessary.
        #    - TODO Confirm OP ExternalID matches NeonID. 
        #    - TODO update email in OpenPath if necessary. (not sure this can actually be done - OP really likes emails)
        #    - TODO add keyfob credential if one doesn't exist and KeyFobID in Neon is valid (user access is still controlled by group membership)
        opExists += 1

        #get OP groups for user
        exception = False
        subscriber = False
        httpVerb = 'GET'
        resourcePath = f'/users/{neonAccounts[account].get("OpenPathID")}/groups?offset=0&sort=name&order=asc'
        url=url = O_baseURL + resourcePath
        opResponse = apiCall(httpVerb, url, "", O_headers)
        # pprint(opResponse)
        if opResponse.get("data"):
            for group in opResponse.get("data"):
                if group.get("id"):
                    id = group.get("id")
                    #27683 Stewards
                    #23174 Board
                    #23175 CoWorking
                    if (id == 27683 or id == 23174 or id == 23175):
                        exception = True
                        subscriber = True #any of the super-access groups include facility access
                    elif id == 23172:
                        # 23172 Subscribers
                        subscriber = True
                else:
                    #TODO what the hell happens if we can't find the ID for an group?
                    #log WTF?
                    pass

        if (neonAccounts[account].get("validMembership") == True and neonAccounts[account].get("AccessSuspended") != True and
            neonAccounts[account].get("WaiverDate") and neonAccounts[account].get("FacilityTourDate")):
            #I deserve access to the space!
            #check group membership; add subscribers if not present
            if not subscriber:
                print(f'''Re-enabling access for {neonAccounts[account].get("First Name")} {neonAccounts[account].get("Last Name")} ({neonAccounts[account].get("Email 1")})''')
                if not dryRun:
                    httpVerb = 'PUT'
                    resourcePath = f'''/users/{neonAccounts[account].get("OpenPathID")}/groupIds'''

                    data = '''
                    {
                        "groupIds": [23172]
                    }
                    '''

                    url=url = O_baseURL + resourcePath
                    opResponse = apiCall(httpVerb, url, data, O_headers)

            #TODO check for valid credential; provision mobile credential and send activation email if one doesn't exist
            pass

        else:
            #If OP user is not in co-working, stewards, or board groups, remove all group memberships
            #otherwise, send exception email
            if not exception:
                print(f'''Disabling access for {neonAccounts[account].get("First Name")} {neonAccounts[account].get("Last Name")} ({neonAccounts[account].get("Email 1")})''')
                if not dryRun:
                    #don't know if this works!
                    httpVerb = 'PUT'
                    resourcePath = f'''/users/{neonAccounts[account].get("OpenPathID")}/groupIds'''

                    data = '''
                    {
                        "groupIds": []
                    }
                    '''

                    url=url = O_baseURL + resourcePath
                    opResponse = apiCall(httpVerb, url, data, O_headers)
                    pass
            else:
                print (f'''I'm not disabling {neonAccounts[account].get("First Name")} {neonAccounts[account].get("Last Name")} ({neonAccounts[account].get("Email 1")}) becuase they're special''')
                #TODO email or something
    else:
        #I don't exist in OpenPath.  Add an account if I need one
        if (neonAccounts[account].get("validMembership") == True and neonAccounts[account].get("AccessSuspended") != True and
            neonAccounts[account].get("WaiverDate") and neonAccounts[account].get("FacilityTourDate")):
            opReady += 1
            #print(f'Adding OP account for {neonAccounts[account].get("First Name")} {neonAccounts[account].get("Last Name")}')
            #I deserve access to the space!
            ##########################
            #create OP user
            data = f'''
            {{
                "identity": {{
                    "email": "{neonAccounts[account].get("Email 1")}",
                    "firstName": "{neonAccounts[account].get("First Name")}",
                    "lastName": "{neonAccounts[account].get("Last Name")}"
                }},
                "externalId": "{neonAccounts[account].get("Account ID")}",
                "hasRemoteUnlock": false
            }}
            '''
            print(f'Adding OP Account: {data}')

            if not dryRun:
                httpVerb = 'POST'
                resourcePath = '/users'
                url=url = O_baseURL + resourcePath
                opResponse = apiCall(httpVerb, url, data, O_headers)
                #pprint(opResponse)
                if opResponse.get("error"):
                    print(f'''OpenPath Error: {opResponse.get("message")}''')
                elif opResponse.get("data"):
                    opUser = opResponse.get("data")
                    createdTime = datetime.strptime(opUser.get("createdAt"), "%Y-%m-%dT%H:%M:%S.000Z")
                    userAge = datetime.now() - createdTime
                    if userAge.seconds > 3600:
                        #This user was created more than an hour ago, but we didn't fail - that means an OP user with this email address was deleted in the past.
                        #OP archives "deleted" users, and doesn't update their ID fields when re-creating them.  We'll have to do a patch.
                        #TODO make sure no other Neon record has this OpenPathID associated

                        #first, find and delete any existing (stale) credentials
                        httpVerb = 'GET'
                        resourcePath = f'''/users/{opUser.get("id")}/credentials?offset=0&sort=id&order=asc'''
                        url=url = O_baseURL + resourcePath
                        opResponse = apiCall(httpVerb, url, data, O_headers)
                        #pprint(opResponse)
                        if opResponse.get("data"):
                            for credential in opResponse.get("data"):
                                if credential.get("id"):
                                    httpVerb = 'DELETE'
                                    resourcePath = f'''/users/{opUser.get("id")}/credentials/{credential.get("id")}'''
                                    url=url = O_baseURL + resourcePath
                                    opResponse = apiCall(httpVerb, url, data, O_headers)
                                    #no response if successful - we should probably check for an error
                                else:
                                    #TODO what the hell happens if we can't find the ID for an existing credential?
                                    #log WTF?
                                    pass

                        #do a user patch to update the name and metadata
                        #...confirmed that updating FirstName and LastName fixes initials and FullName too
                        httpVerb = 'PATCH'
                        resourcePath = f'''/users/{opUser.get("id")}'''
                        url=url = O_baseURL + resourcePath
                        opResponse = apiCall(httpVerb, url, data, O_headers)
                        #pprint(opResponse)

                        #at this point, we have refreshed the stale OP record as though it were newly created.
                        #carry on the same whether the OP record is new new or a resurrected zombie record.

                    ##### NEON - update user's OPID #####
                    httpVerb = 'PATCH'
                    resourcePath = f'/accounts/{neonAccounts[account].get("Account ID")}'
                    queryParams = '?category=Account'
                    data = f'''
                    {{
                    "individualAccount": {{
                        "accountCustomFields": [
                        {{
                            "id": "178",
                            "name": "OpenPathID",
                            "value": "{opUser.get("id")}"
                        }}
                        ]
                    }}
                    }}
                    '''
                    url = N_baseURL + resourcePath + queryParams
                    patch = apiCall(httpVerb, url, data, N_headers)
                    #pprint(patch)

                    ##########################
                    #add new user to subscribers group
                    print("setting groups")
                    httpVerb = 'PUT'
                    resourcePath = f'''/users/{opUser.get("id")}/groupIds'''

                    data = '''
                    {
                        "groupIds": [23172]
                    }
                    '''

                    url=url = O_baseURL + resourcePath
                    opResponse = apiCall(httpVerb, url, data, O_headers)
                    #pprint(opResponse)

                    # ##########################
                    # #add a new mobile credential
                    print("creating mobile credential")
                    httpVerb = 'POST'
                    resourcePath = f'/users/{opUser.get("id")}/credentials'

                    data = '''
                    {
                        "mobile": {"name": "Automatic Mobile Credential"},
                        "credentialTypeId": 1
                    }
                    '''

                    url=url = O_baseURL + resourcePath
                    opResponse = apiCall(httpVerb, url, data, O_headers)
                    pprint(opResponse)
                    if opResponse.get("data") and opResponse.get("data").get("id"):
                        ##########################
                        #activate mobile credential
                        print("activating mobile credential")
                        httpVerb = 'POST'
                        resourcePath = f'/users/{opUser.get("id")}/credentials/{opResponse.get("data").get("id")}/setupMobile'

                        url=url = O_baseURL + resourcePath
                        opResponse = apiCall(httpVerb, url, '', O_headers)
                        #pprint(opResponse)
                    else:
                        #ERRROR unable to find the ID of the mobile credentiail we just created
                        #log WTF
                        pass

                #if I have a KeyFobID in Neon, add it to OP
                #not sure we want to do this?  Better to copy the other direction?
                #if neonAccounts[account].get("KeyFobID"):
                    #check for multiple KeyFobIDs separated by , or ; 
                    #for each keyfobID... 
                        ##########################
                        #add a new card
                        # httpVerb = 'POST'
                        # resourcePath = f'/users/{userId}/credentials'
                        # facilityCode = str(10) #number before hyphen
                        # cardId = str(1234) #number after hyphen
                        # cardFields = f'''"facilityCode": "{facilityCode}","cardId": "{cardId}"'''
                        # cardHeader = '''
                        # {
                        #   "card": {
                        #     "fields": {
                        # '''
                        # cardFooter = '''
                        #     },
                        #     "cardFormatId": 5150
                        #   },
                        #   "credentialTypeId": 2
                        # }
                        # '''
                        # data = cardHeader + cardFields + cardFooter
                        # url=url = O_baseURL + resourcePath
                        # opResponse = apiCall(httpVerb, url, data, O_headers)
                    #pass
        else:
            if neonAccounts[account].get("validMembership") == True:
                opNotReady += 1
                if neonAccounts[account].get("AccessSuspended") == True:
                    opSuspended += 1
                if not neonAccounts[account].get("WaiverDate"):
                    opMissingWaiver += 1
                if not neonAccounts[account].get("FacilityTourDate"):
                    opMissingTour += 1

print (f"Found {opExists} subscribers in OpenPath, {opReady} subscribers to add and {opNotReady} subscribers not ready yet")
print (f"({opSuspended} suspended; {opMissingTour} missing the tour; {opMissingWaiver} missing the waiver)")

#stage 2 - audit for orphan OP Users
#for account in OpenPathAccounts:
#check for valid externalID
#check that NeonAccounts[externalId][openPathID] matches
#send email for exceptions

##########################
#list defined users
# httpVerb = 'GET'
# resourcePath = '/users'
# queryParams = ''
# print(O_headers)

# data = '''
# {
#     "offset":"0",
#     "sort":"identity.lastName",
#     "order":"asc"
# }
# '''
# url=url = O_baseURL + resourcePath
# opResponse = apiCall(httpVerb, url, data, O_headers)

#TODO check for existing user

##########################

#TODO delete mobile that haven't been provisioned, or re-send provision email
#TODO check for keyfob, add number to Neon







