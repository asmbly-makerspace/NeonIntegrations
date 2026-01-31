import base64
import datetime
import os
import requests

if os.environ.get("USER") == "ec2-user":
    from aws_ssm import N_APIkey, N_APIuser
else:
    from config import N_APIkey, N_APIuser

from helpers.api import apiCall


# Neon Account Info
N_auth = f"{N_APIuser}:{N_APIkey}"
N_baseURL = "https://api.neoncrm.com/v2"
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {N_signature}",
}


############################################################################################
#####   NEON EVENTS   ######################################################################
############################################################################################


# Get list of custom fields for events
def getEventCustomFields():
    httpVerb = "GET"
    resourcePath = "/customFields"
    queryParams = "?category=Event"
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseEventFields = apiCall(httpVerb, url, data, N_headers).json()
    # print("### CUSTOM FIELDS ###\n")
    # pprint(responseFields)

    return responseEventFields


# Get list of event categories
def getEventCategories():
    httpVerb = "GET"
    resourcePath = "/properties/eventCategories"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseCategories = apiCall(httpVerb, url, data, N_headers).json()

    return responseCategories


# Filter event categories to active only
def getEventActiveCategories(responseCategories):
    categories = list(filter(lambda cat: cat["status"] == "ACTIVE", responseCategories))

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
    httpVerb = "GET"
    resourcePath = "/events/search/searchFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getEventOutputFields():
    httpVerb = "GET"
    resourcePath = "/events/search/outputFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields


# Post search query to get back events (only gets 200 events, pagination not currently supported)
def postEventSearch(searchFields, outputFields, page=0):
    httpVerb = "POST"
    resourcePath = "/events/search"
    queryParams = ""
    data = {
        "searchFields": searchFields,
        "outputFields": outputFields,
        "pagination": {"currentPage": page, "pageSize": 200},
    }

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents


# Get registrations for a single event by event ID
def getEventRegistrants(eventId):
    httpVerb = "GET"
    resourcePath = f"/events/{eventId}/eventRegistrations"
    queryParams = "?pageSize=30"
    data = ""

    url = N_baseURL + resourcePath + queryParams
    individualEvent = apiCall(httpVerb, url, data, N_headers).json()

    return individualEvent


# Get event registration count (SUCCEEDED status only) from "eventRegistrations" field in individual event
def getEventRegistrantCount(registrantList):
    count = 0
    if type(registrantList) is not type(None):
        for registrant in registrantList:
            status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
            if status == "SUCCEEDED":
                tickets = registrant["tickets"][0]["attendees"]
                count += len(tickets)

    return count


def postEventRegistration(accountID, eventID, accountFirstName, accountLastName):
    httpVerb = "POST"
    resourcePath = "/eventRegistrations"
    queryParams = ""
    data = {
        "id": "string",
        "payments": [
            {
                "id": "string",
                "amount": 0,
                "paymentStatus": "Succeeded",
                "tenderType": 0,
                "receivedDate": datetime.datetime.today().isoformat(),
            }
        ],
        "donorCoveredFeeFlag": False,
        "eventId": eventID,
        "donorCoveredFee": 0,
        "taxDeductibleAmount": 0,
        "sendSystemEmail": True,
        "registrationAmount": 0,
        "ignoreCapacity": False,
        "registrantAccountId": accountID,
        "tickets": [
            {
                "attendees": [
                    {
                        "attendeeId": 0,
                        "accountId": accountID,
                        "firstName": accountFirstName,
                        "lastName": accountLastName,
                        "markedAttended": True,
                        "registrantAccountId": accountID,
                        "registrationStatus": "SUCCEEDED",
                        "registrationDate": datetime.datetime.today().isoformat(),
                    }
                ]
            }
        ],
    }

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents


def getEvent(eventId):
    httpVerb = "GET"
    resourcePath = f"/events/{eventId}"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseEvent = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvent


def cancelClass(registrationId):
    httpVerb = "PATCH"
    resourcePath = f"/eventRegistrations/{registrationId}"
    queryParams = ""
    data = {
        "tickets": [
            {
                "attendees": [
                    {
                        "registrationStatus": "CANCELED",
                    }
                ]
            }
        ]
    }

    url = N_baseURL + resourcePath + queryParams
    responseStatus = apiCall(httpVerb, url, data, N_headers)

    return responseStatus


