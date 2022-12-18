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

    #Step 1: find all Neon accounts that are paid up, have a DiscourseID, and aren't in Makers
    addMakers = set()
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
            addMakers.add(f'{dID}')

    #promote new Makers -- add to Makers, remove from Community (which may fail, but that's OK)
    discourseUtil.removeGroupMembers(list(addMakers), discourseUtil.GROUP_COMMUNITY)
    discourseUtil.addGroupMembers(list(addMakers), discourseUtil.GROUP_MAKERS)

    #step 2 : remove makers without an active membership
    removeMakers = set()
    for maker in makers:
        remove = True
        for account in neonAccounts:
            if maker == neonAccounts[account].get("DiscourseID") and (neonAccounts[account].get("validMembership") or neonUtil.accountIsType(neonAccounts[account], neonUtil.FRESHBOOKS_TYPE)):
                    remove = False

        if remove:
            logging.info(maker+" ("+makers[maker]["name"]+") used to be a subscriber but is no longer")
            removeMakers.add(f'{maker}')

    #demote expired or otherwise inactive Makers -- remove from Makers, add to Community
    discourseUtil.removeGroupMembers(list(removeMakers), discourseUtil.GROUP_MAKERS)
    discourseUtil.addGroupMembers(list(removeMakers), discourseUtil.GROUP_COMMUNITY)


def updateTypes(neonAccounts: dict):
    #using sets for these to pevent duplicate entries
    coworkingMembers= set()
    leadershipMembers = set()
    stewardsMembers = set()
    instructorsMembers = set()
    wikiAdmins = set()

    for account in neonAccounts:
        if neonAccounts[account].get("DiscourseID") is None or neonAccounts[account].get("DiscourseID") == "":
            if neonUtil.accountIsAnyType(neonAccounts[account]):
                logging.warning(f'''{neonAccounts[account]["First Name"]} {neonAccounts[account]["Last Name"]} ({neonAccounts[account]["Account ID"]}) is interesting but has no Discourse ID''')
            continue

        if neonUtil.accountIsType(neonAccounts[account], neonUtil.LEADER_TYPE):
            leadershipMembers.add(neonAccounts[account].get("DiscourseID"))

        if neonUtil.accountIsType(neonAccounts[account], neonUtil.COWORKING_TYPE):
            coworkingMembers.add(neonAccounts[account].get("DiscourseID"))

        if neonUtil.accountIsType(neonAccounts[account], neonUtil.STEWARD_TYPE) or neonUtil.accountIsType(neonAccounts[account], neonUtil.SUPER_TYPE):
            stewardsMembers.add(neonAccounts[account].get("DiscourseID"))

        if neonUtil.accountIsType(neonAccounts[account], neonUtil.INSTRUCTOR_TYPE):
            instructorsMembers.add(neonAccounts[account].get("DiscourseID"))

        if neonUtil.accountIsType(neonAccounts[account], neonUtil.WIKI_ADMIN_TYPE):
            wikiAdmins.add(neonAccounts[account].get("DiscourseID"))

    #Discourse is annoying about primary groups - there's no way to set a heirarchy; it's last-one-sticks
    #Update the "highest rank" group last so users new to multiple groups wind up with the highest title
    discourseUtil.setGroupMembers(list(wikiAdmins), discourseUtil.GROUP_WIKI_ADMINS)
    discourseUtil.setGroupMembers(list(coworkingMembers), discourseUtil.GROUP_COWORKING)
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

if __name__ == "__main__":
    main()
