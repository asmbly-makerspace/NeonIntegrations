################## Asmbly NeonCRM & Gmail API Integrations ##################
#   Neon API docs - https://developer.neoncrm.com/api-v2/                   #
#  Gmail API docs - https://developers.google.com/gmail/api/reference/rest  #
#############################################################################
#############################################################################
#  This helper script grabs Event data from Neon and cross references two   #
#  dicts with a list of all classes Asmbly offers and their expected        #
#  frequency. Sends daily email to education@asmbly.org with latest         #
#  scheduled class date for each class.                                     #
#############################################################################

# Run daily as cronjob on AWS EC2 instance

import base64
import datetime
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

import helpers.neon as neon

CORE_CLASSES = {
    "Orientation": 0.33,
    "Woodshop Safety": 0.33,
    "Metal Shop Safety": 0.5,
    "Woodshop Specialty Tools": 2,
    "Metal Lathe": 4,
    "Milling": 3,
    "MIG Welding": 2,
    "TIG Welding": 3,
    "Beginner CNC": 2,
    "Filament 3D Printing": 3,
    "Resin 3D Printing": 3,
    "Wood Lathe": 4,
    "Big Lasers": 1,
    "Small Lasers": 2,
    "Sublimation": 4,
    "Shaper Origin": 1,
    "Stationary Sanders": 4,
}

OTHER_CLASSES = {
    "Bowl Turning": 4,
    "Epoxy Resin": 3,
    "Vinyl Cutter": 4,
    "Round Materials": 2,
    "Microcontrollers": 3,
    "Stained Glass": 4,
    "Serger": 4,
    "Sewing": 4,
}

