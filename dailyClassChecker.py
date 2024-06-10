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

import datetime
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

from helpers import neon

CORE_CLASSES = {
    "Orientation": 0.33,
    "Woodshop Safety": 0.33,
    "Metal Shop Safety": 0.5,
    "Festool Domino": 2,
    "Metal Lathe": 4,
    "Milling": 3,
    "MIG Welding": 2,
    "TIG Welding Steel": 3,
    "TIG Welding: Aluminum": 3,
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
    "Leatherworking": 4,
    "Embroidery": 4,
}

TODAY = datetime.date.today()
# deltaDays = today + datetime.timedelta(days=90)
SEARCH_FIELDS = [
    {"field": "Event End Date", "operator": "GREATER_THAN", "value": TODAY.isoformat()},
    {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
]

OUTPUT_FIELDS = [
    "Event Name",
    "Event Topic",
    "Event Start Date",
    "Event End Date",
    "Event Registration Attendee Count",
    "Registrants",
    "Event ID",
    "Event Capacity",
]


RESPONSE_EVENTS = neon.postEventSearch(SEARCH_FIELDS, OUTPUT_FIELDS)["searchResults"]


def latest_date(date_list: list[str]) -> list:
    """
    Take list of date strings, convert each to datetime, find latest and convert result
    back to string.
    """

    if date_list:
        datetime_dates = [
            datetime.datetime.strptime(date, "%Y-%m-%d").date() for date in date_list
        ]
        datetime_dates.sort(reverse=True)

        _latest_date = datetime.datetime.strftime(datetime_dates[0], "%m-%d-%y")
        delta_days = (datetime_dates[0] - TODAY).days

    else:
        _latest_date = "None Scheduled"
        delta_days = 0

    return [_latest_date, delta_days]


def latest_classes(classes_info: dict) -> dict:
    """
    Find the latest scheduled class and number of scheduled classes
    for each class in classes.json
    """
    # create dict of dicts sorting all events into class types
    sorted_class_dict = {}
    for item in classes_info:
        ind_class_list = [
            event for event in RESPONSE_EVENTS if item in event["Event Name"]
        ]
        dict_of_ind_class_list = {item: ind_class_list}
        sorted_class_dict.update(dict_of_ind_class_list)

    # create dict of lists with all currently scheduled dates for each class
    class_dates = {}
    for key, value in sorted_class_dict.items():
        dates = [event["Event Start Date"] for event in value]
        is_empty = False
        earliest_available = sys.maxsize
        total_seats_available = 0
        for event in value:
            if event["Event Registration Attendee Count"] == event["Registrants"]:
                actual_registrants = int(event["Registrants"])
            else:
                registrants = neon.getEventRegistrants(event["Event ID"]).get(
                    "eventRegistrations"
                )
                actual_registrants = neon.getEventRegistrantCount(registrants)
            event_capacity = int(event["Event Capacity"])
            seats_available = event_capacity - actual_registrants
            total_seats_available += seats_available
            timestamp = datetime.datetime.timestamp(
                datetime.datetime.fromisoformat(event["Event Start Date"])
            )
            if seats_available > 0 and timestamp < earliest_available:
                earliest_available = timestamp

            delta_days = (
                datetime.datetime.strptime(event["Event Start Date"], "%Y-%m-%d").date()
                - TODAY
            )
            delta_days = delta_days.days

            if delta_days == 1 and actual_registrants == 0:
                is_empty = True

        if earliest_available != sys.maxsize:
            earliest_available_date = datetime.datetime.strftime(
                datetime.datetime.fromtimestamp(earliest_available), "%m-%d-%y"
            )
        else:
            earliest_available_date = "No Seats Available"

        class_dates.update(
            {key: [dates, is_empty, total_seats_available, earliest_available_date]}
        )

    latest_dates = {
        className: [
            latest_date(dates[0])[0],
            latest_date(dates[0])[1],
            len(dates[0]),
            dates[1],
            dates[2],
            dates[3],
        ]
        for className, dates in class_dates.items()
    }

    return latest_dates


CORE_CLASSES = latest_classes(CORE_CLASSES)
OTHER_CLASSES = latest_classes(OTHER_CLASSES)


def html_gen(class_dict: dict) -> str:
    """Generate HTML table for class dictionary"""
    html_string = ""
    warning = ""
    for k, v in class_dict.items():
        if 10 <= v[1] < 30:
            style = (
                'style = "color:orange; text-align:center; padding: 5px 15px 5px 15px"'
            )
        elif v[1] < 10:
            style = 'style = "color:red; text-align:center; padding: 5px 15px 5px 15px"'
        else:
            style = 'style = "text-align:center; padding: 5px 15px 5px 15px"'
        if v[3] is True:
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
        html_string += text

    return [html_string, warning]


CORE_CLASS_HTML = html_gen(CORE_CLASSES)
OTHER_CLASS_HTML = html_gen(OTHER_CLASSES)

##### GMAIL #####
# # Reformat date for email subject
FORMATTED_TODAY = TODAY.strftime("%B %d")

# Compose email
EMAIL_MSG = f"""
<html>
    <body>
        <p>
            This is an automated email tracking the latest scheduled class for every class offered at Asmbly.
        </p>
        <table>
            <tr>
                <td style="text-align:center">
                    <h3>Core Classes</h3>
                    {CORE_CLASS_HTML[1]}
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
                        {CORE_CLASS_HTML[0]}
                    </table
                </td>
            </tr>
            <tr>
                <td style="text-align:center">
                    <h3>Other Classes</h3>
                    {OTHER_CLASS_HTML[1]}
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
                        {OTHER_CLASS_HTML[0]}
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
# print(EMAIL_MSG)

MIME_MESSAGE = MIMEMultipart()
MIME_MESSAGE["to"] = "classes@asmbly.org"
MIME_MESSAGE["subject"] = f"Currently Scheduled Classes - {FORMATTED_TODAY}"
MIME_MESSAGE.attach(MIMEText(EMAIL_MSG, "html"))

sendMIMEmessage(MIME_MESSAGE)
