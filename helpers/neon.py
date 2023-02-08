from pprint import pprint
import base64

from config import N_APIkey, N_APIuser
from helpers.api import apiCall


# Neon Account Info
N_auth      = f'{N_APIuser}:{N_APIkey}'
N_baseURL   = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers   = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}'}



###########################
#####   NEON EVENTS   #####
###########################

# Get list of custom fields for events
def getEventCustomFields():
    httpVerb = 'GET'
    resourcePath = '/customFields'
    queryParams = '?category=Event'
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseEventFields = apiCall(httpVerb, url, data, N_headers).json()
    # print("### CUSTOM FIELDS ###\n")
    # pprint(responseFields)

    return responseEventFields


# Get list of event categories
def getEventCategories():
    httpVerb = 'GET'
    resourcePath = '/properties/eventCategories'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseCategories = apiCall(httpVerb, url, data, N_headers).json()

    return responseCategories


# Filter event categories to active only
def getEventActiveCategories(responseCategories):
    categories = list(filter(lambda cat:cat["status"] == "ACTIVE", responseCategories))
    
    return categories


# Get a list of active event category names
def getEventActiveCatNames(responseCategories):
    categories = []
    for cat in responseCategories:
        if cat["status"] == "ACTIVE":
            categories.append(cat["name"])

    return categories


# Get possible search fields for POST to /events/search
def getEventSearchFields():
    httpVerb = 'GET'
    resourcePath = '/events/search/searchFields'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()
    
    return responseSearchFields


# Get possible output fields for POST to /events/search
def getEventOutputFields():
    httpVerb = 'GET'
    resourcePath = '/events/search/outputFields'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields


# Post search query to get back events (only gets 200 events, pagination not currently supported)
def postEventSearch(searchFields, outputFields):
    httpVerb = 'POST'
    resourcePath = '/events/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": {searchFields},
        "outputFields": {outputFields},
        "pagination": {{
        "currentPage": 0,
        "pageSize": 200
        }}
    }}
    '''

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents

# Get registrations for a single event by event ID
def getEventRegistrants(eventId):
    httpVerb = 'GET'
    resourcePath = f'/events/{eventId}/eventRegistrations'
    queryParams = ''
    # queryParams = '?page=0'
    data = ''
    
    url = N_baseURL + resourcePath + queryParams
    individualEvent = apiCall(httpVerb, url, data, N_headers).json()

    return individualEvent


# Get event registration count (SUCCEEDED status only) from "eventRegistrations" field in individual event
def getEventRegistrantCount(registrantDictionary):
    count = 0
    for registrant in registrantDictionary:
        status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
        if status == "SUCCEEDED":
            tickets = registrant["tickets"][0]["attendees"]
            count+=len(tickets)
    
    return count


# Get individual accounts by account ID
def getAccountIndividual(acctId):
    httpVerb = 'GET'
    resourcePath = f'/accounts/{acctId}'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseAccount = apiCall(httpVerb, url, data, N_headers).json()

    return responseAccount

# Get possible search fields for POST to /orders/search
def getOrderSearchFields():
    httpVerb = 'GET'
    resourcePath = '/orders/search/searchFields'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()
    
    return responseSearchFields


# Get possible output fields for POST to /events/search
def getOrderOutputFields():
    httpVerb = 'GET'
    resourcePath = '/orders/search/outputFields'
    queryParams = ''
    data = ''

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields

# Post search query to get back orders (only gets 200 events, pagination not currently supported)
def postOrderSearch(searchFields, outputFields):
    httpVerb = 'POST'
    resourcePath = '/orders/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": {searchFields},
        "outputFields": {outputFields},
        "pagination": {{
        "currentPage": 0,
        "pageSize": 200
        }}
    }}
    '''

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents
