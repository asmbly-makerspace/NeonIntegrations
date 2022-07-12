###############################################################################
#Fetch all member records from Neon and update OpenPath as necessary for all
#* Run me at least once a day to catch subscription expirations

import neonUtil
import openPathUtil
import logging
import sys

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

def openPathUpdateSingle(neonID):
    account = neonUtil.getMemberById(neonID)
    if account.get("OpenPathID"):
        openPathUtil.updateGroups(account)
        #note that this isn't necessarily 100% accurate, because we have Neon users with provisioned OpenPath IDs and no access groups
        #assuming that typical users who gained and lost openPath access have a signed waiver
    elif neonUtil.accountHasFacilityAccess(account):
        account = openPathUtil.createUser(account)
        openPathUtil.updateGroups(account, openPathGroups=[]) #pass empty groups list to skip the http get
        openPathUtil.createMobileCredential(account)
    elif account.get("validMembership"):
        if not account.get("WaiverDate"):
            logging.info(f'''{neonAccounts[account].get("fullName")} ({neonAccounts[account].get("Email 1")} is missing the Waiver''')
        if not account.get("FacilityTourDate"):
            logging.info(f'''{neonAccounts[account].get("fullName")} ({neonAccounts[account].get("Email 1")} is missing the Facility Tour''')


#begin standalone script functionality -- update single account provided on command line
def main():
    if len(sys.argv) != 2 or not str(sys.argv[1]).isnumeric():
        print(f'''Usage: {sys.argv[0]} <integer NeonID>''')
    else:
        openPathUpdateSingle(str(sys.argv[1]))

if __name__ == "__main__":
    main()
