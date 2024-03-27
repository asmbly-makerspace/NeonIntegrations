########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

from curses import use_default_colors
from os import openpty
from pprint import pformat
from base64 import b64encode
import datetime, pytz
import requests
import logging
from pprint import pprint

import neonUtil
import AsmblyMessageFactory
import gmailUtil
from config import O_APIkey, O_APIuser

#OpenPath Group IDs
GROUP_MANAGEMENT = 23174
GROUP_SUBSCRIBERS = 23172
GROUP_COWORKING = 23175
GROUP_STEWARDS = 27683
GROUP_INSTRUCTORS = 96676
GROUP_SHAPER_ORIGIN = 37059
GROUP_DOMINO = 96643


def isManagedGroup(group: int):
    if (group == GROUP_MANAGEMENT or group == GROUP_COWORKING or group == GROUP_SUBSCRIBERS or group == GROUP_COWORKING or
        group == GROUP_STEWARDS or group == GROUP_INSTRUCTORS or group == GROUP_SHAPER_ORIGIN or group == GROUP_DOMINO):
        return True
    return False
    
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

    opUsers = {}

    limit = 500
    offset = 0
    total = 0
    while offset + limit <= total+limit:
        url = O_baseURL + f'/users?sort=identity.lastName&order=asc' + "&limit="+str(limit)+"&offset="+str(offset)
        response = requests.get(url, headers=O_headers)

        if (response.status_code != 200):
            raise ValueError(f'Get {url} returned status code {response.status_code}')

        offset += limit
        logging.debug(pformat(response.json().get("meta")))
        total = int(response.json().get("totalCount"))

        for i in response.json().get("data"):
            opUsers[i["id"]] = i 

    return opUsers

