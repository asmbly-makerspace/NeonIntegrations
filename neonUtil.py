############### Asmbly NeonCRM API Integrations ##################
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
##################################################################

from pprint import pformat
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


####################################################################
# Update the OpenPathID stored in Neon for an account
####################################################################
def updateOpenPathID(neonAccount):
    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("Account ID")) > 0)
    assert(int(neonAccount.get("OpenPathID")) > 0)

    data = f'''
{{
"individualAccount": {{
    "accountCustomFields": [
    {{
        "id": "178",
        "name": "OpenPathID",
        "value": "{neonAccount.get("OpenPathID")}"
    }}
    ]
}}
}}
'''
    url = N_baseURL + f'/accounts/{neonAccount.get("Account ID")}' + '?category=Account'
    if not dryRun:
        response = requests.patch(url, data=data, headers=N_headers)
        if (response.status_code != 200):
            raise ValueError(f'Patch {url} returned status code {response.status_code}')
    else:
        logging.warn("DryRun in neonUtil.updateOpenPathID()")

####################################################################
# Update the DiscourseID stored in Neon for an account
####################################################################
def updateDID(neonAccount):
    assert(int(neonAccount.get("Account ID")) > 0)
    assert(neonAccount.get("DiscourseID") is not None)

    data = f'''
{{
"individualAccount": {{
    "accountCustomFields": [
    {{
        "id": "85",
        "name": "DiscourseID",
        "value": "{neonAccount.get("DiscourseID")}"
    }}
    ]
}}
}}
'''
    url = N_baseURL + f'/accounts/{neonAccount.get("Account ID")}' + '?category=Account'
    if not dryRun:
        response = requests.patch(url, data=data, headers=N_headers)
        if (response.status_code != 200):
            raise ValueError(f'Patch {url} returned status code {response.status_code}')
    else:
        logging.warn("DryRun in neonUtil.updateDID()")


####################################################################
# Update a valid Neon account to include membership information
####################################################################
def appendMemberships(neonAccount, detailed=False):
    #this should be a pretty thorough check for sane argument
    assert(int(neonAccount.get("Account ID")) > 0)

    #Neon counts a failed renewal as a valid subscription so long as automatic renewal is enabled.
    #WE only think a subscription is valid if the subscriber actually paid for it, so check for a successful payment.
    url = N_baseURL + f'/accounts/{neonAccount.get("Account ID")}/memberships'
    response = requests.get(url, headers=N_headers)

    if (response.status_code != 200):
        raise ValueError(f'Get {url} returned status code {response.status_code}')

    #logging.debug(pformat(response.json()))

    neonAccount["validMembership"] = False

    memberships = response.json().get("memberships")

    if len(memberships) > 0:
        ### end date of the most recent paid membership (initialize to ancient history)
        latestSuccessfulMembershipExpiration = datetime.date(1970, 1, 1)
        ##start date of earliest membership (initialize to today)
        firstMembershipStart = today
        ##flag indicating the account has at least one paid membership
        atLeastOneValidMembership = False
        ##flag indicating the current membership has hard-failed (denied/cancelled/refunded)
        currentMembershipHardFailed = False

        for membership in memberships:
            membershipExpiration = datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date()
            membershipStart = datetime.datetime.strptime(membership["termStartDate"], '%Y-%m-%d').date()

            logging.debug(f'''Membership ending {membershipExpiration} status {membership["status"]} autorenewal is {membership["autoRenewal"]} ''')

            ### If this membership *was* actually paid for:
            if membership["status"] == "SUCCEEDED":
                ### flag this account as having at least once been paid.
                atLeastOneValidMembership = True

                ### If this (paid) membership is later than the latest we know about, remember its end date
                if membershipExpiration > latestSuccessfulMembershipExpiration:
                    latestSuccessfulMembershipExpiration = membershipExpiration

                    #in my testing membership[autoRenewal] is the same value for all memberships and
                    #reflects the current Neon setting.  It seems safest to keep the latest successful
                    #value, but we should probably spot-check this from time to time
                    neonAccount["autoRenewal"] = membership["autoRenewal"]

                ### If this (paid) membership is the earliest one we know about, remember the start date
                if membershipStart < firstMembershipStart:
                    firstMembershipStart = membershipStart

                ### If today is during this (paid), mark the account as valid (should probably be called "active" but well...)
                if membershipExpiration >= today and membershipStart <= today:
                    neonAccount["validMembership"] = True
                    if membership.get("fee") == 0:
                        neonAccount["comped"] = True
            elif membership["status"] == "DECLINED" or membership["status"] == "CANCELLED" or membership["status"] == "REFUNDED":
                ### If today is during a hard-failed membership, note that so we aren't allowing former members access
                if membershipExpiration >= today and membershipStart <= today:
                    currentMembershipHardFailed = True

        if latestSuccessfulMembershipExpiration == yesterday and neonAccount["autoRenewal"] and not currentMembershipHardFailed:
            logging.info(f'''Neon appears to not have processed AutoRenewal for account {neonAccount.get("Account ID")}; allowing access today only''')
            neonAccount["validMembership"] = True

        #!!! NOTE no promise that membership was continuous between these two dates !!!
        if atLeastOneValidMembership:
            neonAccount["Membership Start Date"] = str(firstMembershipStart)
            neonAccount["Membership Expiration Date"] = str(latestSuccessfulMembershipExpiration)

        if (detailed):
            neonAccount["MembershipDetails"] = memberships

    #logging.debug(pformat(neonAccount))

    return neonAccount

