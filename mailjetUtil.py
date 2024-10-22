############### Asmbly Mailjet API Integrations ##################
#      Mailjet API docs - https://dev.mailjet.com/email/guides/  #
##################################################################
import pprint
import datetime
import logging

from urllib.parse import quote
from dataclasses import dataclass
from typing import Protocol, Literal
from enum import StrEnum

import boto3

from pydantic import BaseModel, Field
from mailjet_rest import Client  # type: ignore


logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


class MJContactProperties(StrEnum):
    FIRSTNAME = "firstname"
    LASTNAME = "lastname"
    NAME = "name"
    ATTENDED_ORIENTATION = "attended_orientation"
    SIGNED_WAIVER = "signed_waiver"
    ACTIVE_MEMBER = "active_member"
    ORIENTATION_DATE = "orientation_date"
    LATEST_MEMBERSHIP_END = "latest_membership_end"


class MailjetAction(StrEnum):
    ADD_FORCE = "addforce"
    ADD_NOFORCE = "addnoforce"
    REMOVE = "remove"
    UNSUB = "unsub"


class MailjetContact(BaseModel):
    created_at: datetime.datetime = Field(..., alias="CreatedAt")
    email: str = Field(..., alias="Email")
    id_: int = Field(..., alias="ID")
    name: str = Field(..., alias="Name")
    is_excluded_from_campaigns: bool = Field(..., alias="IsExcludedFromCampaigns")


class StringProperty(BaseModel):
    name: Literal[
        MJContactProperties.NAME,
        MJContactProperties.FIRSTNAME,
        MJContactProperties.LASTNAME,
    ] = Field(..., alias="Name")
    value: str = Field(..., alias="Value")


class BoolProperty(BaseModel):
    name: Literal[
        MJContactProperties.ACTIVE_MEMBER,
        MJContactProperties.SIGNED_WAIVER,
        MJContactProperties.ATTENDED_ORIENTATION,
    ] = Field(..., alias="Name")
    value: bool = Field(..., alias="Value")


class DateProperty(BaseModel):
    name: Literal[
        MJContactProperties.ORIENTATION_DATE, MJContactProperties.LATEST_MEMBERSHIP_END
    ] = Field(..., alias="Name")
    value: datetime.datetime = Field(..., alias="Value")


class MJContactWithProperties(BaseModel):
    contact_id: int = Field(..., alias="ContactID")
    data: list[DateProperty | BoolProperty | StringProperty] = Field(
        ..., alias="Data", discriminator="Name"
    )
    id_: int = Field(..., alias="ID")


class MJContactDataResponse(BaseModel):
    count: int = Field(..., alias="Count")
    data: list[MJContactWithProperties] = Field(..., alias="Data")
    total: int = Field(..., alias="Total")


class MJContactResponse(BaseModel):
    count: int = Field(..., alias="Count")
    data: list[MailjetContact] = Field(..., alias="Data")
    total: int = Field(..., alias="Total")


class CustomContactMetadataField(BaseModel):
    datatype: Literal["str", "int", "bool", "float", "datetime"] = Field(
        "str", alias="Datatype"
    )
    name: str = Field(..., alias="Name")
    namespace: Literal["static", "historic"] = Field("static", alias="NameSpace")


@dataclass
class MJCredentials:
    public_key: str
    secret_key: str


