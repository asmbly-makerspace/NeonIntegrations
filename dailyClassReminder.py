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
import datetime
import logging
import uuid

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from helpers.gmail import sendMIMEmessage

from helpers import neon

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Get events for the next DELTA_DAYS days
TODAY = datetime.date.today()
INVOCATION_ID = str(uuid.uuid4())
logging.info("\n\n----- Beginning class reminders for %s -----\n\n", TODAY.isoformat())
logging.info("Script invocation ID: %s", INVOCATION_ID)
DELTA_DAYS = (TODAY + datetime.timedelta(days=2)).isoformat()
SEARCH_FIELDS = [
    {
        "field": "Event Start Date",
        "operator": "GREATER_AND_EQUAL",
        "value": TODAY.isoformat(),
    },
    {"field": "Event Start Date", "operator": "LESS_AND_EQUAL", "value": DELTA_DAYS},
    {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
]

OUTPUT_FIELDS = [
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

def get_response_events(search_fields, output_fields):
    return neon.postEventSearch(search_fields, output_fields)

# Import teacher contact info
def get_teacher_contact_info():
    CONTACT_INFO = "teachers.json"
    teacher_emails = {}
    with open(CONTACT_INFO, "r", encoding="utf-8") as f:
        teacher_emails = json.load(f)
    return teacher_emails

# For use if script ran and failed to complete
ALREADY_SENT = []

# Begin gathering data for emailing each teacher
# Send each teacher an email reminder about classes they are scheduled to teach
def main():
    TEACHER_EMAILS = get_teacher_contact_info()
    RESPONSE_EVENTS = get_response_events(SEARCH_FIELDS, OUTPUT_FIELDS)

    # Remove duplicates in the list of teachers
    TEACHERS = {item.get("Event Topic") for item in RESPONSE_EVENTS["searchResults"]}

    for teacher in TEACHERS:
        try:
            if not teacher:
                logging.info("WARNING:  No teacher assigned!")
                TEACHER_EMAILS[teacher] = "classes@asmbly.org"
            if teacher in ALREADY_SENT:
                logging.info("Already emailed %s", teacher)
                continue

            # Find all events for each teacher
            events = list(
                filter(
                    lambda x, teach=teacher: x["Event Topic"] == teach,
                    RESPONSE_EVENTS["searchResults"],
                )
            )
            logging.info("\n\n_____\n\nEmailing %s about %s event(s)...", teacher, len(events))
            sorted_events = sorted(
                events, key=lambda x: datetime.datetime.fromisoformat(x["Event Start Date"])
            )

            # Reformat event data so it looks nice in email
            pretty_events = ""
            for event in sorted_events:
                event_id = event["Event ID"]
                logging.info(event_id)
                logging.info(event["Event Name"])

                individual_event_reg = neon.getEventRegistrants(event_id)
                # logging.info(individualEventReg)

                # Declare empty variable that may or may not get filled depending on whether there are registrations
                # registrantDict will be a dictionary of dictionaries
                ### outer key is the registration status
                ### inner key is registrant account id
                registrant_dict = {
                    "SUCCEEDED": [],
                    "DEFERRED": [],
                    "CANCELED": [],
                    "FAILED": [],
                    "REFUNDED": [],
                }
                # Registrant info formatted for email
                pretty_registrants = ""

                # Get total number of attendees - This does not always coordinate with number of account IDs
                attendee_count = neon.getEventRegistrantCount(
                    individual_event_reg["eventRegistrations"]
                )
                logging.info(attendee_count)

                # Only add info if there are registrations
                if attendee_count > 0:

                    # Iterate over response to add registrant account IDs to dictionary organized by registration status
                    for registrant in individual_event_reg["eventRegistrations"]:
                        status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
                        acct_id = registrant["registrantAccountId"]

                        # Retrieve email and phone associated with this account ID
                        # Registrations with multiple attendees may have different emails listed in the UI
                        # but these aren't accessible from the API, so we will just use the info from the main account
                        acct_info = neon.getAccountIndividual(acct_id)
                        email = acct_info["individualAccount"]["primaryContact"]["email1"]
                        addresses = acct_info["individualAccount"]["primaryContact"]["addresses"]
                        # Get all phone numbers in the address entries, then use the first non-None result
                        phones = [addr.get('phone1') for addr in addresses]
                        phone = [p for p in phones if p][0]
                        if not phone:
                            phone = "N/A"

                        # Build a dictionary list of attendee names under this registration
                        attendee_list = {"name": [], "email": email, "phone": phone}
                        for attendee in registrant["tickets"][0]["attendees"]:
                            attendee = f'{attendee["firstName"]} {attendee["lastName"]}'
                            attendee_list["name"].append(attendee)

                        # Build entry to add to registrantDict with all attendees associated with this acct Id
                        entry = {acct_id: attendee_list}

                        # Add to registrantDict under the appropriate status
                        # First check that this registration status is in the dictionary
                        if status not in registrant_dict:
                            registrant_dict[status] = []
                        registrant_dict[status].append(entry)

                    for account in registrant_dict["SUCCEEDED"]:
                        for k, v in account.items():
                            for it in v["name"]:
                                student = f"{it}:  {v['email']}, {v['phone']}"
                                pretty_registrants += f"\t{student}\n\t"
                else:
                    pretty_registrants += "\tNo attendees registered currently. Check Neon for updates as event approaches.\n\t"

                # Build up formatted event info for email body
                raw_time = event["Event Start Time"]
                raw_date = event["Event Start Date"]
                datetime_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
                formatted_date = datetime.date.strftime(datetime_date, "%B %d")
                start_time = datetime.datetime.strptime(raw_time, "%H:%M:%S").strftime(
                    "%I:%M %p"
                )
                if datetime_date == TODAY:
                    date_string = f"TODAY - {formatted_date}"
                elif datetime_date == TODAY + datetime.timedelta(days=1):
                    date_string = f"Tomorrow - {formatted_date}"
                else:
                    date_string = formatted_date
                info = f"""
                {event["Event Name"]}
                Date: {date_string}
                Time: {start_time}
                Number of registrants: {event["Registrants"]}
                    {pretty_registrants}
                """
                pretty_events += info

            ##### GMAIL #####
            # Reformat date for email subject
            formatted_today = TODAY.strftime("%B %d")

            teacher_first_name = teacher.split(' ')[0] if teacher else 'N/A'

            # Compose email
            email_msg = f"""
Hi {teacher_first_name},

This is an automated email to remind you of the upcoming classes you are scheduled to teach at Asmbly.
Thank you for sharing your knowledge with the community!

{pretty_events}

Please note these are the registrations as of the time of this email and may not reflect final registrations for your class.
You can see more details about these events and registrants in your Neon backend account.  
The login URL is https://asmbly.z2systems.com/np/admin/content/contentList.do
Email classes@asmbly.org if you have any questions about the above schedule.

\t* Note: Some registrants are purchased under a single account and thus end up with the same email and phone number.


Thanks again!
Asmbly AdminBot
"""

            mime_message = MIMEMultipart()
            try:
                mime_message["To"] = TEACHER_EMAILS[teacher]
                mime_message["CC"] = "classes@asmbly.org"
                mime_message["Subject"] = "Your upcoming classes at Asmbly"
            except KeyError:
                mime_message["To"] = "classes@asmbly.org"
                mime_message["Subject"] = f"Failed Class Reminder - {teacher}"

            mime_message.attach(MIMEText(email_msg, "plain"))

            sendMIMEmessage(mime_message)
        except Exception as e:
            # Log the error, then move on to the next email
            logging.error(f'Could not send daily class reminder for teacher: {teacher}')
            logging.error(e)


if __name__ == '__main__':
    main()
