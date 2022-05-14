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
# Update a valid Neon account to include membership information
####################################################################
def appendMemberships(neonAccount):
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
        latestSuccessfulMembershipExpiration = datetime.date(1970, 1, 1)
        latestKnownMembershipExpiration = datetime.date(1970, 1, 1)

        firstMembershipStart = today
        atLeastOneValidMembership = False

        for membership in memberships:
            membershipExpiration = datetime.datetime.strptime(membership["termEndDate"], '%Y-%m-%d').date()
            membershipStart = datetime.datetime.strptime(membership["termStartDate"], '%Y-%m-%d').date()

            logging.debug(f'''Membership ending {membershipExpiration} status {membership["status"]} autorenewal is {membership["autoRenewal"]} ''')

            if membershipExpiration > latestKnownMembershipExpiration:
                latestKnownMembershipExpiration = membershipExpiration

            if membership["status"] == "SUCCEEDED":
                atLeastOneValidMembership = True
                if membershipExpiration > latestSuccessfulMembershipExpiration:
                    #in my testing membership[autoRenewal] is the same value for all memberships and
                    #reflects the current Neon setting.  It seems safest to keep the latest successful
                    #value, but we should probably spot-check this from time to time
                    neonAccount["autoRenewal"] = membership["autoRenewal"]
                    latestSuccessfulMembershipExpiration = membershipExpiration
                if membershipStart < firstMembershipStart:
                    firstMembershipStart = membershipStart
                if membershipExpiration >= today and membershipStart <= today:
                    neonAccount["validMembership"] = True

        #There's another scenario where a Neon membership is valid:
        #if the most recent membership expired in the past (yesterday?)
        #  and the most recent membership is SUCCEEDED
        #  and auto-renewal is enabled on the account
        #this catches the scenario where Neon just hasn't gotten around to processing the renewal yet.
        if not neonAccount.get("validMembership"):
            if (latestKnownMembershipExpiration == latestSuccessfulMembershipExpiration) and neonAccount.get("autoRenewal"):
                neonAccount["validMembership"] = True

        #!!! NOTE no promise that membership was continuous between these two dates !!!
        if atLeastOneValidMembership:
            neonAccount["Membership Start Date"] = str(firstMembershipStart)
            neonAccount["Membership Expiration Date"] = str(latestSuccessfulMembershipExpiration)

    #logging.debug(pformat(neonAccount))

    return neonAccount

####################################################################
# Given a Neon member ID, return an account including membership info
####################################################################
def getMemberById(id):
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
    account = appendMemberships(account)
    return account

def getAllMembers():
    neon_accounts = {}
    accountCount = 0
    paidSubscribers = 0

    #Output Fields
    #85 is DiscourseId
    #77 is OrientationDate
    #179 is WaiverDate
    #88 is KeyCardID
    #178 is OpenPathID
    #180 is AccessSuspended

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
        85, 77, 179, 178, 88, 180, 182
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
            neon_accounts[acct["Account ID"]] = acct
        #intentionally incrementing page before checking totalPages 
        #"page" is 0-based, "totalPages" is 1-based
        page += 1
        if page >= response.json().get("pagination").get("totalPages"):
            break

    #some progress logging
    num_pings = 5
    num_loops = len(neon_accounts)
    loops_per_ping = num_loops / num_pings
    progress_per_ping = 100 / num_pings
    progress = 0
    counter = 0

    for account in neon_accounts:
        counter += 1
        #TODO print some progress info so it doesn't look like the script hung
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
# Helper function: is this Neon account allowed facility access?
####################################################################
def accountHasFacilityAccess(account):
    if account.get("validMembership") == True and not account.get("AccessSuspended") and account.get("WaiverDate") and account.get("FacilityTourDate"):
        logging.debug(f'''Account {account.get("Account ID")} has facility access''')
        return True
    logging.debug(f'''Account {account.get("Account ID")} DOES NOT have access: 
ValidMembership({account.get("validMembership")}),
WaiverDate({account.get("WaiverDate")})
FacilityTourDate({account.get("FacilityTourDate")})
AccountSuspended({account.get("AccessSuspended")})''')
    return False

