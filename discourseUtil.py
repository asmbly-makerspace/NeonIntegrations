########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pformat
import requests
import logging
import os

### Discourse Account Info
if os.environ.get("USER") == "ec2-user":
    from aws_ssm import D_APIkey, D_APIuser
else:
    from config import D_APIkey, D_APIuser
D_baseURL = "https://yo.asmbly.org"
D_headers = {"Api-Key": D_APIkey, "Api-Username": D_APIuser}

# testing flag.  this should probably be a command-line arguement
dryRun = False

# Discourse Group names
GROUP_MAKERS = "makers"
GROUP_COMMUNITY = "community"
GROUP_COWORKING = "coworking"
GROUP_LEADERSHIP = "leadership"
GROUP_STEWARDS = "stewards"
GROUP_WIKI_ADMINS = "sysops"

# Discourse Group numeric IDs
GROUP_IDS = {
    GROUP_MAKERS: 42,
    GROUP_COMMUNITY: 45,
    GROUP_COWORKING: 55,
    GROUP_LEADERSHIP: 41,
    GROUP_STEWARDS: 44,
    GROUP_WIKI_ADMINS: 57,
}


####################################################################
# return all members of the given discourse group
####################################################################
def getGroupMembers(groupName: str):
    if GROUP_IDS.get(groupName) is None:
        logging.error(f""""{groupName}" is not a known Discourse group""")
        return {}

    members = {}
    limit = 50
    offset = 0
    total = 0
    while offset + limit <= total + limit:
        url = (
            D_baseURL
            + f"""/groups/{groupName}/members.json"""
            + "?limit="
            + str(limit)
            + "&offset="
            + str(offset)
        )
        print(f"""fetching from {url}""")
        response = requests.get(url, headers=D_headers)
        offset += limit
        logging.debug(pformat(response.json().get("meta")))
        total = int(response.json().get("meta")["total"])
        for member in response.json().get("members"):
            # logging.debug(f'''{members["username"]} is a member of {groupName}''')
            members[member["username"]] = member
    return members


####################################################################
# Add one or more Discourse users to given Discourse group
####################################################################
def addGroupMembers(membersList: list, groupName: str):
    if len(membersList) == 0:
        return

    if GROUP_IDS.get(groupName) is None:
        logging.error(f""""{groupName}" is not a known Discourse group""")
        return

    resourcePath = f"""/groups/{GROUP_IDS[groupName]}/members.json"""
    url = D_baseURL + resourcePath

    logging.info(f"""Adding members to {groupName}: {','.join(membersList)}""")
    if not dryRun:
        updateResponse = requests.put(
            url, data={"usernames": ",".join(membersList)}, headers=D_headers
        )
        # pprint(updateResponse)
        # TODO: check response for skipped usernames.  For now assume callers are checking for valid discourse IDs


####################################################################
# Remove one or more Discourse users from given Discourse group
####################################################################
def removeGroupMembers(membersList: list, groupName: str):
    if len(membersList) == 0:
        return

    if GROUP_IDS.get(groupName) is None:
        logging.error(f""""{groupName}" is not a known Discourse group""")
        return

    resourcePath = f"""/groups/{GROUP_IDS[groupName]}/members.json"""
    url = D_baseURL + resourcePath

    logging.info(f"""Removing members from {groupName}: {','.join(membersList)}""")
    if not dryRun:
        deleteResponse = requests.delete(
            url, data={"usernames": ",".join(membersList)}, headers=D_headers
        )
        # pprint(deleteResponse)
        # don't bother with skipped usernames here - removing a user who wasn't in the group is a safe No-Op


####################################################################
# Set Discourse group membership by adding and/or removing users
####################################################################
def setGroupMembers(newMembersList: list, groupName: str):
    if GROUP_IDS.get(groupName) is None:
        logging.error(f""""{groupName}" is not a known Discourse group""")

    currentMembersDict = getGroupMembers(groupName)
    currentMembersList = currentMembersDict.keys()

    addMembersList = newMembersList - currentMembersList
    removeMembersList = currentMembersList - newMembersList

    removeGroupMembers(removeMembersList, groupName)
    addGroupMembers(addMembersList, groupName)
