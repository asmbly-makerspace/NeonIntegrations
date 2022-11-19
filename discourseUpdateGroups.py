########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pformat
import json
import discourseUtil
import neonUtil
import logging

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

def discourseUpdateGroups(neonAccounts):
    # ##### DISCOURSE #####
    # retrieve all members of makers group
    makers = discourseUtil.getMakers()

    #Step 1: find all Neon accounts that are paid up, have a DiscourseID, and aren't in Makers
    addMakers = ""
    for account in neonAccounts:
        if not neonAccounts[account].get("validMembership") and not neonUtil.accountIsType(neonAccounts[account], neonUtil.FRESHBOOKS_TYPE):
            continue
        #logging.debug(pformat(neonAccounts[account]))
        if neonAccounts[account].get("DiscourseID") is None or neonAccounts[account].get("DiscourseID") == "":
            #neon accounts missing a DiscourseID
            logging.debug(neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+" ("+neonAccounts[account]["Account ID"]+") is active but has no Discourse ID")
            pass
        elif makers.get(neonAccounts[account]["DiscourseID"]) is None:
            dID = neonAccounts[account]["DiscourseID"]
            #neon accounts not in maker group
            logging.info(dID+" ("+neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+") is active and will be added to Makers")
            if addMakers != "":
                addMakers+= ','
            addMakers += f'{dID}'

    discourseUtil.promoteMakers(addMakers)

    #step 2 : remove makers without an active membership
    removeMakers = ""
    for maker in makers:
        expired = False
        match = False
        for account in neonAccounts:
            if maker == neonAccounts[account].get("DiscourseID"):
                match = True
                if not neonAccounts[account].get("validMembership") and not neonUtil.accountIsType(neonAccounts[account], neonUtil.FRESHBOOKS_TYPE):
                    expired = True

        if expired:
            logging.info(maker+" ("+makers[maker]["name"]+") used to be a subscriber but is no longer")
            if removeMakers != "":
                removeMakers+= ','
            removeMakers += f'{maker}'
        if not match:
            logging.warning(maker+" ("+makers[maker]["name"]+") doesn't seem to have a Neon record")
            if removeMakers != "":
                removeMakers+= ','
            removeMakers += f'{maker}'

    discourseUtil.demoteMakers(removeMakers)

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

    discourseUpdateGroups(neonAccounts)

if __name__ == "__main__":
    main()