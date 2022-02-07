#!/usr/bin/env python3
########### ATXHS NeonCRM & Discourse API Integrations ############
#      Neon API docs - https://developer.neoncrm.com/api-v2/     #
#################################################################
#################################################################
#  This helper script cleans up our Events page in the backend  #
#  of Neon.  The default view shows all active events.          #
#  Currently is no way to automatically move past events to     #
#  archived within the product...                               #
#       ... this script is our solution for that.               #
#################################################################

from pprint import pprint
import requests
import json
import base64
import time
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# from Google import Create_Service
from config import N_APIkey, N_APIuser
from helpers.gmail import sendMIMEmessage

# mimeMessage = MIMEMultipart()
# mimeMessage['to'] = "valerie@asmbly.org"
# mimeMessage['cc'] = "vlarie213@gmail.com"
# mimeMessage['subject'] = f'Testing'
# mimeMessage.attach(MIMEText("Test", 'plain'))
# sendMIMEmessage(mimeMessage)


# Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}


# # ## Gmail service creation
# # CLIENT_SECRET_FILE = 'credentials.json'
# # API_NAME = 'gmail'
# # API_VERSION = 'v1'
# # SCOPES = ['https://mail.google.com/']

# # service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)


## Helper function for API calls
def apiCall(httpVerb, url, data, headers):
    # Make request
    if httpVerb == 'GET':
        response = requests.get(url, data=data, headers=headers)
    elif httpVerb == 'POST':
        response = requests.post(url, data=data, headers=headers)
    elif httpVerb == 'PUT':
        response = requests.put(url, data=data, headers=headers)
    elif httpVerb == 'PATCH':
        response = requests.patch(url, data=data, headers=headers)
    elif httpVerb == 'DELETE':
        response = requests.delete(url, data=data, headers=headers)
    else:
        print(f"HTTP verb {httpVerb} not recognized")

    # These lines break the code for PATCH requests
    # response = response.json()
    # pprint(response)

    return response


# # ##### NEON #####
# # # Get list of custom fields for events
# # httpVerb = 'GET'
# # resourcePath = '/customFields'
# # queryParams = '?category=Event'
# # data = ''

# # url = N_baseURL + resourcePath + queryParams
# # responseFields = apiCall(httpVerb, url, data, N_headers).json()
# # print("### CUSTOM FIELDS ###\n")
# # pprint(responseFields)


##### NEON #####
# Get list of custom fields for events
httpVerb = 'GET'
resourcePath = '/properties/eventCategories'
queryParams = ''
data = ''

url = N_baseURL + resourcePath + queryParams
responseCategories = apiCall(httpVerb, url, data, N_headers).json()
# print("### CUSTOM FIELDS ###\n")
# pprint(responseCategories)

# categories = list(filter(lambda cat:cat["status"] == "ACTIVE", responseCategories))
# Make a list of active event categories
categories = []
for cat in responseCategories:
    if cat["status"] == "ACTIVE":
        categories.append(cat["name"])
# print(categories)


# # ##### NEON #####
# # # Get possible search fields for POST to /events/search
# # httpVerb = 'GET'
# # resourcePath = '/events/search/searchFields'
# # queryParams = ''
# # data = ''
# # # Event Category

# # url = N_baseURL + resourcePath + queryParams
# # print("### SEARCH FIELDS ###\n")
# # responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()
# # pprint(responseSearchFields)


# # ##### NEON #####
# # # Get possible output fields for POST to /events/search
# # httpVerb = 'GET'
# # resourcePath = '/events/search/outputFields'
# # queryParams = ''
# # data = ''

# # url = N_baseURL + resourcePath + queryParams
# # print("### OUTPUT FIELDS ###\n")
# # responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()
# # pprint(responseOutputFields)

monthDays = {
    1  : 31,
    2  : 28,
    3  : 31,
    4  : 30,
    5  : 31,
    6  : 30,
    7  : 31,
    8  : 31,
    9  : 30,
    10 : 31,
    11 : 30,
    12 : 31
}

##### NEON #####
# Get events happening this month and next month
today = date.today()

# Get variables for this month
thisMonth = today.month
thisYear = today.year
thisMonthStart = today.replace(day=1)
thisMonthEnd = today.replace(day=monthDays[thisMonth])

# Get variables for next month, accounting for potential year wrap
nextMonth = (today + relativedelta(months=+1)).month
nextMonthYear = thisYear
if nextMonth == 1:
    nextMonthYear += 1
