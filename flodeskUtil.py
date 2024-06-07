############### Asmbly Flodesk API Integrations ##################
#      Flodesk API docs - https://developers.flodesk.com/        #
##################################################################

import base64
import logging
import time

from typing import Generator

import requests

from neonUtil import getNeonAccounts
from config import F_API_KEY

# Flodesk headers
F_AUTH = f"{F_API_KEY}:"
F_BASE_URL = "https://api.flodesk.com/v1"
F_SIGNATURE = base64.b64encode(bytearray(F_AUTH.encode())).decode()
F_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Basic {F_SIGNATURE}",
}


MEMBER_SEGMENT_ID = "6641784c84ebb40fecfd38a8"
ORIENTATION_SEGMENT_ID = "664174acb5a0ac8c73bb785f"


class Subscriber:
    """
    Flodesk subscriber

    Attributes:
        email (str): The subscriber's email address
        first_name (str): Subscriber's first name
        last_name (str): Subsriber's last name
        attended_orientation (bool): Boolean indicating whether the subscriber has attended an
            orientation at Asmbly
        active_member (bool): Boolean indicating an active membership
    """

    def __init__(
        self,
        email: str,
        first_name: str,
        last_name: str,
        attended_orientation: bool,
        signed_waiver: bool,
        active_member: bool = False,
    ):
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.attended_orientation = attended_orientation
        self.active_member = active_member
        self.signed_waiver = signed_waiver

    def create_or_update_sub(
        self, session: requests.Session, segment_ids: list[str] | None = None
    ) -> None:
        """
        Create a new Flodesk subsriber and add them to the provided segments. If the user already
        exists, update them.

        Args:
            segment_ids (list[str]): List of Flodesk segment IDs the user will be added to
            session (requests.Session): Requests library Session object

        Returns:
            None
        """

        endpoint = "/subscribers"
        url = F_BASE_URL + endpoint
        max_retries = 10

        json = {
            "email": self.email,
            "double_optin": False,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "custom_fields": {
                "attendedOrientation": str(self.attended_orientation),
                "signedWaiver": str(self.signed_waiver),
            },
        }

        if segment_ids:
            json["segment_ids"] = segment_ids

        for i in range(max_retries):
            response = session.post(url, json=json, headers=F_HEADERS)

            if response.ok:
                return
            elif response.status_code == 429:
                time.sleep(backoff_time(i))
            else:
                logging.error(
                    "Flodesk add/update subscriber request failed with status code %s. Message: %s. Raw Request: %s",
                    response.status_code,
                    response.json(),
                    response.request.body,
                )
                break

    def remove_sub(self, segment_ids: list[str], session: requests.Session) -> None:
        """
        Remove a subscriber from a Flodesk segment.

        Args:
            segment_ids (list[str]): List of Flodesk segment IDs the user will be removed from
            session (requests.Session): Requests library Session object

        Returns:
            None
        """

        endpoint = f"/subscribers/{self.email}/segments"
        url = F_BASE_URL + endpoint
        max_retries = 10

        json = {
            "segment_ids": segment_ids,
        }

        for i in range(max_retries):
            response = session.delete(url, json=json, headers=F_HEADERS)

            if response.ok:
                return
            elif response.status_code == 429:
                time.sleep(backoff_time(i))
            else:
                logging.error(
                    "Flodesk segment removal request failed with status code %s. Message: %s. Raw Request: %s",
                    response.status_code,
                    response.json(),
                    response.request.body,
                )
                break

    def is_active(self, session: requests.Session) -> bool:
        """
        Check if a subscriber is currently in the Member segment

        Args:
            session (requests.Session): Requests library Session object

        Returns:
            active (bool): Boolean indicating if the subscriber is currently in the Member segment
        """

        endpoint = f"/subscribers/{self.email}"
        url = F_BASE_URL + endpoint

        response = session.get(url, headers=F_HEADERS)

        if not response.ok:
            logging.error(
                "Flodesk user retrieval failed with status code %s. Message: %s. Raw Request: %s",
                response.status_code,
                response.json(),
                response.request.body,
            )

            raise ValueError

        segments: list[dict] | None = response.json().get("segments")

        if not segments:
            return False

        active = any(segment.get("id") == MEMBER_SEGMENT_ID for segment in segments)

        return active


