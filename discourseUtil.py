########### Asmbly NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#      Discourse API docs - https://docs.discourse.org/         #
################################################################

from pprint import pformat
import requests
import logging
from config import D_APIkey, D_APIuser

### Discourse Account Info
from config import D_APIkey, D_APIuser
D_baseURL = 'https://yo.asmbly.org'
D_headers = {'Api-Key':D_APIkey,'Api-Username':D_APIuser}

#testing flag.  this should probably be a command-line arguement
dryRun = False

#Discourse Group IDs
# 42 = haxor
# 45 = haxorcommunity

####################################################################
# return all haxors currently in Discourse
####################################################################
def getHaxors():
    haxors = {}
    resourcePath = '/groups/haxor/members.json'
    limit = 50
    offset = 0
    total = 0
    data = ''
    while offset + limit <= total+limit:
        url = D_baseURL + resourcePath + "?limit="+str(limit)+"&offset="+str(offset)
        response = requests.get(url, headers=D_headers)
        offset += limit
        logging.debug(pformat(response.json().get("meta")))
        total = int(response.json().get("meta")["total"])
        for member in response.json().get("members"):
            #print(haxor["username"]+" is a haxor")
            haxors[member["username"]] = member
    return haxors

####################################################################
# Add one or more Discourse users to haxors, remove from haxorcommunity
####################################################################
def addHaxors(addHaxor):
    if addHaxor == "":
        return 

    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    
    #print("Adding hax0rs: "+str(data))
    if not dryRun:
        updateResponse = requests.put(url, data={'usernames': addHaxor}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames - means we picked up an invalid discourse username somewhere

    #Step 2c: remove them from HaxorCommunity
    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    #print("Removing HaxorCommunity: "+str(data))
    if not dryRun:
        deleteResponse = requests.delete(url, data={'usernames': addHaxor}, headers=D_headers)
        #pprint(deleteResponse)
        #don't bother with skipped usernames here - anyone who isn't a lapsed members will fail to remove from haxorcommunity

####################################################################
# Remove one or more Discourse users from haxors, add to haxorcommunity
####################################################################
def removeHaxors(removeHaxor):
    if removeHaxor == "":
        return

    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    #print("Adding hax0rCommunity: "+str(data))
    if not dryRun:
        updateResponse = requests.put(url, data={'usernames': removeHaxor}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

    #Step 2c: remove them from Haxors
    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    #print("Removing Haxors: "+str(data))
    if not dryRun:
        deleteResponse = requests.delete(url, data={'usernames': removeHaxor}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

