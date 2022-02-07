################## Asmbly NeonCRM & Gmail API Integrations ##################
#   Neon API docs - https://developer.neoncrm.com/api-v2/                   #
#  Gmail API docs - https://developers.google.com/gmail/api/reference/rest  #
#############################################################################
#############################################################################
#  This helper script grabs Event data from Neon and cross references a     #
#  json file with teachers' email addresses in order to send reminder       #
#  emails each week about scheduled classes.                                #
#############################################################################

from pprint import pprint
import requests
import json
import base64
import time
import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from Google import Create_Service
from config import N_APIkey, N_APIuser


## Neon Account Info
N_auth = f'{N_APIuser}:{N_APIkey}'
N_baseURL = 'https://api.neoncrm.com/v2'
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {'Content-Type':'application/json','Authorization': f'Basic {N_signature}', 'NEON-API-VERSION': '2.1'}


# ## Gmail service creation
# CLIENT_SECRET_FILE = 'credentials.json'
# # CLIENT_SECRET_FILE = 'token.json'
# API_NAME = 'gmail'
# API_VERSION = 'v1'
# SCOPES = ['https://mail.google.com/']

# service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)


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


###########################################################################
################    Helpful code for getting field info    ################
###########################################################################

# ##### NEON #####
# # Get list of custom fields for events
# httpVerb = 'GET'
# resourcePath = '/customFields'
# queryParams = '?category=Events'
# data = ''

# url = N_baseURL + resourcePath + queryParams
# responseCustomFields = apiCall(httpVerb, url, data, N_headers)
# response = responseCustomFields.json()
# print("### CUSTOM FIELDS ###\n")
# pprint(response)


# ##### NEON #####
# # Get possible search fields for POST to /events/search
# httpVerb = 'GET'
# resourcePath = '/events/search/searchFields'
# queryParams = ''
# data = ''
# # Event Category

# url = N_baseURL + resourcePath + queryParams
# responseSearchFields = apiCall(httpVerb, url, data, N_headers)
# response = responseSearchFields.json()
# print("### SEARCH FIELDS ###\n")
# pprint(response)


# ##### NEON #####
# # Get possible output fields for POST to /events/search
# httpVerb = 'GET'
# resourcePath = '/events/search/outputFields'
# queryParams = ''
# data = ''

# url = N_baseURL + resourcePath + queryParams
# responseOutputFields = apiCall(httpVerb, url, data, N_headers)
# response = responseOutputFields.json()
# print("### OUTPUT FIELDS ###\n")
# pprint(response)




###########################################################################
########################    Time to do the work    ########################
###########################################################################

##### NEON #####
# Get events for the next 10 days
today = datetime.date.today()
tenDays = today + datetime.timedelta(days=10)
print(f"Date range is {today} thru {tenDays}")

httpVerb = 'POST'
resourcePath = '/events/search'
queryParams = ''
data = f'''
{{
    "searchFields": [
        {{
            "field": "Event End Date",
            "operator": "GREATER_THAN",
            "value": "{today}"
        }},
        {{
            "field": "Event End Date",
            "operator": "LESS_THAN",
            "value": "{tenDays}"
        }},
        {{
            "field": "Event Archived",
            "operator": "EQUAL",
            "value": "No"
        }}
    ],
    "outputFields": [
        "Event Name", 
        "Event ID",
        "Event Topic",
        "Event Start Date",
        "Event Start Time",
        "Event End Date",
        "Event End Time",
        "Registrants",
        "Hold To Waiting List",
        "Waiting List Status"
    ],
    "pagination": {{
    "currentPage": 0,
    "pageSize": 200
    }}
}}
'''

url = N_baseURL + resourcePath + queryParams
responseEvents = apiCall(httpVerb, url, data, N_headers).json()
# print("### UPCOMING EVENTS ###\n")
# pprint(responseEvents)

# Remove duplicates in the list of teachers
rawTeachers = [item.get("Event Topic") for item in responseEvents["searchResults"]]
teachers = []
[teachers.append(teacher) for teacher in rawTeachers if teacher not in teachers]
print(f"Teachers for the next 10 days: {teachers}")

# Import teacher contact info
contactInfo = "teachers.json"
teacherEmails = json.loads(open(contactInfo).read())

# For use if script ran and failed to complete
alreadySent = [
    # "Greg Raines",
    # "Charlie Staley",
    # "Danny Miller",
    # "Matt Mancuso",
    # "Bryan Ribas",
    # "Stephen Loftus-Mercer",
    # "Doug Squires",
    # "George Mossessian",
    # "James McNees",
    # "Josh Cross",
    # "Scott Wynd",
    # "Joe Ngo",
    # "Billy Nelson",
    # "Keiarra Ortiz-Cedeno"
]