def getEventTopics():
    httpVerb = "GET"
    resourcePath = f"/properties/eventTopics"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseTopics = apiCall(httpVerb, url, data, N_headers).json()

    return responseTopics


def eventTierCodePatch(classId, tier):
    httpVerb = "PATCH"
    resourcePath = f"/events/{classId}"
    queryParams = ""
    data = {"code": f"Tier {tier}"}

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response


def eventTimePatch(
    classId: str, eventStartTime: str = "hh:mm AM/PM", eventEndTime: str = "hh:mm AM/PM"
):
    httpVerb = "PATCH"
    resourcePath = f"/events/{classId}"
    queryParams = ""
    data = {"eventDates": {"startTime": eventStartTime, "endTime": eventEndTime}}

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response


def eventAttendeeCountPatch(classId: str, maxAttendees: int):
    httpVerb = "PATCH"
    resourcePath = f"/events/{classId}"
    queryParams = ""
    data = {"maximumAttendees": maxAttendees}

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response


def eventNamePatch(classId: str, newName: str):
    httpVerb = "PATCH"
    resourcePath = f"/events/{classId}"
    queryParams = ""
    data = {"name": newName}

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response



############################################################################################
#####   NEON ACCOUNTS   ####################################################################
############################################################################################


# Get individual accounts by account ID
def getAccountIndividual(acctId):
    httpVerb = "GET"
    resourcePath = f"/accounts/{acctId}"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseAccount = apiCall(httpVerb, url, data, N_headers).json()

    return responseAccount


# Get possible search fields for POST to /accounts/search
def getAccountSearchFields():
    httpVerb = "GET"
    resourcePath = "/accounts/search/searchFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getAccountOutputFields():
    httpVerb = "GET"
    resourcePath = "/accounts/search/outputFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields


# Post search query to get back orders (only gets 200 events, pagination not currently supported)
def postAccountSearch(searchFields, outputFields):
    httpVerb = "POST"
    resourcePath = "/accounts/search"
    queryParams = ""
    data = {
        "searchFields": searchFields,
        "outputFields": outputFields,
        "pagination": {"currentPage": 0, "pageSize": 200},
    }

    url = N_baseURL + resourcePath + queryParams
    responseAccounts = apiCall(httpVerb, url, data, N_headers).json()

    return responseAccounts


def getAccountEventRegistrations(neonId):
    httpVerb = "GET"
    resourcePath = f"/accounts/{neonId}/eventRegistrations"
    queryParams = "?sortColumn=registrationDateTime&sortDirection=DESC"
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseAcctEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseAcctEvents


def account_patch(neon_id: int, new_info: dict) -> requests.Response:
    httpVerb = "PATCH"
    resourcePath = f"/accounts/{neon_id}"
    queryParams = ""
    json = {"individualAccount": new_info}

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, json, N_headers)

    return response


def get_acct_by_email(email: str) -> list:
    search_fields = [{"field": "Email", "operator": "EQUAL", "value": email}]

    output_fields = [
        "Account ID",
        "First Name",
        "Last Name",
        "Email 1",
        "Membership Start Date",
        "Individual Type",
        182,
        179,
    ]

    response = postAccountSearch(search_fields, output_fields)

    try:
        search_results = response.get("searchResults")
    except AttributeError:
        search_results = []

    return search_results



############################################################################################
#####   NEON ORDERS   ######################################################################
############################################################################################


# Get possible search fields for POST to /orders/search
def getOrderSearchFields():
    httpVerb = "GET"
    resourcePath = "/orders/search/searchFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getOrderOutputFields():
    httpVerb = "GET"
    resourcePath = "/orders/search/outputFields"
    queryParams = ""
    data = ""

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields


# Post search query to get back orders (only gets 200 events, pagination not currently supported)
def postOrderSearch(searchFields, outputFields):
    httpVerb = "POST"
    resourcePath = "/orders/search"
    queryParams = ""
    data = {
        "searchFields": searchFields,
        "outputFields": outputFields,
        "pagination": {"currentPage": 0, "pageSize": 200},
    }

    url = N_baseURL + resourcePath + queryParams
    responseOrders = apiCall(httpVerb, url, data, N_headers).json()

    return responseOrders