@dataclass
class Subscriber:
    _email: str
    first_name: str
    last_name: str
    attended_orientation: bool
    orientation_date: datetime.datetime | None
    signed_waiver: bool
    active_member: bool
    latest_membership_end: datetime.datetime | None

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
        self, email: str, metadata: list[DateProperty | BoolProperty | StringProperty]
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
        self.client = Client(
            auth=(credentials.public_key, credentials.secret_key), version="v3"
        )

    def create_contact_metadata_fields(
        self, metadata: list[CustomContactMetadataField]
    ) -> None:
        if not metadata:
            return

        for field in metadata:
            response = self.client.contactmetadata.create(
                data=field.model_dump(by_alias=True)
            )

            if response.status_code != 201:
                logging.error(
                    "Mailjet contact metadata field creation request failed with status code %s. Response: %s.",
                    response.status_code,
                    response.json(),
                )

                return

            logging.info("Mailjet contact metadata field created: %s", response.json())

    def update_ind_contact_metadata(
        self, email: str, metadata: list[DateProperty | BoolProperty | StringProperty]
    ) -> None:
        if not metadata:
            return

        # URL encode email address
        encoded_email = quote(email)

        data = {"Data": [field.model_dump(by_alias=True) for field in metadata]}

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
        self, list_id: int, subscribers: list[Subscriber], action: MailjetAction
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
                        "latest_membership_end": sub.latest_membership_end,
                        "orientation_date": sub.orientation_date,
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
        list_id: int | None = None,
        contact_email: str | None = None,
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

        if contact_email:
            filters["ContactEmail"] = contact_email

        if campaign_id:
            filters["Campaign"] = campaign_id

        if list_id:
            filters["ContactsList"] = list_id

        if sort_key:
            filters["Sort"] = f"{sort_key} {sort_order}"

        response = self.client.contactdata.get(filters=filters)

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
                    orientation_date=contact.get("Properties").get("orientation_date"),
                    signed_waiver=contact.get("Properties").get("signed_waiver", False),
                    active_member=contact.get("Properties").get("active_member", False),
                    latest_membership_end=contact.get("Properties").get(
                        "latest_membership_end"
                    ),
                )
                for contact in contacts_list
            ],
        )

    def get_all_contacts_in_list(self, list_id: int) -> list[Subscriber] | None:
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

    def validate_contact_props(
        self, contact_data: MJContactWithProperties, email: str
    ) -> Subscriber:
        contact_props = {prop.name: prop.value for prop in contact_data.data}

        latest_membership_end = contact_props.get(
            MJContactProperties.LATEST_MEMBERSHIP_END, None
        )
        assert isinstance(latest_membership_end, (datetime.datetime, type(None)))

        first_name = contact_props.get(MJContactProperties.FIRSTNAME, "")
        assert isinstance(first_name, str)

        last_name = contact_props.get(MJContactProperties.LASTNAME, "")
        assert isinstance(last_name, str)

        attended_orientation = bool(
            contact_props.get(MJContactProperties.ATTENDED_ORIENTATION, False)
        )
        assert isinstance(attended_orientation, bool)

        orientation_date = contact_props.get(MJContactProperties.ORIENTATION_DATE, None)
        assert isinstance(orientation_date, (datetime.datetime, type(None)))

        signed_waiver = bool(
            contact_props.get(MJContactProperties.SIGNED_WAIVER, False)
        )
        assert isinstance(signed_waiver, bool)

        active_member = bool(
            contact_props.get(MJContactProperties.ACTIVE_MEMBER, False)
        )
        assert isinstance(active_member, bool)

        return Subscriber(
            _email=email,
            first_name=first_name,
            last_name=last_name,
            attended_orientation=attended_orientation,
            orientation_date=orientation_date,
            signed_waiver=signed_waiver,
            active_member=active_member,
            latest_membership_end=latest_membership_end,
        )

    def get_ind_contact(self, email: str) -> Subscriber | None:
        encoded_email = quote(email)
        response = self.client.contactdata.get(id=encoded_email)

        if response.status_code == 404:
            logging.info("Contact not found.")
            return None

        if response.status_code != 200:
            logging.error(
                "Mailjet get contact request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return None

        contact = MJContactDataResponse.model_validate_json(response.content).data[0]

        return self.validate_contact_props(contact, email)


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

    current_active_mj_list = mailjet.get_all_contacts_in_list(list_id=1)

    if current_active_mj_list is None:
        logging.error("Failed to get active members from Mailjet.")
        return None

    current_active_mj_emails = {sub.email for sub in current_active_mj_list}

    accounts: list[Subscriber] = []
    active_accounts_emails: set[str] = set()
    for account in neon_account_dict:

        account = Subscriber(
            _email=neon_account_dict[account].get("Email 1").lower(),
            first_name=neon_account_dict[account].get("First Name"),
            last_name=neon_account_dict[account].get("Last Name"),
            attended_orientation=neon_account_dict[account].get("FacilityTourDate")
            is not None,
            orientation_date=datetime.datetime.fromisoformat(
                neon_account_dict[account].get("FacilityTourDate")
            ),
            active_member=neon_account_dict[account].get("validMembership"),
            latest_membership_end=neon_account_dict[account].get("Membership End Date"),
            signed_waiver=neon_account_dict[account].get("WaiverDate") is not None,
        )

        accounts.append(account)

        if account.active_member:
            active_accounts_emails.add(account.email)

    member_add_list_emails = active_accounts_emails - current_active_mj_emails
    member_remove_list_emails = current_active_mj_emails - active_accounts_emails

    member_add_list = list(
        filter(lambda x: x.email in member_add_list_emails, accounts)
    )
    member_remove_list = list(
        filter(lambda x: x.email in member_remove_list_emails, current_active_mj_list)
    )

    if member_add_list:
        mailjet.bulk_update_subscribers_in_list(
            list_id=1,
            subscribers=member_add_list,
            action=MailjetAction.ADD_NOFORCE,
        )

    if member_remove_list:
        mailjet.bulk_update_subscribers_in_list(
            list_id=1,
            subscribers=member_remove_list,
            action=MailjetAction.REMOVE,
        )


if __name__ == "__main__":
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

    # current_active_mj_list = mailjet.get_all_contacts_in_list(list_id=10482790)

    # test = mailjet.get_contacts()

    test = mailjet.get_ind_contact(email="max.chandler@example.com")

    pprint.pprint(test)