####################################################################
# Given a Neon member ID, return an account including membership info
####################################################################
def getMemberById(id, detailed = False):
    #I think this will raise an exception and exit if it fails??? 
    id = int(id)

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
def fixTypes(account):
    if account.get("Individual Type"):
        typeDictList = []
        typelist = account.get("Individual Type").split('|')
        for type in typelist:
            typeDictList.append({'name' : type.strip()})
        account["individualTypes"] = typeDictList
    return account

####################################################################
# Get all members in Neon without subscription details
####################################################################
def getMembersFast():
    neon_accounts = {}

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
    "searchFields": [
        {{
            "field": "Membership Expiration Date",
            "operator": "NOT_BLANK"
        }}
    ],
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

        logging.info(f'''{response.json().get("pagination")}''')
        #re-shuffle the data into a format that's a little easier to work with
        for acct in response.json()["searchResults"]:
            neon_accounts[acct["Account ID"]] = fixTypes(acct)
        #intentionally incrementing page before checking totalPages 
        #"page" is 0-based, "totalPages" is 1-based
        page += 1
        if page >= response.json().get("pagination").get("totalPages"):
            break
    return neon_accounts

####################################################################
# Get all members in Neon, incuding detailed subscription info
# BUG -- this function is often used where we want staff accounts too.  fix that.
# FIXME -- this function signature is annoyingly inconsistent with getMemberByID
####################################################################
def getAllMembers():
    accountCount = 0
    paidSubscribers = 0

    neon_accounts = getMembersFast()

    #some progress logging
    num_pings = 5
    num_loops = len(neon_accounts)
    loops_per_ping = num_loops / num_pings
    progress_per_ping = 100 / num_pings
    progress = 0
    counter = 0

    for account in neon_accounts:
        counter += 1
        accountCount += 1

        if counter > loops_per_ping:
            counter = 0
            progress += progress_per_ping
            logging.info(f'Updating Membership Info {int(progress)}% complete')

        #copy primary contact info to match search results format
        neon_accounts[account]["fullName"] = f'''{neon_accounts[account].get("First Name")} {neon_accounts[account].get("Last Name")}'''

        #If Neon thinks the expiration date is in the past, it's surely in the past.  don't bother checking details.
        #NOTE that Neon sets "Membership Start Date" to start of the most recent membership term, not the oldest.  This means
        #     expired members that had a renewal will show incorrect start dates by our counting.
        #     I figure we won't need that data, so don't bother pulling membership details to correct it.
        if datetime.datetime.strptime(neon_accounts[account]["Membership Expiration Date"], '%Y-%m-%d').date() < today:
            neon_accounts[account]["validMembership"] = False
            continue

        neon_accounts[account] = appendMemberships(neon_accounts[account])

        if neon_accounts[account].get("validMembership"):
            paidSubscribers += 1
        
    logging.info(f"In {accountCount} Neon accounts we found {paidSubscribers} paid subscribers")

    return neon_accounts

####################################################################
# Helper function: is this Neon account a staff member
####################################################################
def accountIsStaff(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "Paid Staff":
            return True

    return False

####################################################################
# Helper function: is this Neon account a vounteer leader
####################################################################
def accountIsLeader(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "Leader":
            return True

    return False

####################################################################
# Helper function: is this Neon account a vounteer leader
####################################################################
def accountIsSuper(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "Super Steward":
            return True

    return False

####################################################################
# Helper function: is this Neon account a coWorking subscriber
####################################################################
def accountIsCoWorking(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "CoWorking Tenant":
            return True

    return False

####################################################################
# Helper function: is this Neon account a steward
####################################################################
def accountIsSteward(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "Steward":
            return True

    return False

####################################################################
# Helper function: is this Neon account an instructor
####################################################################
def accountIsInstructor(account):
    if account.get("individualTypes") is None:
        return False

    for type in account.get("individualTypes"):
        if type.get("name") == "Instructor":
            return True

    return False

####################################################################
# Helper function: does this user have access to Shaper Origin?
####################################################################
def accountHasShaperAccess(account):
    #technically should check if this field contains a valid date... 
    if account.get("Shaper Origin"):
        return True
    return False

####################################################################
# Helper function: does this user have access to Festool Domino?
####################################################################
def accountHasDominoAccess(account):
    #technically should check if this field contains a valid date... 
    if account.get("Festool Domino"):
        return True
    return False

####################################################################
# Helper function: is this Neon subscriber allowed facility access?
####################################################################
def subscriberHasFacilityAccess(account):
    if account.get("validMembership") == True and not account.get("AccessSuspended") and account.get("WaiverDate") and account.get("FacilityTourDate"):
        logging.debug(f'''Account {account.get("Account ID")} is a subscriber with facility access''')
        return True
    logging.debug(f'''Account {account.get("Account ID")} DOES NOT have access: 
ValidMembership({account.get("validMembership")}),
WaiverDate({account.get("WaiverDate")})
FacilityTourDate({account.get("FacilityTourDate")})
AccountSuspended({account.get("AccessSuspended")})''')
    return False

####################################################################
# Helper function: is this Neon account allowed facility access for any reason
####################################################################
def accountHasFacilityAccess(account):
    return (accountIsStaff(account) or subscriberHasFacilityAccess(account))
