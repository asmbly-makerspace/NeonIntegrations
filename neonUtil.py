############### Asmbly NeonCRM API Integrations ##################
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
##################################################################

from pprint import pformat, pprint
import base64
import datetime, pytz
import requests
import logging

#I'm not absolutely certain NeonCRM thinks it's in central time, but it's in the ballpark.
#pacific time might be slightly more accurate.  Maybe I'll ask their support.
today = datetime.datetime.now(pytz.timezone("America/Chicago")).date()
yesterday = today - datetime.timedelta(days=1)

from config import N_APIkey, N_APIuser

dryRun = False

# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}

#Strings relevant to Neon account management
STAFF_TYPE = "Paid Staff"
LEADER_TYPE = "Leader"
SUPER_TYPE = "Super Steward"
COWORKING_TYPE = "CoWorking Tenant"
STEWARD_TYPE = "Steward"
INSTRUCTOR_TYPE = "Instructor"
FRESHBOOKS_TYPE = "FreshBooks Member"
WIKI_ADMIN_TYPE = "Wiki Admin"

####################################################################
# Update the OpenPathID stored in Neon for an account
####################################################################
def updateOpenPathID(account: dict):
    #this should be a pretty thorough check for sane argument
    assert(int(account.get("Account ID")) > 0)
    assert(int(account.get("OpenPathID")) > 0)

    data = f'''
{{
"individualAccount": {{
    "accountCustomFields": [
    {{
        "id": "178",
        "name": "OpenPathID",
        "value": "{account.get("OpenPathID")}"
    }}
    ]
}}
}}
'''
    url = N_baseURL + f'/accounts/{account.get("Account ID")}' + '?category=Account'
    if not dryRun:
        response = requests.patch(url, data=data, headers=N_headers)
        if (response.status_code != 200):
            raise ValueError(f'Patch {url} returned status code {response.status_code}')
    else:
        logging.warn("DryRun in neonUtil.updateOpenPathID()")

####################################################################
# Update the DiscourseID stored in Neon for an account
####################################################################
def updateDID(account: dict):
    assert(int(account.get("Account ID")) > 0)
    assert(account.get("DiscourseID") is not None)

    data = f'''
{{
"individualAccount": {{
    "accountCustomFields": [
    {{
        "id": "85",
        "name": "DiscourseID",
        "value": "{account.get("DiscourseID")}"
    }}
    ]
}}
}}
'''
    url = N_baseURL + f'/accounts/{account.get("Account ID")}' + '?category=Account'
    if not dryRun:
        response = requests.patch(url, data=data, headers=N_headers)
        if (response.status_code != 200):
            raise ValueError(f'Patch {url} returned status code {response.status_code}')
    else:
        logging.warn("DryRun in neonUtil.updateDID()")


