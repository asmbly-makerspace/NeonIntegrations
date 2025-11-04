"""Main Lambda handler"""

import logging
import json
import datetime
import zoneinfo
import requests
import boto3
import base64
from collections import deque
from typing import Any

from mailjetUtil import (
    Subscriber as MailjetSubscriber,
    MJCredentials,
    MJService,
    MailjetAction,
)
from openPathUpdateSingle import openPathUpdateSingle
from neonUtil import getMemberById
from aws_ssm import N_APIkey, N_APIuser


logger = logging.getLogger()
logger.setLevel(logging.INFO)

TZ = zoneinfo.ZoneInfo("America/Chicago")


def find_key_bfs(d: dict, target_key: str) -> Any:
    """
    Find a key in a nested dictionary using breadth-first search.

    Args:
        d: The dictionary to search
        target_key: The key to find

    Returns:
        The value associated with the key if found, None otherwise
    """

    queue: deque[tuple[dict, list[str]]] = deque([(d, [])])

    while queue:
        current_dict, path = queue.popleft()

        if not isinstance(current_dict, dict):
            continue

        # Check if target key exists at current level
        if target_key in current_dict:
            return current_dict[target_key]

        # Add all nested dictionaries to the queue
        for key, value in current_dict.items():
            if isinstance(value, dict):
                queue.append((value, path + [key]))
            elif isinstance(value, list):
                # Handle lists that might contain dictionaries
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        queue.append((item, path + [key, f"[{i}]"]))

    return None


def add_member_to_mailjet(
    account: dict, membership_end_dates: list[datetime.date]
) -> None:
    facility_tour_date = account.get("FacilityTourDate")
    if not isinstance(facility_tour_date, str):
        logger.warning(
            "Facility tour date is not a string for %s", account.get("Account ID")
        )
        return
    attended_orientation = facility_tour_date is not None
    active_member = account.get("validMembership", False)
    signed_waiver = account.get("WaiverDate") is not None
    latest_membership_end_date = membership_end_dates[-1]
    account_email = account.get("Email 1")
    account_first_name = account.get("First Name")
    account_last_name = account.get("Last Name")
    account_mailjet_contact_id = account.get("MailjetContactID")

    if (
        not account_email
        or not account_first_name
        or not account_last_name
        or not account_mailjet_contact_id
    ):
        logger.warning(
            "Missing required account information for %s", account.get("Account ID")
        )
        return

    logger.info("Getting mailjet credentials from SSM")

    ssm_mj_creds = boto3.client("ssm").get_parameters(
        Names=[
            "/mailjet/api_key",
            "/mailjet/api_secret",
        ],
        WithDecryption=True,
    )

    mj_creds = MJCredentials(
        public_key=ssm_mj_creds["Parameters"][0]["Value"],
        secret_key=ssm_mj_creds["Parameters"][1]["Value"],
    )

    mailjet = MJService(mj_creds)

    mailjet_account = MailjetSubscriber(
        email_=account_email.lower(),
        id_=account_mailjet_contact_id,
        first_name=account_first_name,
        last_name=account_last_name,
        attended_orientation=attended_orientation,
        orientation_date=(
            datetime.datetime.strptime(facility_tour_date, "%m/%d/%Y").astimezone(TZ)
            if facility_tour_date
            else None
        ),
        active_member=active_member,
        latest_membership_end=datetime.datetime.combine(
            latest_membership_end_date, datetime.time(0, 0)
        ).astimezone(TZ),
        signed_waiver=signed_waiver,
    )

    logger.info("Adding account %s to Mailjet", account_email.lower())

    mailjet.bulk_update_subscribers_in_lists(
        list_ids=[
            mailjet.new_members_list_id,
            mailjet.all_contacts_list_id,
        ],
        subscribers=[mailjet_account],
        action=MailjetAction.ADD_NOFORCE,
    )


