"""
Helper functions for building NeonCRM API response fixtures.

This module provides utilities for creating realistic NeonCRM API responses
that match the actual API schema. Use these in conjunction with requests-mock
to test code that calls the NeonCRM API without duplicating business logic.

API Reference: https://developer.neoncrm.com/api-v2/
"""


import random
import string
from typing import List, Dict, Any, Optional
import neonUtil
from datetime import timedelta


# resets history, calls fn, then asserts each request occurred in order
def assert_history(requests_mock, fn, expected_history):
    requests_mock.reset_mock() # reset history
    fn()
    # Strip query params for comparison (use base URL only)
    history = [(r.method, r.url.split('?')[0]) for r in requests_mock.request_history]
    for i, expected in enumerate(expected_history):
        assert expected == history[i]
    assert len(history) == len(expected_history)


def today_plus(days_offset):
    """Return a date string relative to today."""
    return str(neonUtil.today + timedelta(days=days_offset))


def build_membership_response(
    termStartDate: str,
    termEndDate: str,
    status: str = "SUCCEEDED",
    fee: float = 0.0,
    membershipLevelId: int = 1,
    autoRenewal: bool = False,
    membershipId: Optional[int] = None,
    membershipName: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a single membership entry matching NeonCRM API schema.

    Reference: https://developer.neoncrm.com/api-v2/#/Accounts/listMembershipUsingGET

    Args:
        termStartDate: ISO date string (YYYY-MM-DD) for membership start
        termEndDate: ISO date string (YYYY-MM-DD) for membership end
        status: Payment status (SUCCEEDED, FAILED, PENDING, etc.)
        fee: Membership fee (0.0 for comped memberships)
        membershipLevelId: Neon membership level ID (1=Regular, 7=Ceramics)
        autoRenewal: Whether membership auto-renews
        membershipId: Optional membership transaction ID
        membershipName: Optional membership level name

    Returns:
        Dict matching NeonCRM membership API response format
    """
    return {
        'membershipId': membershipId or random.randint(10000, 99999),
        'termStartDate': termStartDate,
        'termEndDate': termEndDate,
        'status': status,
        'fee': fee,
        'autoRenewal': autoRenewal,
        'membershipLevel': {
            'id': membershipLevelId,
            'name': membershipName or (
                'Ceramics Membership' if membershipLevelId == 7 else 'Regular Membership'
            )
        }
    }


def build_memberships_api_response(memberships: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build the complete NeonCRM memberships API response.

    Reference: https://developer.neoncrm.com/api-v2/#/Accounts/listMembershipUsingGET

    Args:
        memberships: List of membership dicts (from build_membership_response)

    Returns:
        Dict matching NeonCRM GET /accounts/{id}/memberships response format
    """
    return {
        'memberships': memberships
    }


def build_account_api_response(
    accountId: int,
    firstName: str = "John",
    lastName: str = "Doe",
    email: str = "john@example.com",
    phone: Optional[str] = None,
    individualTypes: Optional[List[str]] = None,
    accountCustomFields: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Build a NeonCRM account response matching the API schema.

    Reference: https://developer.neoncrm.com/api-v2/#/Accounts/retrieveIndividualAccountUsingGET

    Args:
        accountId: Neon account ID
        firstName: First name
        lastName: Last name
        email: Primary email address
        phone: Primary phone number
        individualTypes: List of account type names (e.g., ["Paid Staff", "Instructor"])
        accountCustomFields: List of custom field dicts

    Returns:
        Dict matching NeonCRM account GET response format
    """
    addresses = [{'phone1': phone}] if phone else []
    account = {
        'accountId': accountId,
        'primaryContact': {
            'contactId': random.randint(10000, 99999),
            'firstName': firstName,
            'lastName': lastName,
            'email1': email,
            'addresses': addresses
        },
        'individualTypes': [{'id': i, 'name': name} for i, name in enumerate(individualTypes or [], start=1)],
        'accountCustomFields': accountCustomFields or []
    }
    return {'individualAccount': account}


def build_custom_field(fieldId: int, name: str, value: Any) -> Dict[str, Any]:
    """
    Build a custom field entry for NeonCRM API responses.

    Args:
        fieldId: Custom field ID
        name: Field name (e.g., "OpenPathID", "DiscourseID")
        value: Field value

    Returns:
        Dict matching custom field format in Neon API
    """
    return {
        'id': str(fieldId),
        'name': name,
        'value': str(value) if value is not None else None
    }


def build_search_result(
    accountId: str,
    firstName: str = "John",
    lastName: str = "Doe",
    email: str = "john@example.com",
    individualTypes: Optional[List[str]] = None,
    membershipExpirationDate: Optional[str] = None,
    membershipStartDate: Optional[str] = None,
    customFields: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a search result entry matching NeonCRM search API response.

    Search results have a flatter structure than full account GET responses.

    Reference: https://developer.neoncrm.com/api-v2/#/Accounts/searchIndividualAccountsUsingPOST

    Args:
        accountId: Account ID as string
        firstName: First name
        lastName: Last name
        email: Primary email
        individualTypes: List of type names (returned as pipe-separated string)
        membershipExpirationDate: ISO date string
        membershipStartDate: ISO date string
        customFields: Dict of custom field names to values

    Returns:
        Dict matching a single search result entry
    """
    result = {
        'Account ID': accountId,
        'First Name': firstName,
        'Last Name': lastName,
        'Email 1': email,
        'Membership Expiration Date': membershipExpirationDate,
        'Membership Start Date': membershipStartDate,
    }

    # Individual types are returned as pipe-separated string in search results
    if individualTypes:
        result['Individual Type'] = ' | '.join(individualTypes)

    # Add custom fields as top-level keys (matching search output format)
    if customFields:
        result.update(customFields)

    return result

# Map common custom field names to their IDs (from neonUtil.py)
field_id_map = {
    'OpenPathID': 178,
    'DiscourseID': 85,
    'WaiverDate': 179,
    'FacilityTourDate': 77,
    'OrientationDate': 77,
    'AccessSuspended': 180,
    'KeyCardID': 88,
    'CsiDate': 1248,
    'Shaper Origin': 274,
    'Woodshop Specialty Tools': 440,
    'Woodshop Safety': 84,
}

class NeonEventMock:
    """
    Mock for NeonCRM event API responses.

    Example usage:
        student = NeonMock(123, "Test", "Student", phone="555-1234")
        event = NeonEventMock(event_id="1", event_name="Woodworking 101")\
            .add_registrant(student)
        search_mock, event_mocks = NeonEventMock.mock_events(requests_mock, [event])
    """

    def __init__(
        self,
        event_id: str = "12345",
        event_name: str = "Test Class",
        teacher: str = "John Doe",
        date: str = None,
        start_time: str = "10:00:00",
        end_time: str = "12:00:00",
    ):
        self.event_id = event_id
        self.event_name = event_name
        self.teacher = teacher
        self.date = date or str(neonUtil.today)
        self.start_time = start_time
        self.end_time = end_time
        self._registrants: List[tuple] = []  # List of (NeonMock, status, marked_attended)

    def add_registrant(self, account: 'NeonMock', status: str = "SUCCEEDED", marked_attended: bool = False) -> 'NeonEventMock':
        """Add a registrant to this event."""
        self._registrants.append((account, status, marked_attended))
        return self

    def search_result(self) -> Dict[str, Any]:
        """Return event data in the format returned by /events/search."""
        return {
            "Event ID": self.event_id,
            "Event Name": self.event_name,
            "Event Topic": self.teacher,
            "Event Start Date": self.date,
            "Event Start Time": self.start_time,
            "Event End Date": self.date,
            "Event End Time": self.end_time,
            "Event Registration Attendee Count": len(self._registrants),
            "Registrants": len(self._registrants),
            "Hold To Waiting List": "No",
            "Waiting List Status": "Open"
        }

    def mock(self, requests_mock):
        """Mock the event's registrants endpoint and all registrant accounts.

        Returns a tuple of (registrants_mock, [account_mocks]).
        Account mocks are also stored on each NeonMock instance as _account_mock.
        """
        event_registrations = []
        account_mocks = []
        for account, status, marked_attended in self._registrants:
            event_registrations.append({
                "registrantAccountId": account.account_id,
                "tickets": [{
                    "attendees": [{
                        "firstName": account.firstName,
                        "lastName": account.lastName,
                        "registrationStatus": status,
                        "markedAttended": marked_attended
                    }]
                }]
            })
            account.mock(requests_mock)
            account_mocks.append(account._account_mock)

        registrants_mock = requests_mock.get(
            f'https://api.neoncrm.com/v2/events/{self.event_id}/eventRegistrations',
            json={"eventRegistrations": event_registrations}
        )

        return registrants_mock, account_mocks

    @classmethod
    def mock_events(cls, requests_mock, events: List['NeonEventMock']):
        """Mock the events search endpoint and all event registrant endpoints.

        Returns a tuple of (search_mock, [event_mocks]) where each event_mock
        is a tuple of (registrants_mock, [account_mocks]).
        """
        search_mock = requests_mock.post(
            'https://api.neoncrm.com/v2/events/search',
            json={"searchResults": [e.search_result() for e in events]}
        )

        event_mocks = [e.mock(requests_mock) for e in events]

        return search_mock, event_mocks


class NeonMock:
    """
    Fluent builder for constructing NeonCRM membership API responses.

    Example usage:
        account = NeonMock(account_id=123)\
            .add_regular_membership('2025-01-01', '2025-12-31', fee=100.0)\
            .add_ceramics_membership('2025-01-01', '2025-12-31', fee=150.0)\
            .mock(requests_mock) # mocks Neon GET endpoints
    """

    def __init__(
        self,
        account_id: int,
        firstName: str = "John",
        lastName: str = "Doe",
        email: str = None,
        phone: str = None,
        individualTypes: Optional[List[str]] = None,
        custom_fields: dict = None,
        open_path_id: int = None,
        waiver_date: str = None,
        facility_tour_date: str = None,
        access_suspended: bool = False
    ):
        self.account_id = account_id
        self.open_path_id = open_path_id
        self.firstName = firstName
        self.lastName = lastName
        self.email = email or f'{firstName}.{lastName}@example.com'
        self.phone = phone
        self.individualTypes = individualTypes
        self.memberships: List[Dict[str, Any]] = []

        # Allow passing common fields as direct arguments
        fields_dict = custom_fields or {}
        if open_path_id is not None:
            fields_dict['OpenPathID'] = open_path_id
        if waiver_date is not None:
            fields_dict['WaiverDate'] = waiver_date
        if facility_tour_date is not None:
            fields_dict['FacilityTourDate'] = facility_tour_date
        if access_suspended:
            fields_dict['AccessSuspended'] = 'Yes'

        self.accountCustomFields = [
            dict(id=str(field_id_map[name]), name=name, value=value)
            for name, value in fields_dict.items()
        ]

    def add_membership(
        self,
        membershipLevelId: int,
        termStartDate: str,
        termEndDate: str,
        status: str = "SUCCEEDED",
        fee: float = 0.0,
        autoRenewal: bool = False
    ) -> 'NeonMock':
        self.memberships.append(build_membership_response(
            termStartDate=termStartDate,
            termEndDate=termEndDate,
            status=status,
            fee=fee,
            membershipLevelId=membershipLevelId,
            autoRenewal=autoRenewal
        ))
        return self

    def mock(self, requests_mock):
        self._account_mock = requests_mock.get(
            f'https://api.neoncrm.com/v2/accounts/{self.account_id}',
            json=build_account_api_response(
                accountId=self.account_id,
                firstName=self.firstName,
                lastName=self.lastName,
                email=self.email,
                phone=self.phone,
                individualTypes=self.individualTypes,
                accountCustomFields=self.accountCustomFields,
            )
        )

        requests_mock.get(
            f'https://api.neoncrm.com/v2/accounts/{self.account_id}/memberships',
            json=build_memberships_api_response(self.memberships),
        )

        return neonUtil.getMemberById(self.account_id)

