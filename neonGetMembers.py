#Simple script to call neonUtil.getAllMembers() and write the results to disk

import neonUtil
import logging
import json

logging.basicConfig(level=logging.INFO)

#before doing all the Neon-fetching, make sure we can write our output file
#TODO filename should be a global config or command-line option or something
outfile = open('./Neon/memberAccounts.json', 'w')

neon_accounts = neonUtil.getAllMembers()

#write out to the file we opened up top
json.dump(neon_accounts, outfile, indent=4)
