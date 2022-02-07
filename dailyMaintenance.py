from discourseUpdateHaxors import discourseUpdateHaxors
from openPathUpdateAll import openPathUpdateAll

import neonUtil
import logging
import json

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

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
discourseUpdateHaxors(neonAccounts)
