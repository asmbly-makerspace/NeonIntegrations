from discourseUpdateGroups import discourseUpdateGroups
from openPathUpdateAll import openPathUpdateAll

import neonUtil
import logging
import datetime, pytz

import json

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

logging.info("Starting sync cycle.")
neonAccounts = {}

#For real use, just get neon accounts directly
#Be aware this takes a long time (2+ minutes)
neonAccounts = neonUtil.getAllMembers()

# Testing goes a lot faster if we're working with a cache of accounts
# with open("Neon/memberAccounts.json") as neonFile:
#     neonAccountJson = json.load(neonFile)
#     for account in neonAccountJson:
#         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

#we're going to run this multiple times per day, but we don't want to send a zillion emails
now = datetime.datetime.now(pytz.timezone("America/Chicago"))
mailcutoff = datetime.datetime.combine(datetime.datetime.now(pytz.timezone("America/Chicago")), datetime.time(6, 0, tzinfo=pytz.timezone("America/Chicago")))

if (now < mailcutoff):
    openPathUpdateAll(neonAccounts, mailSummary = True)
else:
    openPathUpdateAll(neonAccounts, mailSummary = False)

discourseUpdateGroups(neonAccounts)
logging.info("Sync cycle complete.")
