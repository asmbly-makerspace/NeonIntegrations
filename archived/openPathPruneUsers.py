###############################################################################
#Fetch all member records from Neon and update OpenPath as necessary for all
#* Run me at least once a day to catch subscription expirations

import neonUtil
import openPathUtil
import logging
import json
import datetime, pytz
from email.mime.text import MIMEText
from AsmblyMessageFactory import commonMessageFooter
import gmailUtil

PRUNE_CUTOFF_DAYS = 180

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

#I'm not absolutely certain NeonCRM thinks it's in central time, but it's in the ballpark.
#pacific time might be slightly more accurate.  Maybe I'll ask their support.
today = datetime.datetime.now(pytz.timezone("America/Chicago")).date()
pruneCutoff = today - datetime.timedelta(days=PRUNE_CUTOFF_DAYS)

def openPathPruneUsers(neonAccounts):
    opUsers = openPathUtil.getAllUsers()

    outfile = open('./opUsers.json', 'w')

    #write out to the file we opened up top
    json.dump(opUsers, outfile, indent=4)

    for account in neonAccounts:
        if neonUtil.accountHasFacilityAccess(neonAccounts[account]):
            continue

        if neonAccounts[account].get("OpenPathID"):
            if neonAccounts[account].get("Membership Expiration Date") is not None:
                membershipExpiration = datetime.datetime.strptime(neonAccounts[account]["Membership Expiration Date"], '%Y-%m-%d').date()
                if membershipExpiration < pruneCutoff:
                    logging.info(f'''Neon account {neonAccounts[account].get("fullName")} has had an openPath ID inactive for more than {PRUNE_CUTOFF_DAYS} days.''')
                    credentials = openPathUtil.getCredentialsForId(neonAccounts[account].get("OpenPathID"))
                    for credential in credentials:
                        if credential.get("card") is None:
                            logging.info(f'''    account has a credential to delete: ID {credential.get("id")} type {credential.get('credentialType').get('name')}''')
                            #This call didn't work when tried with the ID of a cloud key.  need to debug further.
                            openPathUtil.deleteCredential(neonAccounts[account].get("OpenPathID"), credential.get("id"))
                        else:
                            logging.info("    account has a card provisioned!")
                            continue
                    openPathUtil.deactivateUser(neonAccounts[account].get("OpenPathID"))
                    neonAccounts[account]["OpenPathID"] = None
                    neonUtil.updateOpenPathID(neonAccounts[account])

#begin standalone script functionality -- pull neonAccounts and call our function
def main():
    neonAccounts = {}

    #For real use, just get neon accounts directly
    #Be aware this takes a long time (2+ minutes)
    neonAccounts = neonUtil.getRealAccounts()

    # Testing goes a lot faster if we're working with a cache of accounts
    # with open("Neon/neonAccounts.json") as neonFile:
    #     neonAccountJson = json.load(neonFile)
    #     for account in neonAccountJson:
    #         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

    openPathPruneUsers(neonAccounts)

if __name__ == "__main__":
    main()