nextMonthStart = today.replace(month=nextMonth).replace(day=1).replace(year=nextMonthYear)
nextMonthEnd = today.replace(month=nextMonth).replace(day=monthDays[nextMonth]).replace(year=nextMonthYear)


# future = today + timedelta(days=45)

# print(f"TODAY IS {today}")
# print(f"MONTH IS {thisMonth}")
# print(f"THIS MONTH IS {thisMonthStart}")
# print(f"THIS MONTH END IS {thisMonthEnd}")
# print(f"NEXT MONTH IS {nextMonthStart}")
# print(f"NEXT MONTH END IS {nextMonthEnd}")


# def getMonthEvents(monthStart, monthEnd, monthName):
def getMonthEvents(monthStart, monthEnd):
    ### Events for this month
    httpVerb = 'POST'
    resourcePath = '/events/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": [
            {{
                "field": "Event Start Date",
                "operator": "GREATER_AND_EQUAL",
                "value": "{monthStart}"
            }},
            {{
                "field": "Event Start Date",
                "operator": "LESS_AND_EQUAL",
                "value": "{monthEnd}"
            }}
        ],
        "outputFields": [
            "Event Name", 
            "Event ID",
            "Event Archive",
            "Event Category Name",
            "Event Topic",
            "Event Start Date",
            "Event Start Time",
            "Event End Date",
            "Event End Time",
            "Event Capacity",
            "Event Registration Attendee Count"
        ],
        "pagination": {{
        "currentPage": 0,
        "pageSize": 200
        }}
    }}
    '''

    url = N_baseURL + resourcePath + queryParams
    thisMonthName = monthStart.strftime("%B")
    responseEvents_ThisMonth = apiCall(httpVerb, url, data, N_headers).json()

    # pprint(responseEvents_ThisMonth)

    reportData_ThisMonth = f"Class counts for {thisMonthName}:"
    warnings = ""

    for cat in categories:
        events = list(filter(lambda x:cat in x["Event Category Name"], responseEvents_ThisMonth["searchResults"]))
        data = ""
        classes = {}
        for event in events:
            classes[event['Event Start Date']] = {
                "Capacity" : event["Event Capacity"],
                "Registered" : event["Event Registration Attendee Count"],
                "Name" : event["Event Name"],
                "Time" : event["Event Start Time"]
            }
        if len(events) > 0:
            sortedDates = sorted(classes)
            catInfo = ""
            for eventDate in sortedDates:
                eventDateFormatted = datetime.strptime(eventDate, "%Y-%m-%d")
                prettyDate = eventDateFormatted.strftime("%a, %-m/%-d")
                eventReg = ""
                cap = int(classes[eventDate]["Capacity"])
                reg = int(classes[eventDate]["Registered"])
                tim = classes[eventDate]["Time"]
                nam = classes[eventDate]["Name"]
                print(classes)

                if cap <= reg:
                    eventReg = f"FULL ({reg}/{cap})"
                elif reg == "0":
                    eventReg = f"EMPTY ({reg}/{cap})"
                else:
                    eventReg = f"{reg}/{cap}"
                catInfo += f"\n\t\t{prettyDate}: {nam} {tim}"
            data = f"\n\n\t{cat}:  {len(events)} classes{catInfo}"

        elif cat == "Miscellaneous":
            print(f"Skipping {cat}")
            continue
        else:
            warnings += f"\n\tWARNING!  No upcoming events scheduled for {cat}."
        reportData_ThisMonth += data

    return reportData_ThisMonth + "\n" + warnings

eventsThisMonth = getMonthEvents(thisMonthStart, thisMonthEnd)
eventsNextMonth = getMonthEvents(nextMonthStart, nextMonthEnd)



##### GMAIL #####
# Reformat date for email subject
# formattedToday = today.strftime('%B %d')
# formattedFuture = future.strftime('%B %d')

# Compose email
emailMsg = f'''
This is an automated email report summarizing the Asmbly class schedule for this month and the following.

__________

{eventsThisMonth}

__________

{eventsNextMonth}

'''

print(emailMsg)
# # mimeMessage = MIMEMultipart()
# # mimeMessage['to'] = "board@asmbly.org"
# # mimeMessage['cc'] = "classes@asmbly.org"
# # mimeMessage['subject'] = f'Neon Class Report: {formattedToday} to {formattedFuture}'
# # mimeMessage.attach(MIMEText(emailMsg, 'plain'))
# # raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

# # message = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
# # print(message)