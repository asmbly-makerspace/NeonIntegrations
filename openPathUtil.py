########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from pprint import pformat
from base64 import b64encode
import datetime, pytz
import requests
import logging

import neonUtil
import AsmblyMessageFactory
import gmailUtil
from config import O_APIkey, O_APIuser

dryRun = False

### OpenPath Account Info
O_auth      = f'{O_APIuser}:{O_APIkey}'
#Asmbly is OpenPath org ID 5231
O_baseURL   = 'https://api.openpath.com/orgs/5231'
O_signature = b64encode(bytearray(O_auth.encode())).decode()
O_headers   = {'Authorization': f'Basic {O_signature}', 'Accept': 'application/json', "Content-Type": "application/json"}

####################################################################
# Get all defined OpenPath users
####################################################################
def getAllUsers():
    ### NOTE this GET has a limit of 1000 users.  If we grow that big, this will be the least of our problems
    url = O_baseURL + f'/users?offset=0&sort=identity.lastName&order=asc'
    response = requests.get(url, headers=O_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    opUsers = {}
    for i in response.json().get("data"):
        opUsers[i["id"]] = i 

    return opUsers

####################################################################
# Given an OpenPath ID, return group membership
####################################################################
def getGroupsById(id):
    if not id:
        return []

    url = O_baseURL + f'/users/{id}/groups'
    response = requests.get(url, headers=O_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    return response.json().get("data")

####################################################################
# Delete all credentials for given OpenPath ID
####################################################################
def deleteAllCredentialsForId(id):
    #this should be a pretty thorough check for sane argument
    assert(int(id) > 0)

    url = O_baseURL + f'''/users/{id}/credentials?offset=0&sort=id&order=asc'''
    response = requests.get(url, headers=O_headers)
    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    for credential in response.json().get("data"):
        if credential.get("id"):
            logging.info("Deleting credential found in stale OpenPath user")
            url = O_baseURL + f'''/users/{id}/credentials/{credential.get("id")}'''
            response = requests.delete(url, headers=O_headers)
            if (response.status_code != 204):
                raise ValueError(f'Delete {url} returned status code {response.status_code}; expected 204')
        else:
            logging.warning(f'''Malformed credential in stale OpenPath user {neonAccount.get("primaryContact").get("email1")}''')


#################################################################################
# Add given openPath user to the subscribers group
#################################################################################
def enableAccount(neonAccount):
    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("OpenPathID")) > 0)

    #TODO make sure user state isn't deleted and credentials exist

    logging.info(f'''Re-enabling OpenPath access for {neonAccount.get("fullName")} ({neonAccount.get("Email 1")})''')
    data = '''
    {
        "groupIds": [23172]
    }'''

    url = O_baseURL + f'''/users/{neonAccount.get("OpenPathID")}/groupIds'''
    logging.debug(f'''PUT to {url} {pformat(data)}''')
    if not dryRun:
        response = requests.put(url, data=data, headers=O_headers)
        if (response.status_code != 204):
            raise ValueError(f'Put {url} returned status code {response.status_code}; expected 204')
        else:
            #todo SEND EMAIL
            pass
    else:
        logger.warn("DryRun in openPathUtil.enableAccount()")

    
#################################################################################
# Remove given openPath user from all groups
#################################################################################
def disableAccount(neonAccount):
    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("OpenPathID")) > 0)

    logging.info(f'''Disabling access for {neonAccount.get("fullName")} ({neonAccount.get("Email 1")})''')
    data = '''
    {
        "groupIds": []
    }'''

    url = O_baseURL + f'''/users/{neonAccount.get("OpenPathID")}/groupIds'''
    logging.debug(f'''PUT to {url} {pformat(data)}''')
    if not dryRun:
        response = requests.put(url, data=data, headers=O_headers)
        if (response.status_code != 204):
            raise ValueError(f'Put {url} returned status code {response.status_code}; expected 204')
        else:
            #todo SEND EMAIL
            pass
    else:
        logger.warn("DryRun in openPathUtil.disableAccount()")

#################################################################################
# Given a Neon account and optionally an OpenPath user, perform necessary updates
#################################################################################
def updateGroups(neonAccount, openPathGroups=None, email=False):
    if not neonAccount.get("OpenPathID"):
        logging.error("No OpenPathID found to update groups")
        return

    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("OpenPathID")) > 0)

    if openPathGroups is None:
        openPathGroups = getGroupsById(neonAccount.get("OpenPathID"))

    logging.debug(f'''OP Groups for {neonAccount.get("OpenPathID")}: {openPathGroups}''')

    OPexception = False
    OPsubscriber = False

    for group in openPathGroups:
        if group.get("id"):
            id = group.get("id")
            #27683 Stewards
            #23174 Board
            #23175 CoWorking
            if (id == 23174 or id == 23175):
                OPexception = True
                OPsubscriber = True #any of the super-access groups include facility access
            elif id == 23172:
                # 23172 Subscribers
                OPsubscriber = True
        else:
            #TODO what the hell happens if we can't find the ID for an group?
            #log WTF?
            pass

    if neonUtil.accountHasFacilityAccess(neonAccount):
        if not OPsubscriber:
            enableAccount(neonAccount)
            if (email):
                gmailUtil.sendMIMEmessage(AsmblyMessageFactory.getOpenPathEnableMessage(neonAccount.get("Email 1"), neonAccount.get("fullName")))
    elif OPsubscriber:
        #If OP user is not in co-working, stewards, or board groups, remove all group memberships
        if not OPexception:
            if (email):
                gmailUtil.sendMIMEmessage(AsmblyMessageFactory.getOpenPathDisableMessage(neonAccount.get("Email 1"), neonAccount.get("fullName")))
            disableAccount(neonAccount)
        else:
            logging.warning(f'''I'm not disabling {neonAccount.get("fullName")} ({neonAccount.get("Email 1")}) becuase they're special''')
            #TODO email or something


