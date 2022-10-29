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

    ##### Initialize these counts to number of zombies in Freshbooks
    ##### When this number falls to 0, update the email body text
    subscriberCount = 15
    missingWaiverCount = 15

    facilityUserCount = 0
    compedSubscriberCount = 0

    warningUsers = []
    missingTourUsers = {}

    for account in neonAccounts:
        if neonAccounts[account].get("validMembership"):
            subscriberCount += 1
        if neonUtil.subscriberHasFacilityAccess(neonAccounts[account]):
            facilityUserCount += 1
        if neonAccounts[account].get("comped"):
            compedSubscriberCount += 1

        if neonAccounts[account].get("OpenPathID"):
            openPathUtil.updateGroups(neonAccounts[account], 
                                        openPathGroups=opUsers.get(int(neonAccounts[account].get("OpenPathID"))).get("groups"))
            #note that this isn't necessarily 100% accurate, because we have Neon users with provisioned OpenPath IDs and no access groups
            #assuming that typical users who gained and lost openPath access have a signed waiver
            if not neonAccounts[account].get("WaiverDate"):
                warningUsers.append(f'''{neonAccounts[account].get("fullName")} ({neonAccounts[account].get("Email 1")})''')
        elif neonUtil.accountHasFacilityAccess(neonAccounts[account]):
            neonAccounts[account] = openPathUtil.createUser(neonAccounts[account])
            openPathUtil.updateGroups(neonAccounts[account],
                                        openPathGroups=[]) #pass empty groups list to skip the http get
            openPathUtil.createMobileCredential(neonAccounts[account])
        elif neonAccounts[account].get("validMembership"):
            if not neonAccounts[account].get("WaiverDate"):
                missingWaiverCount += 1
            if not neonAccounts[account].get("FacilityTourDate"):
                startDate = neonAccounts[account].get("Membership Start Date")
                missingTourUsers[startDate] = f'''{neonAccounts[account].get("fullName")} ({neonAccounts[account].get("Email 1")}) - since {startDate}'''

    list_separator = '\n            '
    compedSubscriberString = ""
    if (compedSubscriberCount > 0):
        compedSubscriberString = f''' plus {compedSubscriberCount} complimentary memberships'''

    msg = MIMEText(f'''
    Today Asmbly has {(subscriberCount - compedSubscriberCount)} paying subscribers{compedSubscriberString}.

    Of those:
        {facilityUserCount} have facility access
        {missingWaiverCount} are missing the waiver
        {len(missingTourUsers)} are missing the tour{':' if len(missingTourUsers) > 0 else ' (yay!)'}
            {list_separator.join(missingTourUsers[x] for x in sorted(missingTourUsers))}
{getWarningText(warningUsers)}
{commonMessageFooter}
''')
    msg['To'] = "membership@asmbly.org"
    msg['Subject'] = "Asmbly Daily Subscriber Update"

    if mailSummary:
        gmailUtil.sendMIMEmessage(msg)

    logging.info(msg)

#begin standalone script functionality -- pull neonAccounts and call our function
def main():
    neonAccounts = {}

    #For real use, just get neon accounts directly
    #Be aware this takes a long time (2+ minutes)
    neonAccounts = neonUtil.getAllMembers()

    # Testing goes a lot faster if we're working with a cache of accounts
    # with open("Neon/memberAccounts.json") as neonFile:
    #     neonAccountJson = json.load(neonFile)
    #     for account in neonAccountJson:
    #         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

    openPathUpdateAll(neonAccounts)

if __name__ == "__main__":
    main()
