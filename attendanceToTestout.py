import base64
import datetime
import logging
import os

import helpers.neon as neon
from helpers.api import apiCall

if os.environ.get("USER") == "ec2-user" or os.environ.get("LAMBDA_TASK_ROOT"):
    from aws_ssm import N_APIkey, N_APIuser
else:
    from config import N_APIkey, N_APIuser

# Neon Account Info
N_auth = f"{N_APIuser}:{N_APIkey}"
N_baseURL = "https://api.neoncrm.com/v2"
N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
N_headers = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {N_signature}",
}

def _get_today():
    return datetime.date.today()

def _get_delta_days():
    return (_get_today() - datetime.timedelta(days=7)).isoformat()

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

EVENT_FIELDS = {
    "Festool Domino": "440",
    "Shaper Origin": "274",
    "Woodshop Safety": "84",
    "Metal Shop Safety": "520",
    "Big Lasers": "86",
    "CNC Router": "435",
    "Stationary Sanders": "675",
    "Metal Lathe": "676",
    "Wood Lathe": "677",
    "MIG Welding": "678",
    "TIG Welding": "679",
    "Small Lasers": "680",
    "Laser Engrave Round": "1007",
    "Milling": "681",
    "Tormach": "682",
    "Filament": "683",
    "Resin": "684",
    "Sublimation": "685",
    "Vinyl": "686",
    "Orientation": "182",
    "CSI": "1248" # Ceramics Safety and Information
}


def getFieldForEvent(className: str):
    for name, id in EVENT_FIELDS.items():
        if name in className:
            return id, name
    return None, None


# A registration with no tickets or no attendees is logged and treated as
# not attended, instead of raising and dropping every registration in the event.
def isMarkedAttended(registration, eventId):
    try:
        return registration["tickets"][0]["attendees"][0]["markedAttended"] == True
    except (KeyError, IndexError, TypeError):
        logging.warning(
            "Skipping registration for Account ID %s in event %s: no ticket or attendee",
            registration.get("registrantAccountId"),
            eventId,
        )
        return False


def toolTestingUpdate(fieldId: str, shortName: str, neonId: int, inputDate: str):
    date = datetime.datetime.strftime(
        datetime.datetime.strptime(inputDate, "%Y-%m-%d"), "%m/%d/%Y"
    )

    # The account read is inside the try so that an account we can't read
    # (error response, company account, etc.) is logged and skipped without
    # stopping the remaining attendees of the event.
    try:
        acctCustFields = neon.getAccountIndividual(neonId)["individualAccount"][
            "accountCustomFields"
        ]

        customIdList = [field["id"] for field in acctCustFields]
        if fieldId in customIdList:
            logging.info("Account ID %s already has %s marked", neonId, shortName)
            return

        ##### NEON #####
        # Update part of an account
        # https://developer.neoncrm.com/api-v2/#/Accounts/patchAccount
        httpVerb = "PATCH"
        resourcePath = f"/accounts/{neonId}"
        queryParams = ""
        data = {
            "individualAccount": {
                "accountCustomFields": [{"id": fieldId, "value": date}]
            }
        }

        url = N_baseURL + resourcePath + queryParams

        patch = apiCall(httpVerb, url, data, N_headers)
        if patch.status_code == 200:
            logging.info(
                "%s SUCCESS!  \n\tAccount ID %s \n\tClass '%s'",
                patch.status_code,
                neonId,
                shortName,
            )
        else:
            logging.error(
                "%s FAILED!  \n\tAccount ID %s \n\tClass '%s'",
                patch.status_code,
                neonId,
                shortName,
            )

    except Exception:
        logging.exception(
            "Update failed for Account ID %s, Class '%s'",
            neonId,
            shortName,
        )


def main():
    today = _get_today()
    delta_days = _get_delta_days()

    searchFields = [
        {"field": "Event End Date", "operator": "GREATER_AND_EQUAL", "value": delta_days},
        {
            "field": "Event End Date",
            "operator": "LESS_AND_EQUAL",
            "value": today.isoformat(),
        },
        {"field": "Event Archived", "operator": "EQUAL", "value": "No"},
    ]

    outputFields = ["Event Name", "Event ID", "Event End Date"]

    logging.info("Starting Tool Testing update for %s:", today.isoformat())

    try:
        eventSearch = neon.postEventSearch(searchFields, outputFields)
        responseEvents = eventSearch["searchResults"]
    except Exception:
        logging.exception("Event search failed")
        return

    if not responseEvents:
        logging.info("Event Search contained no results")
        return

    for event in responseEvents:
        eventName = event["Event Name"]
        eventId = event["Event ID"]
        eventDate = event["Event End Date"]
        fieldId, shortName = getFieldForEvent(eventName)
        if not fieldId:
            logging.info("%s does not have a corresponding custom field", eventName)
            continue
        try:
            registrants = neon.getEventRegistrants(eventId)["eventRegistrations"]
            if registrants is None:
                logging.info("No registrants found for event %s (%s)", eventName, eventId)
                continue
            attendees = [
                r for r in registrants
                if isMarkedAttended(r, eventId)
            ]
            if not attendees:
                logging.info("No attendees marked for event %s (%s)", eventName, eventId)
                continue
            for attendee in attendees:
                toolTestingUpdate(
                    fieldId, shortName, attendee["registrantAccountId"], eventDate
                )
        except Exception:
            logging.exception("Failed processing event %s (%s)", eventName, eventId)


if __name__ == '__main__':
    main()
