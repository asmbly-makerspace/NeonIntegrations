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
# 42 = makers
# 45 = community

####################################################################
# return all makers currently in Discourse
####################################################################
def getMakers():
    makers = {}
    limit = 50
    offset = 0
    total = 0
    while offset + limit <= total+limit:
        url = D_baseURL + '/groups/makers/members.json' + "?limit="+str(limit)+"&offset="+str(offset)
        print(f'''fetching from {url}''')
        response = requests.get(url, headers=D_headers)
        offset += limit
        logging.debug(pformat(response.json().get("meta")))
        total = int(response.json().get("meta")["total"])
        for member in response.json().get("members"):
            #print(makers["username"]+" is a maker")
            makers[member["username"]] = member
    return makers

####################################################################
# Add one or more Discourse users to makers, remove from Asmbly Community
####################################################################
def promoteMakers(makers):
    if makers == "":
        return 

    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    
    #print("Adding makers: "+str(data))
    if not dryRun:
        updateResponse = requests.put(url, data={'usernames': makers}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames - means we picked up an invalid discourse username somewhere

    #Step 2c: remove them from Asmbly Community
    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    #print("Removing from Community: "+str(data))
    if not dryRun:
        deleteResponse = requests.delete(url, data={'usernames': makers}, headers=D_headers)
        #pprint(deleteResponse)
        #don't bother with skipped usernames here - anyone who isn't a lapsed members will fail to remove from community

####################################################################
# Remove one or more Discourse users from makers, add to Asmbly Community
####################################################################
def demoteMakers(makers):
    if makers == "":
        return

    resourcePath = '/groups/45/members.json'
    url = D_baseURL + resourcePath
    #print("Adding Community: "+str(data))
    if not dryRun:
        updateResponse = requests.put(url, data={'usernames': makers}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

    #Step 2c: remove them from Makers
    resourcePath = '/groups/42/members.json'
    url = D_baseURL + resourcePath
    #print("Removing Makers: "+str(data))
    if not dryRun:
        deleteResponse = requests.delete(url, data={'usernames': makers}, headers=D_headers)
        #pprint(updateResponse)
        #TODO check for skipped usernames... not sure how it'd happen.  definitely exception time.

