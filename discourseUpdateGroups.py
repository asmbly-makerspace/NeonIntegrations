########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pformat
import discourseUtil
import neonUtil
import logging

logging.basicConfig(
         format='%(asctime)s %(levelname)-8s %(message)s',
         level=logging.INFO,
         datefmt='%Y-%m-%d %H:%M:%S')

def updateMakers(neonAccounts: dict):
    # retrieve all members of makers group
    makers = discourseUtil.getGroupMembers(discourseUtil.GROUP_MAKERS)
    if makers is None:
        # Failed to fetch group membership, so avoid updating
        return

    #Step 1: find all Neon accounts that are paid up, have a DiscourseID, and aren't in Makers
    addMakers = set()
    for account in neonAccounts:
        if not neonAccounts[account].get("validMembership") and not neonUtil.accountIsType(neonAccounts[account], neonUtil.STAFF_TYPE):
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
            addMakers.add(f'{dID}')

    #promote new Makers -- add to Makers, remove from Community (which may fail, but that's OK)
    discourseUtil.removeGroupMembers(list(addMakers), discourseUtil.GROUP_COMMUNITY)
    discourseUtil.addGroupMembers(list(addMakers), discourseUtil.GROUP_MAKERS)

    #step 2 : remove makers without an active membership
    removeMakers = set()
    for maker in makers:
        remove = True
        for account in neonAccounts:
            if maker == neonAccounts[account].get("DiscourseID") and (neonAccounts[account].get("validMembership") or neonUtil.accountIsType(neonAccounts[account], neonUtil.STAFF_TYPE)):
                    remove = False

        if remove:
            logging.info(maker+" ("+makers[maker]["name"]+") used to be a subscriber but is no longer")
            removeMakers.add(f'{maker}')

    #demote expired or otherwise inactive Makers -- remove from Makers, add to Community
    discourseUtil.removeGroupMembers(list(removeMakers), discourseUtil.GROUP_MAKERS)
    discourseUtil.addGroupMembers(list(removeMakers), discourseUtil.GROUP_COMMUNITY)


def updateTypes(neonAccounts: dict):
    #using sets for these to pevent duplicate entries
    leadershipMembers = set()
    stewardsMembers = set()
    instructorsMembers = set()
    wikiAdmins = set()

    for account in neonAccounts.values():
        dID = account.get("DiscourseID")
        if not dID:
            if neonUtil.accountIsAnyType(account):
                logging.warning(f'{account["First Name"]} {account["Last Name"]} ({account["Account ID"]}) has type {account.get("Individual Type")} but no Discourse ID')
            continue

        if neonUtil.accountIsType(account, neonUtil.LEAD_TYPE) or neonUtil.accountIsType(account, neonUtil.DIRECTOR_TYPE):
            leadershipMembers.add(dID)

        if neonUtil.accountIsType(account, neonUtil.STEWARD_TYPE) or neonUtil.accountIsType(account, neonUtil.SUPER_TYPE):
            stewardsMembers.add(dID)

        if neonUtil.accountIsType(account, neonUtil.INSTRUCTOR_TYPE):
            instructorsMembers.add(dID)

        if neonUtil.accountIsType(account, neonUtil.WIKI_ADMIN_TYPE):
            wikiAdmins.add(dID)

    #Discourse is annoying about primary groups - there's no way to set a heirarchy; it's last-one-sticks
    #Update the "highest rank" group last so users new to multiple groups wind up with the highest title
    discourseUtil.setGroupMembers(list(wikiAdmins), discourseUtil.GROUP_WIKI_ADMINS)
    discourseUtil.setGroupMembers(list(stewardsMembers), discourseUtil.GROUP_STEWARDS)
    #haven't actually decided on a Discourse group for instructors yet
    #discourseUtil.setGroupMembers(list(instructorsMembers), discourseUtil.GROUP_INSTRUCTORS)
    discourseUtil.setGroupMembers(list(leadershipMembers), discourseUtil.GROUP_LEADERSHIP)