#################################################################################
# Create OpenPath user for given Neon account if it doesn't exist
#################################################################################
def createUser(neonAccount):
    logging.info(f'Adding OP account for {neonAccount.get("fullName")}')

    data = f'''
    {{
        "identity": {{
            "email": "{neonAccount.get("Email 1")}",
            "firstName": "{neonAccount.get("First Name")}",
            "lastName": "{neonAccount.get("Last Name")}"
        }},
        "externalId": "{neonAccount.get("Account ID")}",
        "hasRemoteUnlock": false
    }}'''
    url = O_baseURL + '/users'
    logging.debug(f'''POST to {url} {pformat(data)}''')
    if not dryRun:
        response = requests.post(url, data=data, headers=O_headers)
        if (response.status_code != 201):
            logging.error(f'''Status {response.status_code} (expected 201) creating OpenPath User {pformat(data)} ''')
            return neonAccount

        #openPath times are in UTC
        opUser = response.json().get("data")
        createdTime = datetime.datetime.strptime(opUser.get("createdAt"), "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=datetime.timezone.utc)
        userAge = datetime.datetime.now(pytz.timezone("America/Chicago")) - createdTime
        if userAge.seconds > 300:
            logging.warning(f'''Found an existing OpenPath user created at {opUser.get("createdAt")} for {neonAccount.get("Email 1")} when updating Neon account {neonAccount.get("Account ID")}''')
            #This user was created more than 5mins ago, but we didn't fail - that means an OP user with this email address was deleted in the past.
            #OP archives "deleted" users, and doesn't update their ID fields when re-creating them.  We'll have to do a patch.
            #TODO make sure no other Neon record has this OpenPathID associated

            #first, find and delete any existing (stale) credentials
            deleteAllCredentialsForId(opUser.get("id"))

            #do a user patch to update the name and metadata
            #...confirmed that updating FirstName and LastName fixes initials and FullName too
            httpVerb = 'PATCH'
            url = O_baseURL + f'''/users/{opUser.get("id")}'''
            logging.debug(f'''PATCH to {url} {pformat(data)}''')
            response=requests.patch(url, data=data, headers=O_headers)
            if (response.status_code != 200):
                raise ValueError(f'Patch {url} returned status code {response.status_code}; expected 200')

            #at this point, we have refreshed the stale OP record as though it were newly created.
            #carry on the same whether the OP record is new new or a resurrected zombie record.

        #Update our local copy of the account so we don't have to fetch again
        neonAccount["OpenPathID"]=opUser.get("id")
        neonUtil.updateOpenPathID(neonAccount)
    else:
        logger.warn("DryRun in openPathUtil.createUser()")

    return neonAccount

#################################################################################
# Create and Activate OpenPath mobile credential for given Neon account
#################################################################################
def createMobileCredential(neonAccount):
    if not neonAccount.get("OpenPathID"):
        logging.error("No OpenPathID found to create mobile credential")
        return
    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("OpenPathID")) > 0)

    logging.info(f'Creating OP Mobile Credential for {neonAccount.get("fullName")} (OP ID {neonAccount.get("OpenPathID")})')

    data = '''
    {
        "mobile": {"name": "Automatic Mobile Credential"},
        "credentialTypeId": 1
    }
    '''
    url = O_baseURL + f'/users/{neonAccount.get("OpenPathID")}/credentials'
    logging.debug(f'''POST to {url} {pformat(data)}''')
    if not dryRun:
        response = requests.post(url, data=data, headers=O_headers)
        if (response.status_code != 201):
            raise ValueError(f'Post {url} returned status code {response.status_code}; expected 201')

        if response.json().get("data") and response.json().get("data").get("id"):
            logging.info(f'Activating OP Mobile Credential for {neonAccount.get("fullName")} (OP ID {neonAccount.get("OpenPathID")})')
            httpVerb = 'POST'
            url = O_baseURL + f'/users/{neonAccount.get("OpenPathID")}/credentials/{response.json().get("data").get("id")}/setupMobile'
            logging.debug(f'''POST to {url}''')
            response = requests.post(url, headers=O_headers)
            if (response.status_code != 204):
                raise ValueError(f'Post {url} returned status code {response.status_code}; expected 204')
        else:
            logging.error("Created a mobile credential but unable to find ID")
    else:
        logger.warn("DryRun in openPathUtil.createMobileCredential()")

#################################################################################
# Given a single Neon ID, perform necessary OpenPath updates
#################################################################################
def updateOpenPathByNeonId(neonId):
    logging.info(f"Updating Neon ID {neonId}")
    account = neonUtil.getMemberById(neonId)
    #logging.debug(account)
    if account.get("OpenPathID"):
        updateGroups(account, email=True)
    elif accountHasFacilityAccess(account):
        account = createUser(account)
        updateGroups(account, groups=[]) #pass empty groups list to skip the http get
        createMobileCredential(account)
