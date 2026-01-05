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
from neonUtil import N_baseURL
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

    event_id is random by default, so tests must reference the mock's properties
    (e.g., event.event_id) rather than hardcoding values.

    When creating multiple NeonEventMock instances in a test, pass explicit distinct IDs.

    Example usage:
        student = NeonUserMock()
        event = NeonEventMock(event_name="Woodworking 101").add_registrant(student)
        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

    Example with multiple events:
        event1 = NeonEventMock(1, event_name="Woodworking 101")
        event2 = NeonEventMock(2, event_name="Advanced Woodworking")
        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event1, event2])
    """

    def __init__(
        self,
        event_id: int = None,
        event_name: str = "Test Class",
        teacher: str = "John Doe",
        date: str = None,
        start_time: str = "10:00:00",
        end_time: str = "12:00:00",
        capacity: int = 10,
    ):
        self.event_id = event_id if event_id is not None else random.randint(10000, 99999)
        self.event_name = event_name
        self.teacher = teacher
        self.date = date or str(neonUtil.today)
        self.start_time = start_time
        self.end_time = end_time
        self.capacity = capacity
        self._registrants: List[tuple] = []  # List of (NeonUserMock, status, marked_attended)

    def add_registrant(self, account: 'NeonUserMock', status: str = "SUCCEEDED", marked_attended: bool = False) -> 'NeonEventMock':
        """Add a registrant to this event."""
        self._registrants.append((account, status, marked_attended))
        return self

    def search_result(self) -> Dict[str, Any]:
        """Return event data in the format returned by /events/search."""
        return {
            "Event ID": str(self.event_id),
            "Event Name": self.event_name,
            "Event Topic": self.teacher,
            "Event Start Date": self.date,
            "Event Start Time": self.start_time,
            "Event End Date": self.date,
            "Event End Time": self.end_time,
            "Event Registration Attendee Count": len(self._registrants),
            "Registrants": len(self._registrants),
            "Event Capacity": self.capacity,
            "Hold To Waiting List": "No",
            "Waiting List Status": "Open"
        }

    def mock(self, requests_mock):
        """Mock the event's registrants endpoint and all registrant accounts.

        Returns a tuple of (registrants_mock, [account_mocks]).
        Account mocks are also stored on each NeonUserMock instance as _account_mock.
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
            f'{N_baseURL}/events/{self.event_id}/eventRegistrations',
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
            f'{N_baseURL}/events/search',
            json={"searchResults": [e.search_result() for e in events]}
        )

        event_mocks = [e.mock(requests_mock) for e in events]

        return search_mock, event_mocks


class NeonUserMock:
    """
    Fluent builder for constructing NeonCRM account/membership API responses.

    account_id is random by default, so tests must reference the mock's properties
    (e.g., student.account_id) rather than hardcoding values.

    When creating multiple NeonUserMock instances in a test, pass explicit distinct IDs.

    Example usage:
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)
        NeonEventMock.mock_events(requests_mock, [event])
        patch_mock = requests_mock.patch(f'{N_baseURL}/accounts/{student.account_id}')

    Example with multiple accounts:
        student1 = NeonUserMock(1)
        student2 = NeonUserMock(2)
        search_mock, _ = NeonUserMock.mock_search(requests_mock, [student1, student2])
    """

    def __init__(
        self,
        account_id: int = None,
        firstName: str = "John",
        lastName: str = "Doe",
        email: str = None,
        phone: str = "123-4567",
        individualTypes: Optional[List[str]] = None,
        custom_fields: dict = None,
        open_path_id: int = None,
        waiver_date: str = None,
        facility_tour_date: str = None,
        access_suspended: bool = False
    ):
        self.account_id = account_id if account_id is not None else random.randint(10000, 99999)
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
    ) -> 'NeonUserMock':
        self.memberships.append(build_membership_response(
            termStartDate=termStartDate,
            termEndDate=termEndDate,
            status=status,
            fee=fee,
            membershipLevelId=membershipLevelId,
            autoRenewal=autoRenewal
        ))
        return self

    def search_result(self) -> Dict[str, Any]:
        """Return account data in the format returned by /accounts/search."""
        # Get membership dates from the memberships list
        membership_exp = None
        membership_start = None
        for m in self.memberships:
            if m.get('status') == 'SUCCEEDED':
                end = m.get('termEndDate')
                start = m.get('termStartDate')
                if end and (membership_exp is None or end > membership_exp):
                    membership_exp = end
                if start and (membership_start is None or start < membership_start):
                    membership_start = start

        result = {
            'Account ID': str(self.account_id),
            'First Name': self.firstName,
            'Last Name': self.lastName,
            'Email 1': self.email,
            'Membership Expiration Date': membership_exp,
            'Membership Start Date': membership_start,
        }

        # Individual types are returned as pipe-separated string in search results
        if self.individualTypes:
            result['Individual Type'] = ' | '.join(self.individualTypes)

        # Add custom fields as top-level keys (matching search output format)
        for field in self.accountCustomFields:
            result[field['name']] = field['value']

        return result

    def mock(self, requests_mock):
        self._account_mock = requests_mock.get(
            f'{N_baseURL}/accounts/{self.account_id}',
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
            f'{N_baseURL}/accounts/{self.account_id}/memberships',
            json=build_memberships_api_response(self.memberships),
        )

        return neonUtil.getMemberById(self.account_id)

    @classmethod
    def mock_search(cls, requests_mock, accounts: List['NeonUserMock']):
        """Mock the accounts search endpoint and all account endpoints."""
        total_pages = 1 if accounts else 0
        search_mock = requests_mock.post(
            f'{N_baseURL}/accounts/search',
            json={
                "searchResults": [a.search_result() for a in accounts],
                "pagination": {"totalPages": total_pages, "currentPage": 0}
            }
        )
        account_results = [a.mock(requests_mock) for a in accounts]
        return search_mock, account_results

