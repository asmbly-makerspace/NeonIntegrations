################## Asmbly NeonCRM & Gmail API Integrations ##################
#   Neon API docs - https://developer.neoncrm.com/api-v2/                   #
#  Gmail API docs - https://developers.google.com/gmail/api/reference/rest  #
#############################################################################
#############################################################################
#  This helper script grabs Event data from Neon and cross references a     #
#  json file with a list of all classes Asmbly offers and their expected    #
#  frequency. Sends daily email to education@asmbly.org with latest         #
#  scheduled class date for each class.                                     #                        
#############################################################################

# Outside of the following imports, this script relies on classes.json file 
# containing class names and frequencies which is expected in the same directory
# as this script.

# Run daily as cronjob on AWS EC2 instance

from pprint import pprint
import json
import base64
import datetime

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

import helpers.neon as neon

today = datetime.date.today()
#deltaDays = today + datetime.timedelta(days=90)
searchFields = f'''
[
    {{
        "field": "Event End Date",
        "operator": "GREATER_THAN",
        "value": "{today}"
    }},
    {{
        "field": "Event Archived",
        "operator": "EQUAL",
        "value": "No"
    }}
]
'''
outputFields = '''
[
    "Event Name", 
    "Event Topic",
    "Event Start Date",
    "Event End Date"
]
'''

responseEvents = neon.postEventSearch(searchFields, outputFields)['searchResults']


# Import classes info
classesInfo = "classes.json"
classesInfo = json.loads(open(classesInfo).read())

#pprint(responseEvents["searchResults"])

#Find the latest scheduled class and number of scheduled classes for each class in classes.json
def latestClasses(classesInfo: dict) -> dict:
    #create dict of list of dicts sorting all events into class types 
    sortedClassDict = {}
    for item in classesInfo:
        indClassList = [event for event in responseEvents if item in event['Event Name']]
        dictOfIndClassList = {item: indClassList}
        sortedClassDict.update(dictOfIndClassList)

    #create dict of lists with all currently scheduled dates for each class
    classDates = {}
    for key,value in sortedClassDict.items():
        dates = [event['Event Start Date'] for event in value]
        classDates.update({key:dates})

    #take list of date strings, convert each to datetime, find latest and convert result back to string
    def latestDate(dateList: list) -> list:
        if dateList:
            datetimeDates = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in dateList]
            datetimeDates.sort(reverse = True)
           
            latestDate = datetime.datetime.strftime(datetimeDates[0], '%m-%d-%y')
            deltaDays = datetimeDates[0] - today
            deltaDays = deltaDays.days
            
        else:
            latestDate = "None Scheduled"
            deltaDays = 0
        
        return [latestDate, deltaDays]

    latestDates = {className: [latestDate(dates)[0], latestDate(dates)[1], len(dates)] for className, dates in classDates.items()}

    return latestDates


classes = latestClasses(classesInfo)

htmlText = ""

for k,v in classes.items():
    if 10 <= v[1] < 30:
        style = 'style = "color:orange; text-align:center; padding: 5px 15px 5px 15px"'
    elif v[1] < 10:
        style = 'style = "color:red; text-align:center; padding: 5px 15px 5px 15px"'
    else:
        style = 'style = "text-align:center; padding: 5px 15px 5px 15px"'

    text = f'''
    <tr>
        <td style="text-align:center; padding: 5px 15px 5px 15px">{k}</td>
        <td {style}>{v[0]}</td>
        <td {style}>{v[1]}</td>
        <td style="text-align:center; padding: 5px 15px 5px 15px">{v[2]}</td>
    </tr>
    '''       
    htmlText += text

##### GMAIL #####
# # Reformat date for email subject
formattedToday = today.strftime('%B %d')

# Compose email
emailMsg = f'''
<html>
    <body>
        <p>
            This is an automated email tracking the latest scheduled class for every class offered at Asmbly.
        </p>
        <table>
            <tr>
                <th style="text-align:center; padding: 5px 15px 5px 15px">Class Name</th>
                <th style="text-align:center; padding: 5px 15px 5px 15px">Latest Scheduled</th>
                <th style="text-align:center; padding: 5px 15px 5px 15px">Days Away</th>
                <th style="text-align:center; padding: 5px 15px 5px 15px">Number Scheduled</th>
            </tr>
            {htmlText}
        </table
        <p>
            Thanks!<br>
            Asmbly AdminBot
        </p>
    </body>
</html>
    '''
#print(emailMsg)

mimeMessage = MIMEMultipart()
mimeMessage['to'] = 'education@asmbly.org'
mimeMessage['subject'] = f'Currently Scheduled Classes - {formattedToday}'
mimeMessage.attach(MIMEText(emailMsg, 'html'))
raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

sendMIMEmessage(mimeMessage)