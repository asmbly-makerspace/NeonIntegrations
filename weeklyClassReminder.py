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

# Currently this script is set to run on a weekly basis - Sundays at 6:00 PM

from pprint import pprint
import json
import datetime
import uuid
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

import helpers.neon as neon

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_teacher_contact_info():
    """Load teacher contact information from JSON file"""
    contactInfo = "teachers.json"
    try:
        with open(contactInfo, "r", encoding="utf-8") as f:
            teacherEmails = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Teacher contact file '{contactInfo}' not found. Please ensure teachers.json exists in the same directory as this script.")
        raise
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse '{contactInfo}' as JSON: {e}")
        raise
    return teacherEmails


def get_search_fields():
    """Build search fields for the next 10 days of events"""
    today = datetime.date.today()
    tenDays = today + datetime.timedelta(days=10)
    searchFields = [
        {"field": "Event End Date", "operator": "GREATER_THAN", "value": today},
        {"field": "Event End Date", "operator": "LESS_THAN", "value": tenDays},
        {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
    ]
    return searchFields, today


def get_output_fields():
    """Define output fields for event search"""
    return [
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


def main():
    """Main function to send weekly class reminders"""
    invocation_id = str(uuid.uuid4())
    searchFields, today = get_search_fields()
    outputFields = get_output_fields()
    
    logging.info("\n\n----- Beginning weekly class reminders for %s -----\n\n", today.isoformat())
    logging.info("Script invocation ID: %s", invocation_id)
    
    responseEvents = neon.postEventSearch(searchFields, outputFields)
    
    pprint(responseEvents["searchResults"])
    
    # Remove duplicates in the list of teachers
    # Using set comprehension for efficient deduplication
    teachers = list({item.get("Event Topic") for item in responseEvents["searchResults"]})
    
    # Import teacher contact info
    teacherEmails = get_teacher_contact_info()
    
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
        events = list(
            filter(lambda x: x["Event Topic"] == teacher, responseEvents["searchResults"])
        )
        print(f"\n\n_____\n\nEmailing {teacher} about {len(events)} event(s)...")
        sortedEvents = sorted(
            events, key=lambda x: datetime.datetime.fromisoformat(x["Event Start Date"])
        )

        # Reformat event data so it looks nice in email
        prettyEvents = ""
        for event in sortedEvents:
            eventId = event["Event ID"]

            individualEventReg = neon.getEventRegistrants(eventId)

            # Declare empty variable that may or may not get filled depending on whether there are registrations
            # registrantDict will be a dictionary of dictionaries
            ### outer key is the registration status
            ### inner key is registrant account id
            registrantDict = {"SUCCEEDED": [], "DEFERRED": [], "CANCELED": []}
            # Registrant info formatted for email
            prettyRegistrants = ""

            # Get total number of attendees - This does not always coordinate with number of account IDs
            attendeeCount = neon.getEventRegistrantCount(
                individualEventReg["eventRegistrations"]
            )

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
            startTime = datetime.datetime.strptime(rawTime, "%H:%M:%S").strftime("%I:%M %p")
            info = f"""
            {event["Event Name"]}
            Date: {event["Event Start Date"]}
            Time: {startTime}
            Number of registrants: {event["Registrants"]}
                {prettyRegistrants}
            """
            prettyEvents += info

        ##### GMAIL #####
        # Reformat date for email subject
        formattedToday = today.strftime("%B %d")

        # Compose email
        emailMsg = f"""
Hi {teacher},

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
        print(emailMsg)

        mimeMessage = MIMEMultipart()
        mimeMessage["To"] = teacherEmails[teacher]
        mimeMessage["CC"] = "classes@asmbly.org"
        mimeMessage["Subject"] = (
            f"Your upcoming classes at Asmbly - week of {formattedToday}"
        )
        mimeMessage.attach(MIMEText(emailMsg, "plain"))

        sendMIMEmessage(mimeMessage)


if __name__ == '__main__':
    main()
