########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################

import json
import neonUtil
import logging

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

#before doing all the Neon-fetching, make sure we can write our output file
#TODO filename should be a global config or command-line option or something
outfile = open('./Neon/memberAccounts.json', 'w')

#For real use, just get neon accounts directly
#Be aware this takes a long time (2+ minutes)
neonAccounts = neonUtil.getAllMembers()

#print (f"In {accountCount} Neon accounts we found {successfulMemberships} paid memberships, {expiredMemberships} expired memberships, and {failedMemberships} failed renewals")

#write out to the file we opened up top
json.dump(neonAccounts, outfile, indent=4)

