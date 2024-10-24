############### Asmbly Mailjet API Integrations ##################
#      Mailjet API docs - https://dev.mailjet.com/email/guides/  #
##################################################################
import datetime
import logging

from urllib.parse import quote
from dataclasses import dataclass
from typing import Protocol, Literal, Self, Any
from enum import StrEnum
from zoneinfo import ZoneInfo

import boto3

from pydantic import BaseModel, Field, model_validator, field_serializer
from mailjet_rest import Client  # type: ignore
from neonUtil import getNeonAccounts


logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


class MJContactProperties(StrEnum):
    FIRSTNAME = "first_name"
    LASTNAME = "last_name"
    ATTENDED_ORIENTATION = "attended_orientation"
    SIGNED_WAIVER = "signed_waiver"
    ACTIVE_MEMBER = "active_member"
    ORIENTATION_DATE = "orientation_date"
    LATEST_MEMBERSHIP_END = "latest_membership_end"


class MJContactListNames(StrEnum):
    NEW_MEMBERS = "NewMembers"
    ALL_CONTACTS = "AllContacts"


class MailjetAction(StrEnum):
    ADD_FORCE = "addforce"
    ADD_NOFORCE = "addnoforce"
    REMOVE = "remove"
    UNSUB = "unsub"


class StringProperty(BaseModel):
    name: Literal[
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


class UnknownProperty(BaseModel):
    name: str = Field(..., alias="Name")
    value: datetime.datetime | bool | float | int | str = Field(..., alias="Value")


class MailjetContact(BaseModel):
    created_at: datetime.datetime = Field(..., alias="CreatedAt", exclude=True)
    email: str = Field(..., alias="Email")
    id_: int = Field(..., alias="ID", exclude=True)
    name: str = Field(..., alias="Name")
    is_excluded_from_campaigns: bool = Field(..., alias="IsExcludedFromCampaigns")
    properties: (
        list[StringProperty | BoolProperty | DateProperty | UnknownProperty] | None
    ) = Field(None, alias="Properties")

    @field_serializer("properties")
    def serialize_properties(
        self,
        properties: (
            list[StringProperty | BoolProperty | DateProperty | UnknownProperty] | None
        ),
    ) -> dict[str, Any] | None:
        if properties is None:
            return None

        return {prop.name: prop.value for prop in properties}


class MJContactWithProperties(BaseModel):
    contact_id: int = Field(..., alias="ContactID")
    data: list[DateProperty | BoolProperty | StringProperty | UnknownProperty] = Field(
        ..., alias="Data", discriminator="Name"
    )
    id_: int = Field(..., alias="ID")


class MJContactList(BaseModel):
    id_: int = Field(..., alias="ID")
    name: str = Field(..., alias="Name")
    is_deleted: bool = Field(..., alias="IsDeleted")
    subscriber_count: int = Field(..., alias="SubscriberCount")
    created_at: datetime.datetime = Field(..., alias="CreatedAt")


class MJContactListResponse(BaseModel):
    count: int = Field(..., alias="Count")
    data: list[MJContactList] = Field(..., alias="Data")
    total: int = Field(..., alias="Total")


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


class MJBulkListUpdateRequest(BaseModel):
    action: Literal[
        MailjetAction.ADD_FORCE,
        MailjetAction.ADD_NOFORCE,
        MailjetAction.REMOVE,
        MailjetAction.UNSUB,
    ] = Field(..., alias="Action")
    contacts: list[MailjetContact] = Field(..., alias="Contacts")


class Subscriber(BaseModel):
    email_: str | None
    id_: int | None
    first_name: str
    last_name: str
    attended_orientation: bool
    orientation_date: datetime.datetime | None
    signed_waiver: bool
    active_member: bool
    latest_membership_end: datetime.datetime | None

    @property
    def email(self) -> str | None:
        if self.email_ is not None:
            return self.email_.lower()

        return self.email_

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @model_validator(mode="after")
    def validate_either_email_or_id(self) -> Self:
        if self.email_ is None and self.id_ is None:
            raise ValueError("Either email_ or id_ must be provided for a subscriber.")
        return self


@dataclass
class MJCredentials:
    public_key: str
    secret_key: str


class MailserviceInterface(Protocol):
    def send_email(self) -> None: ...

    def bulk_update_subscribers_in_list(
        self, list_id: str, subscribers: list[Subscriber], action: MailjetAction
    ) -> None | int: ...

    def create_contact_metadata_fields(
        self, metadata: list[CustomContactMetadataField]
    ) -> None: ...

    def get_ind_contact(self, email: str) -> None | Subscriber: ...

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

    def get_all_contacts_in_list(self, list_id: int) -> list[Subscriber] | None: ...


class MJService:
    new_members_list_id: int | None = None
    all_contacts_list_id: int | None = None

    def __init__(self, credentials: MJCredentials) -> None:
        self.client = Client(
            auth=(credentials.public_key, credentials.secret_key), version="v3"
        )

        self.set_list_ids()

    def set_list_ids(self) -> None:
        response = self.client.contactslist.get()

        if not response.ok:
            logging.error(
                "Mailjet contact list retrieval request failed with status code %s. Response: %s.",
                response.status_code,
                response.json(),
            )

            return

        contact_lists = MJContactListResponse.model_validate_json(response.content).data

        lists = {list.name: list.id_ for list in contact_lists if not list.is_deleted}

        self.new_members_list_id = lists.get(MJContactListNames.NEW_MEMBERS, None)
        self.all_contacts_list_id = lists.get(MJContactListNames.ALL_CONTACTS, None)

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
                        "first_name": sub.first_name,
                        "last_name": sub.last_name,
                        "attended_orientation": sub.attended_orientation,
                        "signed_waiver": sub.signed_waiver,
                        "active_member": sub.active_member,
                        "latest_membership_end": (
                            sub.latest_membership_end.astimezone(
                                ZoneInfo("America/Chicago")
                            ).isoformat()
                            if sub.latest_membership_end
                            else None
                        ),
                        "orientation_date": (
                            sub.orientation_date.isoformat()
                            if sub.orientation_date
                            else None
                        ),
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

        contacts_list = MJContactDataResponse.model_validate_json(response.content)

        if len(contacts_list.data) == 0:
            logging.info("No contacts found.")
            return None

        return (
            contacts_list.count,
            [self.validate_contact_props(contact) for contact in contacts_list.data],
        )

    def get_all_contacts_in_list(self, list_id: int) -> list[Subscriber] | None:
        offset = 0
        response = self.get_contacts(list_id=list_id, offset=offset)

        if response is None:
            return None

        count = response[0]
        subscribers = response[1]

        offset += 50

        while offset < count:
            response = self.get_contacts(list_id=list_id, offset=offset)

            if response is None:
                return subscribers

            subscribers.extend(response[1])
            offset += 50

        return subscribers

    def validate_contact_props(
        self,
        contact_data: MJContactWithProperties,
        email: str | None = None,
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
            email_=email,
            id_=contact_data.id_,
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


def update_mj_all_contacts_list(mailjet: MJService, neon_account_dict: dict) -> None:
    all_contacts_mj_list_id = mailjet.all_contacts_list_id

    if all_contacts_mj_list_id is None:
        logging.error(
            "Failed to get %s list ID from Mailjet.", MJContactListNames.ALL_CONTACTS
        )
        return None

    accounts: list[Subscriber] = []
    for account in neon_account_dict:

        account = Subscriber(
            email_=neon_account_dict[account].get("Email 1").lower(),
            id_=neon_account_dict[account].get("MailjetContactID"),
            first_name=neon_account_dict[account].get("First Name"),
            last_name=neon_account_dict[account].get("Last Name"),
            attended_orientation=neon_account_dict[account].get("FacilityTourDate")
            is not None,
            orientation_date=(
                datetime.datetime.strptime(
                    neon_account_dict[account].get("FacilityTourDate"), "%m/%d/%Y"
                ).astimezone(ZoneInfo("America/Chicago"))
                if neon_account_dict[account].get("FacilityTourDate")
                else None
            ),
            active_member=neon_account_dict[account].get(
                "Account Current Membership Status"
            )
            == "Active",
            latest_membership_end=neon_account_dict[account].get(
                "Membership Expiration Date"
            ),
            signed_waiver=neon_account_dict[account].get("WaiverDate") is not None,
        )

        accounts.append(account)

    mailjet.bulk_update_subscribers_in_list(
        list_id=all_contacts_mj_list_id,
        subscribers=accounts,
        action=MailjetAction.ADD_NOFORCE,
    )


def run_mailjet_maintenance() -> None:
    """
    Main entry point for running maintenance tasks on Mailjet.
    """

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

    orientation_search_fields = [
        {"field": "Account Type", "operator": "EQUAL", "value": "Individual"},
        {"field": "Email 1", "operator": "NOT_BLANK"},
        {
            "field": "Email Opt-Out",
            "operator": "EQUAL",
            "value": "At least one email opted in",
        },
        {"field": "FacilityTourDate", "operator": "NOT_BLANK"},
    ]

    waiver_search_fields = [
        {"field": "Account Type", "operator": "EQUAL", "value": "Individual"},
        {"field": "Email 1", "operator": "NOT_BLANK"},
        {
            "field": "Email Opt-Out",
            "operator": "EQUAL",
            "value": "At least one email opted in",
        },
        {"field": "WaiverDate", "operator": "NOT_BLANK"},
    ]

    # This will only retrieve accounts who have had at least one membership at some point
    member_search_fields = [
        {"field": "Account Type", "operator": "EQUAL", "value": "Individual"},
        {"field": "Email 1", "operator": "NOT_BLANK"},
        {
            "field": "Email Opt-Out",
            "operator": "EQUAL",
            "value": "At least one email opted in",
        },
        {
            "field": "Most Recent Membership Only",
            "operator": "EQUAL",
            "value": "Yes",
        },
    ]

    # all_acct_search_fields = [
    #     {"field": "Account Type", "operator": "EQUAL", "value": "Individual"},
    #     {"field": "Email 1", "operator": "NOT_BLANK"},
    #     {
    #         "field": "Email Opt-Out",
    #         "operator": "EQUAL",
    #         "value": "At least one email opted in",
    #     },
    # ]

    orientation_accts: dict[str, dict] = {}
    waiver_accts: dict[str, dict] = {}
    member_accts: dict[str, dict] = {}

    orientation_accts = getNeonAccounts(
        searchFields=orientation_search_fields, neonAccountDict=orientation_accts
    )
    waiver_accts = getNeonAccounts(
        searchFields=waiver_search_fields, neonAccountDict=waiver_accts
    )
    member_accts = getNeonAccounts(
        searchFields=member_search_fields, neonAccountDict=member_accts
    )

    all_accts = orientation_accts | waiver_accts | member_accts

    # all_accts = getNeonAccounts(searchFields=all_acct_search_fields)

    update_mj_all_contacts_list(mailjet, all_accts)

    logging.info("Finished running Mailjet maintenance tasks.")


if __name__ == "__main__":
    run_mailjet_maintenance()