####################################################################
# Update a valid Neon account to include membership information
####################################################################
def appendMemberships(account: dict, detailed=False):
    #this should be a pretty thorough check for sane argument
    assert(int(account.get("Account ID")) > 0)

    #Neon counts a failed renewal as a valid subscription so long as automatic renewal is enabled.
    #WE only think a subscription is valid if the payment transaction was successful, so check payment status.
    url = N_baseURL + f'/accounts/{account.get("Account ID")}/memberships'
    response = requests.get(url, headers=N_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    #logging.debug(pformat(response.json()))

    account["validMembership"] = False

    memberships = response.json().get("memberships")

    if len(memberships) > 0:
        ### end date of the most recent active membership (initialize to ancient history)
        lastActiveMembershipExpiration = datetime.date(1970, 1, 1)
        ##start date of earliest membership (initialize to today)
        firstActiveMembershipStart = today
        ##flag indicating the account has at least one active membership
        atLeastOneActiveMembership = False
        ##flag indicating the current membership has hard-failed (denied/cancelled/refunded)
        currentMembershipStatus = "No Record"

        for membership in memberships:
            membershipExpiration = datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date()
            membershipStart = datetime.datetime.strptime(membership["termStartDate"], '%Y-%m-%d').date()

            logging.debug(f'''Membership ending {membershipExpiration} status {membership["status"]} autorenewal is {membership["autoRenewal"]} ''')

            if membershipExpiration >= today and membershipStart <= today:
                currentMembershipStatus = membership["status"]

            ### If this membership *was* actually paid for (or comped):
            if membership["status"] == "SUCCEEDED":
                ### flag this account as having at least once been active.
                atLeastOneActiveMembership = True

                ### If this active membership is later than the latest we know about, remember its end date
                if membershipExpiration > lastActiveMembershipExpiration:
                    lastActiveMembershipExpiration = membershipExpiration

                    #in my testing membership[autoRenewal] is the same value for all memberships and
                    #reflects the current Neon setting.  It seems safest to keep the latest successful
                    #value, but we should probably spot-check this from time to time
                    account["autoRenewal"] = membership["autoRenewal"]

                ### If this active membership is the earliest one we know about, remember the start date
                if membershipStart < firstActiveMembershipStart:
                    firstActiveMembershipStart = membershipStart

                ### If today is during this active membership, mark the account as valid (should probably be called "active" but well...)
                if membershipExpiration >= today and membershipStart <= today:
                    account["validMembership"] = True
                    if membership.get("fee") == 0:
                        account["comped"] = True

        #!!! NOTE no promise that membership was continuous between these two dates !!!
        if atLeastOneActiveMembership:
            account["Membership Start Date"] = str(firstActiveMembershipStart)
            account["Membership Expiration Date"] = str(lastActiveMembershipExpiration)

        if not account["validMembership"] and lastActiveMembershipExpiration == yesterday:
            logging.info(f'''Neon {account.get("Account ID")} expired yesterday. autoRenewal = {account["autoRenewal"]}, current membership status = {currentMembershipStatus}''')

        if (detailed):
            account["MembershipDetails"] = memberships

    #logging.debug(pformat(account))

    return account

####################################################################
# Given a Neon member ID, return an account including membership info
####################################################################
def getMemberById(id: int, detailed = False):
    url = N_baseURL + f'/accounts/{id}'
    response = requests.get(url, headers=N_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    account = response.json().get("individualAccount")
    logging.debug(pformat(account))

    if account.get('accountCustomFields'):
        #raise custom fields to top-level so they're easier to reach by calling functions
        for field in account.pop('accountCustomFields'):
            if field.get("value"):
                account[field.get("name")] = field.get("value")
            elif field.get("optionValues"):
                if field.get("optionValues")[0].get("name"):
                    account[field.get("name")] = field.get("optionValues")[0].get("name")
                else:
                    raise ValueError(f'Unexpected value format for Neon custom field {field.get("name")}')
            else:
                raise ValueError(f'''Can't find value for Neon custom field {field.get("name")}''')

    #copy primary contact info to match search results format
    account["fullName"] = f'''{account.get("primaryContact").get("firstName")} {account.get("primaryContact").get("lastName")}'''
    account["Email 1"] = account.get("primaryContact").get("email1")
    account["First Name"] = account.get("primaryContact").get("firstName")
    account["Last Name"] = account.get("primaryContact").get("lastName")
    account["Account ID"] = account.get("accountId")

    #This only contains basic account info.  We have to fetch the membership data separately
    account = appendMemberships(account, detailed=detailed)
    return account

####################################################################
# *Annoyingly* a search returns types in a different format than a fetch
# Our scripts expect the fetch format, so do translation here
####################################################################
def fixTypes(account: dict):
    if account.get("Individual Type"):
        typeDictList = []
        typelist = account.get("Individual Type").split('|')
        for type in typelist:
            typeDictList.append({'name' : type.strip()})
        account["individualTypes"] = typeDictList
    return account

####################################################################
# Get Neon accounts matching given criteria
####################################################################
def getNeonAccounts(searchFields, neonAccountDict = {}):
    #Output Fields
    #85 is DiscourseId
    #77 is OrientationDate
    #179 is WaiverDate
    #88 is KeyCardID
    #178 is OpenPathID
    #180 is AccessSuspended
    #274 is ShaperOrigin Date
    #440 is Domino date

    # Neon does pagination as a data parameter, so need to update data for each page
    page = 0
    while True:
        data = f'''
{{
    "searchFields": {searchFields},
    "outputFields": [
        "First Name", 
        "Last Name",
        "Preferred Name",
        "Account ID",
        "Email 1",
        "Email 2",
        "Email 3",
        "Membership Expiration Date",
        "Membership Start Date",
        "Individual Type",
        85, 77, 179, 178, 88, 180, 182, 274, 440
    ],
    "pagination": {{
    "currentPage": {page},
    "pageSize": 200
    }}
}}
'''
        url = N_baseURL + '/accounts/search'
        response = requests.post(url, data=data, headers=N_headers)

        if (response.status_code != 200):
            raise ValueError(f'Post {url} returned status code {response.status_code}')

        logging.info(f'''Fetching Accounts: {response.json().get("pagination")}''')
        #re-shuffle the data into a format that's a little easier to work with
        for acct in response.json()["searchResults"]:
            #don't clobber an existing local account record that may have been updated since the last Neon query
            if neonAccountDict.get(acct["Account ID"]) is None:
                neonAccountDict[acct["Account ID"]] = fixTypes(acct)
        #intentionally incrementing page before checking totalPages 
        #"page" is 0-based, "totalPages" is 1-based
        page += 1
        if page >= response.json().get("pagination").get("totalPages"):
            break
    return neonAccountDict


####################################################################
# Get all accounts in neon with OP IDs but no memberships 
####################################################################
def getOrphanOpAccounts(neonAccountDict = {}):
    searchFields = '''[
    {
        "field": "Membership Expiration Date",
        "operator": "BLANK"
    },
    {
        "field": "OpenPathID",
        "operator": "NOT_BLANK"
    }
]'''

    return getNeonAccounts(searchFields, neonAccountDict = neonAccountDict)

####################################################################
# Get all accounts in neon with Discourse IDs but no memberships 
####################################################################
def getOrphanDiscourseAccounts(neonAccountDict = {}):
    searchFields = '''[
    {
        "field": "Membership Expiration Date",
        "operator": "BLANK"
    },
    {
        "field": "DiscourseID",
        "operator": "NOT_BLANK"
    }
]'''

    return getNeonAccounts(searchFields, neonAccountDict = neonAccountDict)

####################################################################
# Get all members in Neon without subscription details
# Should we make a synthetic type for "Members" and combine this with getByType? 
####################################################################
def getMembersFast(neonAccountDict = {}):
    searchFields = '''[
    {
        "field": "Membership Expiration Date",
        "operator": "NOT_BLANK"
    }
]'''

    return getNeonAccounts(searchFields, neonAccountDict = neonAccountDict)

####################################################################
# Get all accounts of a given type in Neon without subscription details
####################################################################
def getAccountsByType(type: str, neonAccountDict = {}):
    searchFields = f'''[
    {{
        "field": "Individual Type",
        "operator": "EQUAL",
        "value": "{type}"
    }}
]'''

    return getNeonAccounts(searchFields, neonAccountDict = neonAccountDict)

####################################################################
# Get all staf and current/past members from Neon, incuding detailed subscription info
####################################################################
def getRealAccounts():
    accountCount = 0
    activeSubscriptions = 0

    neonAccountDict = getMembersFast()
    #Staff accounts might not have any membership records
    neonAccountDict = getAccountsByType(STAFF_TYPE, neonAccountDict = neonAccountDict)
    #former Staff accounts might not have any membership records
    neonAccountDict = getOrphanDiscourseAccounts(neonAccountDict = neonAccountDict)
    neonAccountDict = getOrphanOpAccounts(neonAccountDict = neonAccountDict)

    #some progress logging
    num_pings = 5
    num_loops = len(neonAccountDict)
    loops_per_ping = num_loops / num_pings
    progress_per_ping = 100 / num_pings
    progress = 0
    counter = 0

    for account in neonAccountDict:
        counter += 1
        accountCount += 1

        if counter > loops_per_ping:
            counter = 0
            progress += progress_per_ping
            logging.info(f'Updating Membership Info {int(progress)}% complete')

        #copy primary contact info to match search results format
        neonAccountDict[account]["fullName"] = f'''{neonAccountDict[account].get("First Name")} {neonAccountDict[account].get("Last Name")}'''

        #fixup missing membership expiration dates so we don't have to keep checking for them
        if neonAccountDict[account].get("Membership Expiration Date") is None:
            neonAccountDict[account]["Membership Expiration Date"] = "1970-01-01"
            neonAccountDict[account]["validMembership"] = False
            continue

        #If Neon thinks the expiration date is in the past, it's surely in the past.  don't bother checking details.
        #NOTE that Neon sets "Membership Start Date" to start of the most recent membership term, not the oldest.  This means
        #     expired members that had a renewal will show incorrect start dates by our counting.
        #     I figure we won't need that data, so don't bother pulling membership details to correct it.
        if datetime.datetime.strptime(neonAccountDict[account]["Membership Expiration Date"], '%Y-%m-%d').date() < yesterday:
            neonAccountDict[account]["validMembership"] = False
            continue

        neonAccountDict[account] = appendMemberships(neonAccountDict[account])

        if neonAccountDict[account].get("validMembership"):
            activeSubscriptions += 1
        
    logging.info(f"In {accountCount} Neon accounts we found {activeSubscriptions} active subscriptions")

    return neonAccountDict

####################################################################
# Helper function: is this Neon account marked with any type
####################################################################
def accountIsAnyType(account: dict):
    if account.get("individualTypes") is None:
        return False

    return True

####################################################################
# Helper function: is this Neon account marked with specified type
####################################################################
def accountIsType(account: dict, accountType: str):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == accountType:
            return True

    return False

####################################################################
# Helper function: does this user have access to Shaper Origin?
####################################################################
def accountHasShaperAccess(account: dict):
    #technically should check if this field contains a valid date... 
    if account.get("Shaper Origin"):
        return True
    return False

####################################################################
# Helper function: does this user have access to Festool Domino?
####################################################################
def accountHasDominoAccess(account: dict):
    #technically should check if this field contains a valid date... 
    if account.get("Festool Domino"):
        return True
    return False

####################################################################
# Helper function: is this Neon subscriber allowed facility access?
####################################################################
def subscriberHasFacilityAccess(account: dict):
    if account.get("validMembership") == True and not account.get("AccessSuspended") and account.get("WaiverDate") and account.get("FacilityTourDate"):
        logging.debug(f'''Account {account.get("Account ID")} is a subscriber with facility access''')
        return True
    logging.debug(f'''Subscriber Account {account.get("Account ID")} DOES NOT have access: 
ValidMembership({account.get("validMembership")}),
WaiverDate({account.get("WaiverDate")})
FacilityTourDate({account.get("FacilityTourDate")})
AccountSuspended({account.get("AccessSuspended")})''')
    return False

####################################################################
# Helper function: is this Neon account allowed facility access for any reason
####################################################################
def accountHasFacilityAccess(account: dict):
    if (accountIsType(account, STAFF_TYPE) or subscriberHasFacilityAccess(account)):
        return True

    # CoWorking is a moderately permissive group - they can ride out subscription lapses, but not other membership requirements
    if (accountIsType(account, COWORKING_TYPE)):
        if account.get("WaiverDate") and account.get("FacilityTourDate") and not account.get("AccessSuspended"):
            logging.warning(f'''Cowrking subscriber {account.get("fullName")} has access despite a lapsed membership.''')
            return True

    return False
