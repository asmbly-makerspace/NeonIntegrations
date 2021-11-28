###############################################################################
#Fetch all member records from Neon and update OpenPath as necessary for all
#* Run me at least once a day to catch subscription expirations

import neonUtil
import openPathUtil
import logging
import json

logging.basicConfig(level=logging.INFO)

neonAccounts = {}

#For real use, just get neon accounts directly
#Be aware this takes a long time (2+ minutes)
neonAccounts = neonUtil.getAllMembers()

# Testing goes a lot faster if we're working with a cache of accounts
# with open("Neon/memberAccounts.json") as neonFile:
#     neonAccountJson = json.load(neonFile)
#     for account in neonAccountJson:
#         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

opUsers = openPathUtil.getAllUsers()

for account in neonAccounts:
    if neonAccounts[account].get("OpenPathID"):
        openPathUtil.updateGroups(neonAccounts[account], opUsers.get(int(neonAccounts[account].get("OpenPathID"))).get("groups"))
    elif neonUtil.accountHasFacilityAccess(neonAccounts[account]):
        neonAccounts[account] = openPathUtil.createUser(neonAccounts[account])
        openPathUtil.updateGroups(neonAccounts[account], []) #pass empty groups list to skip the http get
        openPathUtil.createMobileCredential(neonAccounts[account])
