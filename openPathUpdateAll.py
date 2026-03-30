###############################################################################
#Fetch all member records from Neon and update OpenPath as necessary for all
#* Run me at least once a day to catch subscription expirations

import neonUtil
import openPathUtil
import logging
import json
from email.mime.text import MIMEText
from AsmblyMessageFactory import commonMessageFooter
import gmailUtil

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

def getWarningText(warningUsers):
    if len(warningUsers) == 0:
        return ""

    list_separator = '\n      '
    return f'''
    WARNING: {len(warningUsers)} USER{'S HAVE' if len(warningUsers) > 1 else ' HAS'} FACILITY ACCESS WITHOUT A SIGNED WAIVER:
      {list_separator.join(warningUsers)}'''

def openPathUpdateAll(neonAccounts, mailSummary = False):
    opUsers = openPathUtil.getAllUsers()

    # Build externalId->opUser lookup to reconcile Neon accounts missing their OpenPathID
    opUsersByExternalId = {}
    for opUser in opUsers.values():
        externalId = opUser.get("externalId")
        if externalId:
            opUsersByExternalId[externalId] = opUser

    subscriberCount = 0
    ceramicsCount = 0
    facilityUserCount = 0
    ceramicsFacilityCount = 0

    warningUsers = []
    missingTourSubscribers = {}
    missingWaiverSubscribers = {}
    missingCsiSubscribers = {}
    compedSubscribers = []
    compedLeaders = []

    paidRegulars = 0
    paidCeramics = 0

    for accountId, account in neonAccounts.items():
        if not account.get("OpenPathID") and accountId in opUsersByExternalId:
            opUser = opUsersByExternalId[accountId]
            logging.info(
                "Reconciling OpenPathID %s for Neon account %s (%s)",
                opUser.get("id"),
                accountId,
                account.get("Email 1"),
            )
            account["OpenPathID"] = opUser.get("id")
            neonUtil.updateOpenPathID(account)

        if not account.get("paidRegular") and not account.get("paidCeramics") and not neonUtil.accountIsType(account, neonUtil.STAFF_TYPE):
            #Accounts that are neither paid nor staff might still have access
            if neonUtil.accountIsType(account, neonUtil.LEAD_TYPE):
                compedLeaders.append(f'''{account.get("fullName")} ({account.get("Email 1")})''')
            elif account.get("compedRegular") or account.get("compedCeramics"):
                compedSubscribers.append(f'''{account.get("fullName")} ({account.get("Email 1")})''')

        if account.get("validMembership"):
            subscriberCount += 1
            if account.get("ceramicsMembership"):
                ceramicsCount += 1

            #accounts with concurrent paid regular and ceramics memberships are most likely
            #upgrades that should be only counted as ceramics members
            if account.get("paidCeramics"):
                paidCeramics += 1
            elif account.get("paidRegular"):
                paidRegulars += 1

        if account.get("paidRegular") and account.get("paidCeramics"):
            logging.info(f'''{account.get("fullName")} ({account.get("Email 1")}) has concurrent paid memberships.''')

        if neonUtil.subscriberHasFacilityAccess(account):
            facilityUserCount += 1

        if neonUtil.subscriberHasCeramicsAccess(account):
            ceramicsFacilityCount += 1

        if account.get("OpenPathID"):
            openPathUtil.updateGroups(account,
                                        openPathGroups=opUsers.get(int(account.get("OpenPathID"))).get("groups"))
            #note that this isn't necessarily 100% accurate, because we have Neon users with provisioned OpenPath IDs and no access groups
            #assuming that typical users who gained and lost openPath access have a signed waiver
            if not account.get("WaiverDate"):
                warningUsers.append(f'''{account.get("fullName")} ({account.get("Email 1")})''')
        elif neonUtil.accountHasFacilityAccess(account):
            if openPathUtil.createUser(account):
                openPathUtil.updateGroups(account,
                                            openPathGroups=[]) #pass empty groups list to skip the http get
                openPathUtil.createMobileCredential(account)
        elif account.get("validMembership"):
            startDate = account.get("Membership Start Date")
            if not account.get("WaiverDate"):
                missingWaiverSubscribers[accountId] = f'''{account.get("fullName")} ({account.get("Email 1")}) - since {startDate}'''
            if not account.get("FacilityTourDate"):
                missingTourSubscribers[accountId] = f'''{account.get("fullName")} ({account.get("Email 1")}) - since {startDate}'''

        #an account might be missing CSI but still have regular facility access stuff handled
        if account.get("ceramicsMembership") and not account.get("CsiDate"):
            missingCsiSubscribers[accountId] = f'''{account.get("fullName")} ({account.get("Email 1")}) - since {account.get("Ceramics Start Date")}'''

    list_separator = '\n            '
    compedSubscriberString = ""
    compedSubscriberDetails =""
    compedLeaderDetails = ""
    if (len(compedSubscribers)+len(compedLeaders) > 0):
        compedSubscriberString = f''' plus {len(compedSubscribers)+len(compedLeaders)} complimentary memberships'''
        if (len(compedLeaders) > 0):
            compedLeaderDetails = f'''
        Comped Volunteer Leaders:
            {list_separator.join(compedLeaders[x] for x in range(len(compedLeaders)))}
'''
        if (len(compedSubscribers) > 0):
            compedSubscriberDetails = f'''
        Other Comped Memberships:
            {list_separator.join(compedSubscribers[x] for x in range(len(compedSubscribers)))}
'''

    msg = MIMEText(f'''
    Today Asmbly has {paidRegulars} regular and {paidCeramics} ceramics subscribers{compedSubscriberString}.

    Of those:
        {facilityUserCount} have facility access and {ceramicsFacilityCount} have ceramics access
        {len(missingWaiverSubscribers)} are missing the waiver{':' if len(missingWaiverSubscribers) > 0 else ' (yay!)'}
            {list_separator.join(missingWaiverSubscribers[x] for x in sorted(missingWaiverSubscribers, reverse=True))}
        {len(missingTourSubscribers)} are missing orientation{':' if len(missingTourSubscribers) > 0 else ' (yay!)'}
            {list_separator.join(missingTourSubscribers[x] for x in sorted(missingTourSubscribers, reverse=True))}
        {len(missingCsiSubscribers)} are missing Ceramics Introduction{':' if len(missingCsiSubscribers) > 0 else ' (yay!)'}
            {list_separator.join(missingCsiSubscribers[x] for x in sorted(missingCsiSubscribers, reverse=True))}
{getWarningText(warningUsers)}
{compedLeaderDetails}
{compedSubscriberDetails}
{commonMessageFooter}
''')
    msg['To'] = "membership@asmbly.org"
    msg['Subject'] = "Asmbly Daily Subscriber Update"

    summaryMsg = MIMEText(f'''
    Today Asmbly has {paidRegulars} regular and {paidCeramics} ceramics paid subscribers.

    Additionally:
        {len(compedLeaders)} Asmbly leaders have free memberships.
        {len(compedSubscribers)} other Asmbly volunteers have free memberships.

    {facilityUserCount} users have facility access and {ceramicsFacilityCount} have ceramics access
    {len(missingWaiverSubscribers)} are missing the waiver.
    {len(missingTourSubscribers)} are missing orientation.
    {len(missingCsiSubscribers)} are missing Ceramics Introduction.

{commonMessageFooter}
''')
    summaryMsg['To'] = "membership.committee@asmbly.org"
    summaryMsg['Subject'] = "Asmbly Daily Subscriber Summary"

    if mailSummary:
        gmailUtil.sendMIMEmessage(msg)
        gmailUtil.sendMIMEmessage(summaryMsg)

    logging.info(msg.get_payload())
    print(summaryMsg.get_payload())

#begin standalone script functionality -- pull neonAccounts and call our function
def main():
    neonAccounts = {}

    #For real use, just get neon accounts directly
    #Be aware this takes a long time (2+ minutes)
    neonAccounts = neonUtil.getRealAccounts()

    # Testing goes a lot faster if we're working with a cache of accounts
    #with open("Neon/neonAccounts.json") as neonFile:
    #    neonAccountJson = json.load(neonFile)
    #    for account in neonAccountJson:
    #        neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

    openPathUpdateAll(neonAccounts)

if __name__ == "__main__":
    main()