def discourseUpdateGroups(neonAccounts: dict):
    #quick sanity check - don't blow away all the groups if this is called with an empty dict
    if len(neonAccounts) == 0:
        logging.error("discourseUpdateGroups() called with empty accounts dict.  aborting.")
        return

    updateMakers(neonAccounts)
    updateTypes(neonAccounts)

#begin standalone script functionality -- pull neonAccounts and call our function
def main():
    neonAccounts = {}

    #For real use, just get neon accounts directly
    #Be aware this takes a long time (2+ minutes)
    neonAccounts = neonUtil.getRealAccounts()
    #neonAccounts = neonUtil.getMembersFast()

    # Testing goes a lot faster if we're working with a cache of accounts
    # with open("Neon/neonAccounts.json") as neonFile:
    #     neonAccountJson = json.load(neonFile)
    #     for account in neonAccountJson:
    #         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

    discourseUpdateGroups(neonAccounts)


# Discourse accounts that were tests, and shouldn't be linked
EXCLUDED_DISCOURSE_USERNAMES = {"janedoe", "testuser"}


# Neon allows multiple accounts to have the same email
# Group by email to make it easier to find collisions
def group_neon_accounts(nAccounts):
    nAccountsByEmail = {}
    for nAccount in nAccounts.values():
        # normalized so a stray capital or space in Neon doesn't hide a match
        email = (nAccount.get("Email 1") or "").strip().lower()
        if not email:
            continue
        if email not in nAccountsByEmail:
            nAccountsByEmail[email] = []
        nAccountsByEmail[email].append(nAccount)
    return nAccountsByEmail


# The one neon account this discourse account belongs to, or None if we can't tell.
# Neon lets several accounts share an email address (households, duplicate records),
# so a shared address falls back to the name on the discourse profile.
def find_matching_neon_account(dAccount, nAccountsByEmail):
    # normalized to match how nAccountsByEmail is keyed
    dEmail = dAccount["email"].strip().lower()
    dName = dAccount["name"] or ""

    emailMatches = nAccountsByEmail.get(dEmail, [])
    if len(emailMatches) == 0:
        # case 0a
        logging.debug(f'Discourse account {dAccount["username"]} {dEmail} matches no neon account. Ignoring it')
        return None
    elif len(emailMatches) == 1: # 1 matched - use it
        # case 0c
        logging.debug(f'Discourse account {dAccount["username"]} {dEmail} uniquely matches neon account {emailMatches[0]["Account ID"]}')
        return emailMatches[0]

    # > 1 matched - find name match. if no unambiguous name match, give up
    nameMatches = [
        na for na in emailMatches if
        na["fullName"].strip().lower() == dName.strip().lower()
    ]
    if len(nameMatches) != 1:
        # case 0b
        logging.warning(f'Cannot find unambiguous match for discourse account {dEmail} found {len(emailMatches)} email matches and {len(nameMatches)} name matches')
        return None
    # case 0d
    logging.debug(f'Discourse account {dAccount["username"]} {dEmail} matches {len(emailMatches)} neon accounts, resolved to neon account {nameMatches[0]["Account ID"]} by name')
    return nameMatches[0]


