########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pprint
import json
import discourseUtil
import logging
from config import D_APIkey, D_APIuser

from util import apiCall

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

neonFilename = "Neon/memberAccounts.json"
neonAccounts = {}

# ##### NEON ######
#first off, check that we have a Neon account list before spending a bunch of time on the Discourse API
with open(neonFilename) as neonFile:
    neonAccountJson = json.load(neonFile)
    for account in neonAccountJson:
        neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

# ##### DISCOURSE #####
# retrieve all members of hax0r group
haxors = discourseUtil.getHaxors()

#this first loop adds people to haxors (or notes lack of DiscourseID)
addHaxor = ""

#Step 1a: find all Neon accounts that are paid up, have a DiscourseID, and aren't in Hax0rs
for account in neonAccounts:
    if neonAccounts[account].get("validMembership") != True:
        continue
    #pprint(neonAccounts[account])
    if neonAccounts[account].get("DiscourseID") is None or neonAccounts[account].get("DiscourseID") == "":
        #neon accounts missing a DiscourseID
        #print(neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+" ("+neonAccounts[account]["Account ID"]+") is active but has no Discourse ID")
        pass
    elif haxors.get(neonAccounts[account]["DiscourseID"]) is None:
        dID = neonAccounts[account]["DiscourseID"]
        #neon accounts not in Haxor group
        print(dID+" ("+neonAccounts[account]["First Name"]+" "+neonAccounts[account]["Last Name"]+") is active and will be added to Haxors")
        if addHaxor != "":
            addHaxor+= ','
        addHaxor += f'{dID}'

discourseUtil.addHaxors(addHaxor)

#until we decommission FreshBooks, hax0r auditing is weirded
#for now just remove people with valid neon accounts who let their subscriptions lapse
print()
#step 2 : find hax0rs without an active membership
removeHaxor = ""
matchedAccounts = 0
for haxor in haxors:
    expired = False
    match = False
    for account in neonAccounts:
        if haxor == neonAccounts[account].get("DiscourseID"):
            match = True
            if not neonAccounts[account].get("validMembership"):
                expired = True

    if expired:
        print(haxor+" ("+haxors[haxor]["name"]+") used to be a subscriber but is no longer")
        if removeHaxor != "":
            removeHaxor+= ','
        removeHaxor += f'{haxor}'
    if not match:
        #print(haxor+" ("+haxors[haxor]["name"]+") doesn't seem to have a Neon record")
        #this will happen must less often once we stop using Freshbooks
        pass

discourseUtil.removeHaxors(removeHaxor)