today = datetime.date.today()
# deltaDays = today + datetime.timedelta(days=90)
searchFields = [
    {"field": "Event End Date", "operator": "GREATER_THAN", "value": today.isoformat()},
    {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
]

outputFields = [
    "Event Name",
    "Event Topic",
    "Event Start Date",
    "Event End Date",
    "Event Registration Attendee Count",
    "Registrants",
    "Event ID",
    "Event Capacity",
]


responseEvents = neon.postEventSearch(searchFields, outputFields)["searchResults"]

# pprint(responseEvents["searchResults"])


# take list of date strings, convert each to datetime, find latest and convert result back to string
def latestDate(dateList: list) -> list:
    if dateList:
        datetimeDates = [
            datetime.datetime.strptime(date, "%Y-%m-%d").date() for date in dateList
        ]
        datetimeDates.sort(reverse=True)

        latestDate = datetime.datetime.strftime(datetimeDates[0], "%m-%d-%y")
        deltaDays = datetimeDates[0] - today
        deltaDays = deltaDays.days

    else:
        latestDate = "None Scheduled"
        deltaDays = 0

    return [latestDate, deltaDays]


# Find the latest scheduled class and number of scheduled classes for each class in classes.json
def latestClasses(classesInfo: dict) -> dict:
    # create dict of dicts sorting all events into class types
    sortedClassDict = {}
    for item in classesInfo:
        indClassList = [
            event for event in responseEvents if item in event["Event Name"]
        ]
        dictOfIndClassList = {item: indClassList}
        sortedClassDict.update(dictOfIndClassList)

    # create dict of lists with all currently scheduled dates for each class
    classDates = {}
    for key, value in sortedClassDict.items():
        dates = [event["Event Start Date"] for event in value]
        isEmpty = False
        earliestAvailable = sys.maxsize
        totalSeatsAvailable = 0
        for event in value:
            if event["Event Registration Attendee Count"] == event["Registrants"]:
                actualRegistrants = int(event["Registrants"])
            else:
                registrants = neon.getEventRegistrants(event["Event ID"]).get(
                    "eventRegistrations"
                )
                actualRegistrants = neon.getEventRegistrantCount(registrants)
            eventCapacity = int(event["Event Capacity"])
            seatsAvailable = eventCapacity - actualRegistrants
            totalSeatsAvailable += seatsAvailable
            timestamp = datetime.datetime.timestamp(
                datetime.datetime.fromisoformat(event["Event Start Date"])
            )
            if seatsAvailable > 0 and timestamp < earliestAvailable:
                earliestAvailable = timestamp

            deltaDays = (
                datetime.datetime.strptime(event["Event Start Date"], "%Y-%m-%d").date()
                - today
            )
            deltaDays = deltaDays.days

            if deltaDays == 1 and actualRegistrants == 0:
                isEmpty = True

        if earliestAvailable != sys.maxsize:
            earliestAvailableDate = datetime.datetime.strftime(
                datetime.datetime.fromtimestamp(earliestAvailable), "%m-%d-%y"
            )
        else:
            earliestAvailableDate = "No Seats Available"

        classDates.update(
            {key: [dates, isEmpty, totalSeatsAvailable, earliestAvailableDate]}
        )

    latestDates = {
        className: [
            latestDate(dates[0])[0],
            latestDate(dates[0])[1],
            len(dates[0]),
            dates[1],
            dates[2],
            dates[3],
        ]
        for className, dates in classDates.items()
    }

    return latestDates


coreClasses = latestClasses(CORE_CLASSES)
otherClasses = latestClasses(OTHER_CLASSES)


def htmlGen(classDict: dict) -> str:
    htmlString = ""
    warning = ""
    for k, v in classDict.items():
        if 10 <= v[1] < 30:
            style = (
                'style = "color:orange; text-align:center; padding: 5px 15px 5px 15px"'
            )
        elif v[1] < 10:
            style = 'style = "color:red; text-align:center; padding: 5px 15px 5px 15px"'
        else:
            style = 'style = "text-align:center; padding: 5px 15px 5px 15px"'
        if v[3] == True:
            warning = f"""<p><b style="color:red">Warning: </b>{k} currently has no registrants for tomorrow's session.</p>"""

        text = f"""
        <tr>
            <td style="text-align:center; padding: 5px 15px 5px 15px">{k}</td>
            <td {style}>{v[0]}</td>
            <td {style}>{v[1]}</td>
            <td style="text-align:center; padding: 5px 15px 5px 15px">{v[2]}</td>
            <td style="text-align:center; padding: 5px 15px 5px 15px">{v[4]}</td>
            <td style="text-align:center; padding: 5px 15px 5px 15px">{v[5]}</td>
        </tr>
        """
        htmlString += text

    return [htmlString, warning]


coreClassesHtml = htmlGen(coreClasses)
otherClassesHtml = htmlGen(otherClasses)

##### GMAIL #####
# # Reformat date for email subject
formattedToday = today.strftime("%B %d")

# Compose email
emailMsg = f"""
<html>
    <body>
        <p>
            This is an automated email tracking the latest scheduled class for every class offered at Asmbly.
        </p>
        <table>
            <tr>
                <td style="text-align:center">
                    <h3>Core Classes</h3>
                    {coreClassesHtml[1]}
                </td>
            </tr>
            <tr style="width: 100%">
                <td style="text-align:center; width: 100%">
                    <table style="margin:0 auto; width: 100%">
                        <tr>
                            <th style="text-align:center; padding: 5px 15px 5px 15px; width:150px">Class Name</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Latest Scheduled</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Days Away</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Number Scheduled</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Seats Available</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Nearest Open Seat</th>
                        </tr>
                        {coreClassesHtml[0]}
                    </table
                </td>
            </tr>
            <tr>
                <td style="text-align:center">
                    <h3>Other Classes</h3>
                    {otherClassesHtml[1]}
                </td>
            </tr>
            <tr style="width: 100%">
                <td style="text-align:center; width: 100%">
                    <table style="margin:0 auto; width: 100%">
                        <tr>
                            <th style="text-align:center; padding: 5px 15px 5px 15px; width:150px">Class Name</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Latest Scheduled</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Days Away</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Number Scheduled</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Seats Available</th>
                            <th style="text-align:center; padding: 5px 15px 5px 15px">Nearest Open Seat</th>
                        </tr>
                        {otherClassesHtml[0]}
                    </table
                </td>
            </tr>
        </table>
        <p>
            Thanks!<br>
            Asmbly AdminBot
        </p>
    </body>
</html>
    """
# print(emailMsg)

mimeMessage = MIMEMultipart()
mimeMessage["to"] = "classes@asmbly.org"
mimeMessage["subject"] = f"Currently Scheduled Classes - {formattedToday}"
mimeMessage.attach(MIMEText(emailMsg, "html"))
raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

sendMIMEmessage(mimeMessage)