def update_discourse_ids(nAccounts, dAccounts):
    if not dAccounts:
        # an empty or missing list would read as "every discourse account was deleted"
        logging.error("Fetched no Discourse users; skipping DiscourseID sync.")
        return []

    """
    Update dID field on neon accounts by analyzing all neon and discourse users

    Different cases to handle:
        0. which neon account, if any, a discourse account belongs to
            0a. matches no existing neon accounts -> ignore discourse account, log debug
            0b. could ambiguously match multiple existing neon accounts -> do not use it, warning
            0c. matches exactly one neon account by email -> use it, log debug
            0d. matches several by email but one by name -> use that one, log debug
            0e. is in EXCLUDED_DISCOURSE_USERNAMES -> never link it, log debug
        1. neon account currently has no dID set
            1a. there is a matching discource account -> set dID, log debug
            1b. there is no match -> ignore the neon account, log debug
        2. neon account has dID, but that id doesn't exist in discourse -> remove it from neon account, warning
        3. neon account has dID, and accounts still match -> ignore neon account, log debug
        4. neon account has dID, it exists, but accounts don't match
            4a. neon account matches a different discourse account -> set new dID in neon, warning
            4b. neon account matches no other discourse account, and its discourse id isn't used by any other account -> keep it, log debug
            4c. neon account matches no other discourse account, but its current discourse account now matches a different neon account -> remove it, warning
    """

    nAccountsByEmail = group_neon_accounts(nAccounts)

    # First pass: try to match each discourse account with one neon account
    dMatches = {}
    nMatches = set()
    updates = []
    for dUsername, dAccount in dAccounts.items():
        if dUsername in EXCLUDED_DISCOURSE_USERNAMES:
            # case 0e
            logging.debug(f'Discourse account {dUsername} is excluded from matching. Ignoring it')
            continue

        nAccount = find_matching_neon_account(dAccount, nAccountsByEmail)
        if nAccount is None:
            # cases 0a and 0b
            continue

        nAccountID = nAccount["Account ID"]
        nDiscourseID = nAccount.get("DiscourseID")
        nEmail = nAccount.get("Email 1")

        dMatches[dUsername] = nAccountID
        nMatches.add(nAccountID)

        if not nDiscourseID:
            # case 1a
            logging.debug(f'Neon account {nAccountID} {nEmail} had no discourseID, but now matches {dUsername}. Updating it')
            updates.append((nAccount, dUsername))
        elif nDiscourseID != dUsername:
            # case 4a
            logging.warning(f'Neon account {nAccountID} had discourseID {nDiscourseID} but now matches {dUsername}. Updating it')
            updates.append((nAccount, dUsername))
        else:
            # case 3
            logging.debug(f'Neon account {nAccountID} {nEmail} already has the correct discourseID {nDiscourseID}. Leaving it')

    # Second pass: Check all unmatched neon accounts
    allDiscourseUsernames = set(dAccounts)
    for nAccountID, nAccount in nAccounts.items():
        if nAccountID in nMatches:
            # Already matched the account in the first pass
            continue

        nDiscourseID = nAccount.get("DiscourseID")
        nEmail = nAccount.get("Email 1")

        if nDiscourseID:
            if nDiscourseID not in allDiscourseUsernames:
                # case 2
                logging.warning(f"Neon account {nAccountID} had discourseID {nDiscourseID} but that ID doesn't exist in discourse anymore, so removing it")
                updates.append((nAccount, ""))
            elif nDiscourseID in dMatches:
                # case 4c
                otherNeonAccountID = dMatches[nDiscourseID]
                otherNeonEmail = nAccounts[otherNeonAccountID].get("Email 1")
                logging.warning(f"Neon account {nAccountID} {nEmail} had discourseID {nDiscourseID}, but that discourse account now matches a different neon account {otherNeonAccountID} {otherNeonEmail}, so removing it from {nAccountID}")
                updates.append((nAccount, ""))
            else:
                # case 4b
                dAccount = dAccounts[nDiscourseID]
                dEmail = dAccount['email']
                logging.debug(f"Neon account {nAccountID} {nEmail} has discourseID {nDiscourseID} {dEmail} but the accounts no longer match. Keeping it anyway, since that discourse account doesn't match any other neon account right now.")
        else:
            # case 1b
            logging.debug(f'Neon account {nAccountID} {nEmail} has no discourseID and matches no discourse account. Leaving it')

    return updates


def run_update_discourse_ids(dry_run=True):
    neonAccounts = neonUtil.getRealAccounts()
    discourseAccounts = discourseUtil.getActiveUsers()
    updates = update_discourse_ids(neonAccounts, discourseAccounts)
    if not dry_run:
        neonUtil.batchUpdateDIDs(updates)
    return updates


if __name__ == "__main__":
    # main()
    run_update_discourse_ids()