def backoff_time(retry_count: int) -> float:
    """
    Calculates the backoff time for retrying an operation. The backoff time increases exponentially.

    Args:
        retry_count (int): The number of times the operation has been retried.

    Returns:
        wait_time (float): The calculated backoff time in seconds.
    """
    initial_delay = 200 / 1000
    wait_time = (2**retry_count) * initial_delay
    return wait_time


def get_current_subs(
    session: requests.Session, segment_id: str | None = None
) -> Generator[dict, None, None]:
    """
    Generator function returning current Flodesk subscribers. If a segment_id is provided,
    only returns subscriber for that segment

    Args:
        segment_id (str|None): Flodesk segment ID
        session (requests.Session): Requests library Session object

    Yields:
        response (dict): JSON response containing subscriber info
    """

    endpoint = "/subscribers"
    url = F_BASE_URL + endpoint
    max_retries = 10

    params = {"per_page": 100}

    if segment_id:
        params["segment_id"] = segment_id

    for i in range(max_retries):
        response = session.get(url, headers=F_HEADERS, params=params)

        if response.ok:
            response = response.json()
            yield response
            break
        elif response.status_code == 429:
            time.sleep(backoff_time(i))
        else:
            logging.error(
                "Flodesk subscriber list fetch failed with status code %s. Message: %s. Raw Request: %s",
                response.status_code,
                response.json(),
                response.request.body,
            )
            break

    total_pages = response.get("meta").get("total_pages")

    for page in range(2, total_pages + 1):

        params = {
            "page": page,
            "per_page": 100,
        }

        if segment_id:
            params["segment_id"] = segment_id

        for i in range(max_retries):

            response = session.get(url, headers=F_HEADERS, params=params)

            if response.ok:
                yield response.json()
                break
            elif response.status_code == 429:
                time.sleep(backoff_time(i))
            else:
                logging.error(
                    "Flodesk subscriber list fetch failed with status code %s. Message: %s. Raw Request: %s",
                    response.status_code,
                    response.json(),
                    response.request.body,
                )
                break


def update_flodesk_segments(neon_account_dict: dict) -> None:
    """
    Update audience segments in Flodesk to reflect current Membership status and Orientation
    attendance.

    Args:
        neon_account_dict (dict): Account info for every Asmbly Neon account holder

    Returns:
        None
    """

    session = requests.Session()

    current_member_seg_subs = set()

    for page in get_current_subs(session, MEMBER_SEGMENT_ID):
        subs = {sub["email"] for sub in page["data"]}

        current_member_seg_subs.update(subs)

    current_orientation_seg_subs = set()

    for page in get_current_subs(session, ORIENTATION_SEGMENT_ID):
        subs = {sub["email"] for sub in page["data"]}

        current_orientation_seg_subs.update(subs)

    accounts: dict[str, Subscriber] = {}
    for account in neon_account_dict:

        account = Subscriber(
            email=neon_account_dict[account].get("Email 1").lower(),
            first_name=neon_account_dict[account].get("First Name"),
            last_name=neon_account_dict[account].get("Last Name"),
            attended_orientation=neon_account_dict[account].get("FacilityTourDate")
            is not None,
            active_member=neon_account_dict[account].get("validMembership"),
            signed_waiver=neon_account_dict[account].get("WaiverDate") is not None,
        )

        accounts[account.email] = account

    active_accounts = {
        account.email for account in accounts.values() if account.active_member
    }

    attended_orientation_accounts = {
        account.email for account in accounts.values() if account.attended_orientation
    }

    orientation_add_list = attended_orientation_accounts - current_orientation_seg_subs

    member_add_list = active_accounts - current_member_seg_subs

    final_member_remove_list = current_member_seg_subs - active_accounts

    final_o_and_m_add_list = orientation_add_list & member_add_list

    final_o_only_add_list = orientation_add_list - member_add_list

    final_m_only_add_list = member_add_list - orientation_add_list

    for sub in final_member_remove_list:
        accounts[sub].remove_sub([MEMBER_SEGMENT_ID], session)

    for sub in final_o_and_m_add_list:
        accounts[sub].create_or_update_sub(
            session, segment_ids=[MEMBER_SEGMENT_ID, ORIENTATION_SEGMENT_ID]
        )

    for sub in final_m_only_add_list:
        accounts[sub].create_or_update_sub(session, segment_ids=[MEMBER_SEGMENT_ID])

    for sub in final_o_only_add_list:
        accounts[sub].create_or_update_sub(
            session, segment_ids=[ORIENTATION_SEGMENT_ID]
        )

    session.close()