####################################################################
# Get a single OpenPath user by OpenPath ID
####################################################################
def getUser(opId:int):
    url = O_baseURL + f'/users/{opId}'
    response = requests.get(url, headers=O_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    return response.json().get("data")

####################################################################
# Deactivate (ie mark as deleted) an OpenPath user by ID
####################################################################
def deactivateUser(opId:int):
    url = O_baseURL + f'/users/{opId}/status'
    data = '''{"status": "I"}'''
    logging.debug(f'''PUT to {url} {pformat(data)}''')

    response=requests.put(url, data=data, headers=O_headers)
    if (response.status_code != 204):
        raise ValueError(f'Put {url} returned status code {response.status_code}; expected 200')

####################################################################
# ACTUALLY DELETE an OpenPath user by ID
# NOTE that acutally deleted users no longer show up in access logs
# USE WITH EXTREME CAUTION
####################################################################
def reallyActuallyDeleteUser(opId:int):
    logging.warn(f'''ACTUALLY DELETING OpenPath User {opId}! User will no longer show up in logs!''')
    url = O_baseURL + f'/users/{opId}'
    response = requests.delete(url, headers=O_headers)

    #A successful delete call returns 204 "NO DATA"
    if (response.status_code != 204):
        raise ValueError(f'Delete {url} returned status code {response.status_code}')

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
# fetch all credentials for given OpenPath ID
####################################################################
def getCredentialsForId(id:int):
    #this should be a pretty thorough check for sane argument
    assert(int(id) > 0)

    url = O_baseURL + f'''/users/{id}/credentials?offset=0&sort=id&order=asc'''
    response = requests.get(url, headers=O_headers)
    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    return response.json().get("data")

####################################################################
# Delete a single credential
####################################################################
def deleteCredential(userId: int, credentialId: int):
    url = O_baseURL + f'''/users/{userId}/credentials/{credentialId}'''
    response = requests.delete(url, headers=O_headers)
    if (response.status_code != 204):
        raise ValueError(f'Delete {url} returned status code {response.status_code}; expected 204')

####################################################################
# Delete all credentials for given OpenPath ID
####################################################################
def deleteAllCredentialsForId(id:int):
    #this should be a pretty thorough check for sane argument
    assert(int(id) > 0)

    credentials = getCredentialsForId(id)

    for credential in credentials:
        if credential.get("id"):
            logging.info("Deleting credential found in stale OpenPath user")
            deleteCredential(id, credential.get("id"))
        else:
            logging.warning(f'''Malformed credential in stale OpenPath user {neonAccount.get("primaryContact").get("email1")}''')

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
        logger.warning("DryRun in openPathUtil.disableAccount()")

#################################################################################
# Determine authorized OP groups for a Neon account
#################################################################################
def getOpGroups(neonAccount):
    opGroups = set()   #using a set prevents duplicates

    #Board / Leaders / SuperStewards 24x7 access
    if (neonUtil.accountIsType(neonAccount, neonUtil.LEAD_TYPE) or neonUtil.accountIsType(neonAccount, neonUtil.DIRECTOR_TYPE) or neonUtil.accountIsType(neonAccount, neonUtil.SUPER_TYPE)):
        opGroups.add(GROUP_MANAGEMENT)
    elif neonUtil.accountIsType(neonAccount, neonUtil.STAFF_TYPE):
        #non-leader staff have access to all storage during regular hours
        opGroups.add(GROUP_SUBSCRIBERS) #shop
        opGroups.add(GROUP_STEWARDS) #stewards storage
        opGroups.add(GROUP_INSTRUCTORS) #instructor storage
        opGroups.add(GROUP_COWORKING) #coworking

    #Other groups are effectively subsets of overall facility access
    if neonUtil.accountHasFacilityAccess(neonAccount):
        opGroups.add(GROUP_SUBSCRIBERS)
        if neonUtil.accountIsType(neonAccount, neonUtil.COWORKING_TYPE):
            opGroups.add(GROUP_COWORKING)
        if neonUtil.accountIsType(neonAccount, neonUtil.STEWARD_TYPE):
            opGroups.add(GROUP_STEWARDS)
        if neonUtil.accountIsType(neonAccount, neonUtil.INSTRUCTOR_TYPE):
            opGroups.add(GROUP_INSTRUCTORS)
        if neonUtil.accountHasShaperAccess(neonAccount):
            opGroups.add(GROUP_SHAPER_ORIGIN)
        if neonUtil.accountHasDominoAccess(neonAccount):
            opGroups.add(GROUP_DOMINO)

    return list(opGroups)

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

    neonOpGroups = getOpGroups(neonAccount)

    opGroupArray = []
    for group in openPathGroups:
        id = group.get("id")
        if id is not None:
            opGroupArray.append(id)

        #prevent specialty groups from being clobbered
        if not isManagedGroup(id):
            logging.info(f'''{neonAccount.get("fullName")} ({neonAccount.get("Email 1")}) has unmanaged OpenPath Group ID {id}''')
            neonOpGroups.append(id)
    
    logging.debug(f'''Groups for {neonAccount.get("OpenPathID")}: Current {opGroupArray}; New: {neonOpGroups}''')

    #If the OP groups for this Neon account changed, update OP
    if sorted(opGroupArray) != sorted(neonOpGroups):
        #this should be a pretty thorough check for sane argument
        assert(int(neonAccount.get("OpenPathID")) > 0)

        logging.info(f'''Updating OpenPath groups for {neonAccount.get("fullName")} ({neonAccount.get("Email 1")}) {neonOpGroups}''')
        data = f'''
        {{
            "groupIds": {neonOpGroups}
        }}'''

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
            logger.warn("DryRun in openPathUtil.updateGroups()")

    if (email):
        if len(opGroupArray) == 0:
            #account went from no groups to some groups
            gmailUtil.sendMIMEmessage(AsmblyMessageFactory.getOpenPathEnableMessage(neonAccount.get("Email 1"), neonAccount.get("fullName")))

        if len(neonOpGroups) == 0:
            #account went from some groups to no groups
            gmailUtil.sendMIMEmessage(AsmblyMessageFactory.getOpenPathDisableMessage(neonAccount.get("Email 1"), neonAccount.get("fullName")))

        if not neonUtil.accountHasFacilityAccess(neonAccount):
            ##these account types always have factility access even if their term expires.  Note the exception in the log.
            if neonUtil.accountIsType(neonAccount, neonUtil.DIRECTOR_TYPE) or neonUtil.accountIsType(neonAccount, neonUtil.LEAD_TYPE) or neonUtil.accountIsType(neonAccount, neonUtil.SUPER_TYPE):
                logging.warning(f'''I'm not disabling {neonAccount.get("fullName")} ({neonAccount.get("Email 1")}) becuase they're special''')
                #Send an email if we ever get the renewal-bounce problem figured out.


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
    elif neonUtil.accountHasFacilityAccess(account):
        account = createUser(account)
        updateGroups(account, groups=[]) #pass empty groups list to skip the http get
        createMobileCredential(account)
