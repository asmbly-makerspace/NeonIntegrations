########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pformat
import json
import requests
import os
import neonUtil
import logging

### Discourse Account Info
from config import D_APIkey, D_APIuser
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

##### DISCOURSE #####
# Get a list of all active users on Discourse
# Discourse queries return max 100 results, so if we get 100 try for another page
page = 0
fullDlist = []

discourseFilename = "Discourse/usersFull.json"
neonFilename = "Neon/neonAccounts.json"
neonDImissingFilename = "Neon/dIDmissing.json"

neonAccountList = []
noDIDlist = []
matchedDiscourseIDs = 0
fixedDiscourseIDs = 0
neonAccountsByDID = {}


#Just do a quick Neon fetch - we don't care about subscription details, and they take forever
neon_accounts = neonUtil.getMembersFast()
for account in neon_accounts:
    neonAccountList.append(neon_accounts.get(account))
    dID = neon_accounts.get(account).get("DiscourseID")
    if dID:
        #burn a little RAM to save search time later - make known DiscourseIDs easy to reference
        if neonAccountsByDID.get(dID):
            logging.warning(f'''Neon Account Problem: duplicate use of discourseID {dID}''')
        else:
            neonAccountsByDID[dID]= neon_accounts.get(account)

#check if we have user data cached.  If we do, use it.
if os.path.exists(discourseFilename) and os.access(discourseFilename, os.R_OK):
    with open(discourseFilename) as discourseFile:
        fullDlist = json.load(discourseFile)
else:
    #before doing all the Discourse-fetching, make sure we can write our output file
    outfile = open(discourseFilename, 'w')

    while True:
        url = f'https://yo.atxhs.org/admin/users/list/active.json?page={page}'
        memberResponse = requests.get(url, headers=D_headers)
        #TODO check status
        memberResponse = memberResponse.json()
        fullDlist = fullDlist + memberResponse
        if len(memberResponse) < 100:
            break
        else:
            logging.info(f'{len(fullDlist)} active users retrieved from Discourse... Querying for more data.')
            page += 1

    # Fetching emails and checking for weirdness (the weirdness is not coming from here.)
    # this email check is janky somehow - sometimes we get "email":null for accounts with valid emails in their Discourse profile
    # so far the error count has been low enough I've just been updating them in Neon manually

    # FETCHING EMAILS IN DISCOURSE IS SLOW -- only do it for accounts we don't already have Neon records for
    for i, response in enumerate(fullDlist):
        dID = response['username']
        if neonAccountsByDID.get(dID):
            fullDlist[i]["email"] = neonAccountsByDID.get(dID).get("Email 1")
            #logging.debug(f'''Found Discourse ID {dID} in Neon account {fullDlist[i]["email"]}''')
        else:
            url = f'https://yo.atxhs.org/users/{dID}/emails.json'
            emailResponse = requests.get(url, headers=D_headers)
            #TODO check status
            emailResponse = emailResponse.json()
            fullDlist[i]["email"]=emailResponse.get("email")
            fullDlist[i]["secondary_emails"]=emailResponse.get("secondary_emails")
            if " " in dID or "|" in dID:
                logging.warning(f'Discourse username "{dID}" found is not in a valid format. Check response at index {i}.')
            else:
                # print("All good")
                continue

    #TODO do we really want to save this file unconditionally?  It'll break automation...
    logging.info(f'{len(fullDlist)} active users retrieved from Discourse... saving to file as {discourseFilename}')
    json.dump(fullDlist, outfile, indent=4)

# Loop through response from Neon and update accounts where there is a matching name in Discourse
for acct in neonAccountList:
    fullname = f'{acct["First Name"]} {acct["Last Name"]}'
    email = acct["Email 1"]
    neonID = acct.get('Account ID')
    if acct.get("DiscourseID") is not None:
        dID = acct.get("DiscourseID")
        if any(dUser.get("username") == dID for dUser in fullDlist):
            matchedDiscourseIDs += 1
            continue
        else:
            logging.warning(f'''Neon Account Problem: {fullname}'s dID "{dID}" doesn't actually exist in Discourse (Neon ID {neonID})''')
    else:
        #logging.debug(f"{fullname} doesn't have a DiscourseID (Neon ID {neonID})")
        pass

    dID = ""
    for Daccount in fullDlist:
        if Daccount.get("email") and Daccount.get("email").casefold() == email.casefold():
            dID = Daccount.get("username")
            #logging.debug(f'{fullname} (Neon Acct #{neonID}) matches email with Discourse ID {dID}')
            break
        elif Daccount.get("name") and Daccount.get("name").casefold() == fullname.casefold():
            dID = Daccount.get("username")
            #logging.debug(f'{fullname} (Neon Acct #{neonID}) matches name with Discourse ID {dID}')
            break

    if dID != "":
        fixedDiscourseIDs += 1
        logging.info(f'   Updating DiscourseID to {dID} for Neon account #{neonID} - {fullname} {email}')
        acct["DiscourseID"] = dID
        neonUtil.updateDID(acct)
    else:
        logging.debug(f'   No DiscourseID found for Neon account #{neonID} - {fullname} {email}')
        noDIDlist.append(acct)

logging.info(f'''{len(neonAccountList)} Neon accounts checked: {matchedDiscourseIDs} had valid DiDs, {fixedDiscourseIDs} new matches, {len(noDIDlist)} still missing DiDs''')

# Save to file.  Do this open at the very end so Neon updates
# complete even if the report can't be saved
with open(neonDImissingFilename, 'w') as outfile:
    logging.info(f'Missing-DiDs Report saved to file as {neonDImissingFilename} for further review.')
    json.dump(noDIDlist, outfile, indent=4)