def update_flodesk_custom_fields() -> None:
    """
    Update custom fields for all Flodesk subscribers with Neon accounts to reflect Orientation
    and Waiver status. If Neon account doesn't exist in Flodesk, create it.

    Args:
        None

    Returns:
        None
    """

    session = requests.Session()

    all_current_subs = []

    for page in get_current_subs(session):
        subs = [sub for sub in page["data"]]

        all_current_subs.extend(subs)

    current_orientation_true = set()
    current_orientation_false = set()
    current_waiver_true = set()
    current_waiver_false = set()

    for sub in all_current_subs:
        orientation_signed: bool = (
            sub["custom_fields"].get("attendedOrientation") == "True"
        )
        waiver_signed: bool = sub["custom_fields"].get("signedWaiver") == "True"

        if orientation_signed:
            current_orientation_true.add(sub["email"])
        else:
            current_orientation_false.add(sub["email"])

        if waiver_signed:
            current_waiver_true.add(sub["email"])
        else:
            current_waiver_false.add(sub["email"])

    orientation_search = """
    [
        {
            "field": "FacilityTourDate",
            "operator": "NOT_BLANK"
        }
    ]
    """

    waiver_search = """
    [
        {
            "field": "WaiverDate",
            "operator": "NOT_BLANK"
        }
    ]
    """
    orientation_neon_accounts = {}
    waiver_neon_accounts = {}

    orientation_neon_accounts = getNeonAccounts(
        orientation_search, orientation_neon_accounts
    )
    waiver_neon_accounts = getNeonAccounts(waiver_search, waiver_neon_accounts)

    all_neon_accounts: dict[str, Subscriber] = {}

    subs_to_update: dict[str, Subscriber] = {}

    orientation_attended_emails = set()
    waiver_signed_emails = set()

    for account in orientation_neon_accounts.values():
        sub = Subscriber(
            email=account.get("Email 1").lower(),
            first_name=account.get("First Name"),
            last_name=account.get("Last Name"),
            attended_orientation=account.get("FacilityTourDate") is not None,
            signed_waiver=account.get("WaiverDate") is not None,
        )

        orientation_attended_emails.add(sub.email)

        all_neon_accounts[sub.email] = sub

        if sub.email in current_orientation_true:
            continue

        subs_to_update[sub.email] = sub

    for account in waiver_neon_accounts.values():
        sub = Subscriber(
            email=account.get("Email 1").lower(),
            first_name=account.get("First Name"),
            last_name=account.get("Last Name"),
            attended_orientation=account.get("FacilityTourDate") is not None,
            signed_waiver=account.get("WaiverDate") is not None,
        )

        waiver_signed_emails.add(sub.email)

        if not all_neon_accounts.get(sub.email):
            all_neon_accounts[sub.email] = sub

        if sub.email in current_waiver_true:
            continue

        subs_to_update[sub.email] = sub

    incorrect_orientation_field = current_orientation_true - orientation_attended_emails
    incorrect_waiver_field = current_waiver_true - waiver_signed_emails
    all_incorrect = incorrect_orientation_field | incorrect_waiver_field

    for email in all_incorrect:
        if not subs_to_update.get(email):
            subs_to_update[email] = all_neon_accounts[email]

    for sub in subs_to_update.values():
        if sub.attended_orientation:
            sub.create_or_update_sub(session, segment_ids=[ORIENTATION_SEGMENT_ID])
        else:
            sub.create_or_update_sub(session)


def run_flodesk_maintanence(neon_account_dict: dict) -> None:
    update_flodesk_segments(neon_account_dict)

    update_flodesk_custom_fields()


if __name__ == "__main__":
    update_flodesk_custom_fields()
