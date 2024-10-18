############### Asmbly Mailjet API Integrations ##################
#      Mailjet API docs - https://dev.mailjet.com/email/guides/  #
##################################################################
import datetime
import logging
from urllib.parse import quote
from dataclasses import dataclass
from typing import Protocol
from enum import StrEnum

import boto3

from mailjet_rest import Client


class MailjetAction(StrEnum):
    ADD_FORCE = "addforce"
    ADD_NOFORCE = "addnoforce"
    REMOVE = "remove"
    UNSUB = "unsub"


@dataclass
class MJCredentials:
    public_key: str
    secret_key: str


@dataclass
class CustomContactMetadataField:
    datatype: str
    name: str
    namespace: str


@dataclass
class ContactMetadata:
    name: str
    value: str | int | float | bool | datetime.datetime


@dataclass
class Subscriber:
    _email: str
    first_name: str
    last_name: str
    attended_orientation: bool
    signed_waiver: bool
    active_member: bool

    @property
    def email(self) -> str:
        return self._email.lower()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class MailserviceInterface(Protocol):
    def send_email(self) -> None: ...

    def bulk_update_subscribers_in_list(
        self, list_id: str, subscribers: list[Subscriber], action: MailjetAction
    ) -> None | int: ...

    def create_contact_metadata_fields(
        self, metadata: list[CustomContactMetadataField]
    ) -> None: ...

    def update_ind_contact_metadata(
        self, email: str, metadata: list[ContactMetadata]
    ) -> None: ...

    def get_contacts(
        self,
        campaign_id: str | None = None,
        list_id: str | None = None,
        sort_key: str | None = None,
        sort_order: str = "asc",
        count_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> None | tuple[int, list[Subscriber]]: ...


class MJService:
    def __init__(self, credentials: MJCredentials):
        self.client = Client(auth=(credentials.public_key, credentials.secret_key))

    def create_contact_metadata_fields(
        self, metadata: list[CustomContactMetadataField]
    ) -> None:
        if not metadata:
            return

        for field in metadata:
            data = {
                "Datatype": field.datatype,
                "Name": field.name,
                "Namespace": field.namespace,
            }
            response = self.client.contactmetadata.create(data=data)

            if response.status_code != 201:
                logging.error(
                    "Mailjet contact metadata field creation request failed with status code %s. Response: %s.",
                    response.status_code,
                    response.json(),
                )

                return

            logging.info("Mailjet contact metadata field created: %s", response.json())

    def update_ind_contact_metadata(
        self, email: str, metadata: list[ContactMetadata]
    ) -> None:
        if not metadata:
            return

        # URL encode email address
        encoded_email = quote(email)

        data = {
            "Data": [{"Name": field.name, "Value": field.value} for field in metadata]
        }

        response = self.client.contactdata.update(id=encoded_email, data=data)

        if response.status_code != 200:
            logging.error(
                "Mailjet contact metadata update request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return

        logging.info(
            "Mailjet contact metadata updated for %s: %s", email, response.json()
        )

    def bulk_update_subscribers_in_list(
        self, list_id: str, subscribers: list[Subscriber], action: MailjetAction
    ) -> None | int:
        if not subscribers:
            return None

        data = {
            "Action": action.value,
            "Contacts": [
                {
                    "Email": sub.email,
                    "IsExcludedFromCampaigns": False,
                    "Name": sub.full_name,
                    "Properties": {
                        "attended_orientation": sub.attended_orientation,
                        "signed_waiver": sub.signed_waiver,
                        "active_member": sub.active_member,
                    },
                }
                for sub in subscribers
            ],
        }

        response = self.client.contactslist_managemanycontacts.create(
            id=list_id, data=data
        )

        if response.status_code != 201:
            logging.error(
                "Mailjet bulk list update request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return None

        job_id: int = response.json().get("Data")[0].get("JobID")

        return job_id

    def get_job_status(self, job_id: int) -> str | None:
        response = self.client.contactslist_managemanycontacts.get(id=job_id)

        if response.status_code != 200:
            logging.error(
                "Mailjet get job status request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return None

        return response.json().get("Data")[0].get("Status")

    def send_email(self) -> None:
        pass

    def get_contacts(
        self,
        campaign_id: str | None = None,
        list_id: str | None = None,
        sort_key: str | None = None,
        sort_order: str = "asc",
        count_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> None | tuple[int, list[Subscriber]]:
        filters: dict[str, str | int] = {
            "countOnly": 1 if count_only else 0,
            "limit": limit,
            "offset": offset,
        }

        if campaign_id:
            filters["Campaign"] = campaign_id

        if list_id:
            filters["ContactsList"] = list_id

        if sort_key:
            filters["Sort"] = f"{sort_key} {sort_order}"

        response = self.client.contact.get(filters=filters)

        if response.status_code != 200:
            logging.error(
                "Mailjet get contacts request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return None

        contacts_list = response.json().get("Data")

        if not contacts_list:
            logging.info("No contacts found.")
            return None

        return (
            response.json().get("Count"),
            [
                Subscriber(
                    _email=contact.get("Email"),
                    first_name=contact.get("Name").split()[0],
                    last_name=contact.get("Name").split()[1],
                    attended_orientation=contact.get("Properties").get(
                        "attended_orientation", False
                    ),
                    signed_waiver=contact.get("Properties").get("signed_waiver", False),
                    active_member=contact.get("Properties").get("active_member", False),
                )
                for contact in contacts_list
            ],
        )

    def get_all_contacts_in_list(self, list_id: str) -> list[Subscriber] | None:
        offset = 0
        response = self.get_contacts(list_id=list_id, offset=offset)

        if response is None:
            return None

        count = response[0]
        subscribers = response[1]

        while offset < count:
            offset += 50
            response = self.get_contacts(list_id=list_id, offset=offset)

            if response is None:
                return None

            subscribers.extend(response[1])

        return subscribers


def run_mailjet_maintenance(neon_account_dict: dict) -> None:
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

    current_active_mj_list = mailjet.get_all_contacts_in_list(list_id="Active Members")

    if current_active_mj_list is None:
        logging.error("Failed to get active members from Mailjet.")
        return None

    current_active_mj_list = {sub.email for sub in current_active_mj_list}

    accounts: dict[str, Subscriber] = {}
    for account in neon_account_dict:

        account = Subscriber(
            _email=neon_account_dict[account].get("Email 1").lower(),
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

    member_add_list = active_accounts - current_active_mj_list
    member_remove_list = current_active_mj_list - active_accounts

    member_add_list = [accounts[email] for email in member_add_list]
    member_remove_list = [accounts[email] for email in member_remove_list]

    if member_add_list:
        mailjet.bulk_update_subscribers_in_list(
            list_id="Active Members",
            subscribers=member_add_list,
            action=MailjetAction.ADD_NOFORCE,
        )

    if member_remove_list:
        mailjet.bulk_update_subscribers_in_list(
            list_id="Active Members",
            subscribers=member_remove_list,
            action=MailjetAction.REMOVE,
        )