def handle_joins(neon_id: int) -> tuple[dict, bool, list[datetime.date]]:
    logger.info("Getting account %s from Neon", neon_id)
    account = getMemberById(id=neon_id)
    membership_start_dates = sorted(
        [
            datetime.datetime.strptime(key, "%Y-%m-%d").date()
            for key in account.get("membershipDates").keys()
        ]
    )
    membership_end_dates = sorted(
        [
            datetime.datetime.strptime(value, "%Y-%m-%d").date()
            for value in account.get("membershipDates").values()
        ]
    )

    latest_membership_start_date = membership_start_dates[-1]

    should_add_member = False

    if (
        latest_membership_start_date == datetime.datetime.now(TZ).date()
        and len(membership_start_dates) == 1
    ):
        should_add_member = True
    elif (
        len(membership_start_dates) > 1
        and latest_membership_start_date == datetime.datetime.now(TZ).date()
        and latest_membership_start_date - membership_end_dates[-2]
        >= datetime.timedelta(days=365)
    ):
        should_add_member = True

    return account, should_add_member, membership_end_dates


def get_neon_id_from_membership_id(membership_id: int) -> int | None:
    N_auth = f"{N_APIuser}:{N_APIkey}"
    N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
    N_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {N_signature}",
    }
    try:
        response = requests.get(
            url=f"https://api.neoncrm.com/v2/memberships/{membership_id}",
            headers=N_headers,
        )
    except requests.exceptions.RequestException as e:
        logger.error("Error retrieving membership %s from Neon: %s", membership_id, e)
        return None

    if not response.ok:
        logger.error(
            "Error retrieving membership %s from Neon: %s (%s)",
            membership_id,
            response.json(),
            response.status_code,
        )
        return None

    neon_id = find_key_bfs(response.json(), "accountId")
    if not neon_id:
        logger.warning("No Neon ID found in membership %s response", membership_id)
        return None

    return neon_id


def lambda_handler(event: dict, _: dict) -> None:
    """
    Main lambda handler.
    """

    now = datetime.datetime.now(TZ)

    # Don't run between 2:30 AM and 4:59 AM (inclusive)
    if (now.hour == 2 and now.minute >= 30) or (3 <= now.hour < 5):
        logger.info("Skipping run between 2:30 and 5:00 AM")
        return

    logger.info("EVENT INFO: %s", event)

    if not (body := event.get("body")):
        return

    neon_response: dict = json.loads(body)
    if not (event_trigger := neon_response.get("eventTrigger")):
        return

    neon_id = None

    match event_trigger:
        case "createMembership":
            logger.info("Event trigger: createMembership")
            if not (data := neon_response.get("data")):
                logger.error("No data found in event object")
                return
            neon_id = find_key_bfs(data, "accountId")
            if not neon_id:
                logger.error("No Neon ID found in event data")
                return

            if find_key_bfs(data, "transactionStatus") == "SUCCEEDED" and find_key_bfs(
                data, "enrollmentType"
            ) in {
                "JOIN",
                "REJOIN",
            }:
                logger.info(
                    "Getting account and membership end dates for Neon ID: %s", neon_id
                )
                account, should_add_member, membership_end_dates = handle_joins(neon_id)

                if should_add_member:
                    logger.info("Adding Neon ID %s to Mailjet", neon_id)
                    add_member_to_mailjet(account, membership_end_dates)

        case "updateMembership":
            neon_id = find_key_bfs(neon_response, "accountId")
        case "editAccount" | "mergedAccount":
            neon_id = find_key_bfs(neon_response, "accountId")

        case "deleteMembership":
            membership_id = find_key_bfs(neon_response, "membershipId")
            if not membership_id:
                logger.error("No membership ID found in event data")
                return

            logger.info("Getting Neon ID from membership ID: %s", membership_id)

            neon_id = get_neon_id_from_membership_id(membership_id)

    if not neon_id:
        logger.warning("No Neon ID found")
        return

    logger.info("Updating Alta Open for Neon ID: %s", neon_id)

    openPathUpdateSingle(neon_id)

    # Currently, marking attendance does not trigger the updateEventRegistration webhook,
    # so the following code will not run
    # if event_trigger == "updateEventRegistration":
    #     event_id = neon_response.get("data").get("eventId")
    #     event = neon.getEvent(event_id)
    #     event_name = event.get("name")
    #     event_date = event.get("eventDates").get("endDate")
    #     attendees = neon_response.get("data").get("tickets")[0].get("attendees")
    #     for attendee in attendees:
    #         if attendee.get("markedAttended"):
    #             neon_id = attendee.get("registrantAccountId")
    #             toolTestingUpdate(event_name, neon_id, event_date)
