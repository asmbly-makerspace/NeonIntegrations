################## Asmbly NeonCRM & Gmail API Integrations ##################
#   Neon API docs - https://developer.neoncrm.com/api-v2/                   #
#  Gmail API docs - https://developers.google.com/gmail/api/reference/rest  #
#############################################################################
#############################################################################
#  This helper script grabs Event data from Neon and cross references a     #
#  json file with teachers' email addresses in order to send reminder       #
#  emails each week about scheduled classes.                                #
#############################################################################

# Outside of the following imports, this script relies on teachers.json file
# containing teacher names and emails which is expected in the same directory
# as this script.

# Currently this script is set to run on a daily basis

import json
import base64
import datetime
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

import helpers.neon as neon

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%H:%S",
)


# Get events for the next deltaDays days
today = datetime.date.today()
logging.info(today)
deltaDays = (today + datetime.timedelta(days=2)).isoformat()
searchFields = [
    {
        "field": "Event Start Date",
        "operator": "GREATER_AND_EQUAL",
        "value": today.isoformat(),
    },
    {"field": "Event Start Date", "operator": "LESS_AND_EQUAL", "value": deltaDays},
    {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
]

outputFields = [
    "Event Name",
    "Event ID",
    "Event Topic",
    "Event Start Date",
    "Event Start Time",
    "Event End Date",
    "Event End Time",
    "Event Registration Attendee Count",
    "Registrants",
    "Hold To Waiting List",
    "Waiting List Status",
]

responseEvents = neon.postEventSearch(searchFields, outputFields)

# pprint(responseEvents["searchResults"])

# Remove duplicates in the list of teachers
rawTeachers = [item.get("Event Topic") for item in responseEvents["searchResults"]]
teachers = []
[teachers.append(teacher) for teacher in rawTeachers if teacher not in teachers]
# print(f"Teachers for the next 10 days: {teachers}")

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
        logging.info("WARNING:  No teacher assigned!")
        teacherEmails[None] = "classes@asmbly.org"
    if teacher in alreadySent:
        logging.info(f"Already emailed {teacher}")
        continue

    # Find all events for each teacher
    events = list(
        filter(lambda x: x["Event Topic"] == teacher, responseEvents["searchResults"])
    )
    logging.info(f"\n\n_____\n\nEmailing {teacher} about {len(events)} event(s)...")
    sortedEvents = sorted(
        events, key=lambda x: datetime.datetime.fromisoformat(x["Event Start Date"])
    )

    # Reformat event data so it looks nice in email
    prettyEvents = ""
    for event in sortedEvents:
        eventId = event["Event ID"]
        logging.info(eventId)
        logging.info(event["Event Name"])

        individualEventReg = neon.getEventRegistrants(eventId)
        # logging.info(individualEventReg)

        # Declare empty variable that may or may not get filled depending on whether there are registrations
        # registrantDict will be a dictionary of dictionaries
        ### outer key is the registration status
        ### inner key is registrant account id
        registrantDict = {"SUCCEEDED": [], "DEFERRED": [], "CANCELED": [], "FAILED": []}
        # Registrant info formatted for email
        prettyRegistrants = ""

        # Get total number of attendees - This does not always coordinate with number of account IDs
        attendeeCount = neon.getEventRegistrantCount(
            individualEventReg["eventRegistrations"]
        )
        logging.info(attendeeCount)

        # Only add info if there are registrations
        if attendeeCount > 0:

            # Iterate over response to add registrant account IDs to dictionary organized by registration status
            for registrant in individualEventReg["eventRegistrations"]:
                status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
                acctId = registrant["registrantAccountId"]

                # Retrieve email and phone associated with this account ID
                # Registrations with multiple attendees may have different emails listed in the UI
                # but these aren't accessible from the API, so we will just use the info from the main account
                acctInfo = neon.getAccountIndividual(acctId)
                email = acctInfo["individualAccount"]["primaryContact"]["email1"]
                phone = ""
                try:
                    phone = acctInfo["individualAccount"]["primaryContact"][
                        "addresses"
                    ][0]["phone1"]
                except KeyError:
                    phone = acctInfo["individualAccount"]["primaryContact"][
                        "addresses"
                    ][1]["phone1"]

                # Build a dictionary list of attendee names under this registration
                attendeeList = {"name": [], "email": email, "phone": phone}
                for attendee in registrant["tickets"][0]["attendees"]:
                    attendee = f'{attendee["firstName"]} {attendee["lastName"]}'
                    attendeeList["name"].append(attendee)

                # Build entry to add to registrantDict with all attendees associated with this acct Id
                entry = {acctId: attendeeList}

                # Add to registrantDict under the appropriate status
                registrantDict[status].append(entry)

            for account in registrantDict["SUCCEEDED"]:
                for k, v in account.items():
                    for it in v["name"]:
                        student = f"{it}:  {v['email']}, {v['phone']}"
                        prettyRegistrants += f"\t{student}\n\t"
        else:
            prettyRegistrants += f"\tNo attendees registered currently. Check Neon for updates as event approaches.\n\t"

        # Build up formatted event info for email body
        rawTime = event["Event Start Time"]
        rawDate = event["Event Start Date"]
        datetimeDate = datetime.datetime.strptime(rawDate, "%Y-%m-%d").date()
        formattedDate = datetime.date.strftime(datetimeDate, "%B %d")
        startTime = datetime.datetime.strptime(rawTime, "%H:%M:%S").strftime("%I:%M %p")
        if datetimeDate == today:
            dateString = f"TODAY - {formattedDate}"
        elif datetimeDate == today + datetime.timedelta(days=1):
            dateString = f"Tomorrow - {formattedDate}"
        else:
            dateString = formattedDate
        info = f"""
        {event["Event Name"]}
        Date: {dateString}
        Time: {startTime}
        Number of registrants: {event["Registrants"]}
            {prettyRegistrants}
        """
        prettyEvents += info

    ##### GMAIL #####
    # Reformat date for email subject
    formattedToday = today.strftime("%B %d")

    teacherFirstName = teacher[: teacher.index(" ")]

    # Compose email
    emailMsg = f"""
Hi {teacherFirstName},

This is an automated email to remind you of the upcoming classes you are scheduled to teach at Asmbly.
Thank you for sharing your knowledge with the community!

{prettyEvents}

Please note these are the registrations as of the time of this email and may not reflect final registrations for your class.
You can see more details about these events and registrants in your Neon backend account.  
The login URL is https://asmbly.z2systems.com/np/admin/content/contentList.do
Email classes@asmbly.org if you have any questions about the above schedule.

\t* Note: Some registrants are purchased under a single account and thus end up with the same email and phone number.


Thanks again!
Asmbly AdminBot
    """
    # print(emailMsg)

    mimeMessage = MIMEMultipart()
    try:
        mimeMessage["To"] = teacherEmails[teacher]
        mimeMessage["CC"] = "classes@asmbly.org"
        mimeMessage["Subject"] = f"Your upcoming classes at Asmbly"
    except KeyError:
        mimeMessage["To"] = "classes@asmbly.org"
        mimeMessage["Subject"] = f"Failed Class Reminder - {teacher}"

    mimeMessage.attach(MIMEText(emailMsg, "plain"))
    raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()

    sendMIMEmessage(mimeMessage)