# Begin gathering data for emailing each teacher
# Send each teacher an email reminder about classes they are scheduled to teach
for teacher in teachers:
    if teacher == None:
        print("WARNING:  No teacher assigned!")
        teacherEmails[None] = "board@asmbly.org"
    if teacher in alreadySent:
        print(f"Already emailed {teacher}")
        continue

    # Find all events for each teacher
    events = list(filter(lambda x:x["Event Topic"]==teacher,responseEvents["searchResults"]))
    print(f"\n\n_____\n\nEmailing {teacher} about {len(events)} event(s)...")
    sortedEvents = sorted(events, key = lambda x:datetime.datetime.fromisoformat(x["Event Start Date"]))

    # Reformat event data so it looks nice in email
    prettyEvents = ""
    for event in sortedEvents:
        eventId = event["Event ID"]

        # GET registrations for a single event
        httpVerb = 'GET'
        resourcePath = f'/events/{eventId}/eventRegistrations'
        queryParams = ''
        # queryParams = '?page=0'
        data = ''
        
        url = N_baseURL + resourcePath + queryParams
        individualEvent = apiCall(httpVerb, url, data, N_headers).json()
        # print("### EVENT REGISTRANTS ###\n")
        # pprint(individualEvent)

        # Declare empty variables that may or may not get filled depending on whether there are registrations
        registrants = {}
        studentInfo = {}
        prettyRegistrants = ""

        # Only add info if there are registrations
        if (int(event["Registrants"]) > 0):
            # Iterate over response to add registrant account IDs to dictionary organized by registration status
            for registrant in individualEvent["eventRegistrations"]:
                status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
                if status in registrants.keys():
                    registrants[status].append(registrant["registrantAccountId"])
                else:
                    registrants.update({status: [registrant["registrantAccountId"]]})
                
            # Get email addresses for each successful registrant
            for id in registrants["SUCCEEDED"]:
                ##### NEON #####
                httpVerb = 'GET'
                resourcePath = f'/accounts/{id}'
                queryParams = ''
                data = ''

                url = N_baseURL + resourcePath + queryParams
                responseAccount = apiCall(httpVerb, url, data, N_headers).json()
                # pprint(responseAccount)

                # Add to email address list
                name = f'{responseAccount["individualAccount"]["primaryContact"]["firstName"]} {responseAccount["individualAccount"]["primaryContact"]["lastName"]}'
                email = responseAccount["individualAccount"]["primaryContact"]["email1"]
                try:
                    phone = responseAccount["individualAccount"]["primaryContact"]["addresses"][0]["phone1"]
                except KeyError:
                    phone = responseAccount["individualAccount"]["primaryContact"]["addresses"][1]["phone1"]

                studentInfo[name] = {"email" : email, "phone" : phone}

            # Format email addresses for pretty printing in email body
            # for k,v in emails.items():
            for k,v in studentInfo.items():
                student = f"{k}:  {v['email']}, {v['phone']}"
                prettyRegistrants += f"\t{student}\n\t"

        rawTime = event["Event Start Time"]
        startTime = datetime.datetime.strptime(rawTime,'%H:%M:%S').strftime('%I:%M %p')
        info = f'''
        {event["Event Name"]}
        Date: {event["Event Start Date"]}
        Time: {startTime}
        Number of registrants: {event["Registrants"]}
            {prettyRegistrants}
        '''
        prettyEvents += info
        

    ##### GMAIL #####
    # Reformat date for email subject
    formattedToday = today.strftime('%B %d')

    # Compose email
    emailMsg = f'''
Hi {teacher},

This is an automated email to remind you of the upcoming classes you are scheduled to teach at Asmbly.
Thank you for sharing your knowledge with the community!

{prettyEvents}

Please note these are the registrations as of the time of this email and may not reflect final registrations for your class.
You can see more details about these events and registrants in your Neon backend account.  
The login URL is https://atxhs.z2systems.com/np/admin/content/contentList.do
Email classes@asmbly.org if you have any questions about the above schedule.

Thanks again!
Asmbly Bot
    '''
    print(emailMsg)
    # mimeMessage = MIMEMultipart()
    # mimeMessage['to'] = teacherEmails[teacher]
    # mimeMessage['cc'] = "classes@asmbly.org"
    # mimeMessage['subject'] = f'Your upcoming classes at Asmbly - week of {formattedToday}'
    # mimeMessage.attach(MIMEText(emailMsg, 'plain'))
    # raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

    # message = service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
    # print(message)