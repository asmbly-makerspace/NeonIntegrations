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


def random_alphanumeric(length: int) -> str:
    """Generate a random alphanumeric string."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


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
    membership = {
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
    return membership


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


def build_account_response(
    accountId: int,
    firstName: str = "John",
    lastName: str = "Doe",
    email: str = "john@example.com",
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
        individualTypes: List of account type names (e.g., ["Paid Staff", "Instructor"])
        accountCustomFields: List of custom field dicts

    Returns:
        Dict matching NeonCRM account GET response format
    """
    account = {
        'accountId': str(accountId),
        'primaryContact': {
            'contactId': random.randint(10000, 99999),
            'firstName': firstName,
            'lastName': lastName,
            'email1': email,
            'addresses': []
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


class NeonMembershipBuilder:
    """
    Fluent builder for constructing NeonCRM membership API responses.

    Example usage:
        builder = NeonMembershipBuilder(account_id=123)
        builder.add_regular_membership('2025-01-01', '2025-12-31', fee=100.0)
        builder.add_ceramics_membership('2025-01-01', '2025-12-31', fee=150.0)

        # Use with requests_mock
        mock_adapter = requests_mock.Adapter()
        mock_adapter.register_uri(
            'GET',
            f'https://api.neoncrm.com/v2/accounts/123/memberships',
            json=builder.build()
        )
    """

    def __init__(self, account_id: int):
        self.account_id = account_id
        self.memberships: List[Dict[str, Any]] = []

    def add_membership(
        self,
        termStartDate: str,
        termEndDate: str,
        status: str = "SUCCEEDED",
        fee: float = 0.0,
        membershipLevelId: int = 1,
        autoRenewal: bool = False
    ) -> 'NeonMembershipBuilder':
        """Add a membership entry (chainable)."""
        self.memberships.append(build_membership_response(
            termStartDate=termStartDate,
            termEndDate=termEndDate,
            status=status,
            fee=fee,
            membershipLevelId=membershipLevelId,
            autoRenewal=autoRenewal
        ))
        return self

    def add_regular_membership(
        self,
        termStartDate: str,
        termEndDate: str,
        fee: float = 100.0,
        status: str = "SUCCEEDED",
        autoRenewal: bool = False
    ) -> 'NeonMembershipBuilder':
        """Add a regular membership (level ID 1)."""
        return self.add_membership(
            termStartDate=termStartDate,
            termEndDate=termEndDate,
            status=status,
            fee=fee,
            membershipLevelId=1,
            autoRenewal=autoRenewal
        )

    def add_ceramics_membership(
        self,
        termStartDate: str,
        termEndDate: str,
        fee: float = 150.0,
        status: str = "SUCCEEDED",
        autoRenewal: bool = False
    ) -> 'NeonMembershipBuilder':
        """Add a ceramics membership (level ID 7)."""
        return self.add_membership(
            termStartDate=termStartDate,
            termEndDate=termEndDate,
            status=status,
            fee=fee,
            membershipLevelId=7,
            autoRenewal=autoRenewal
        )

    def build(self) -> Dict[str, Any]:
        """Build the complete API response."""
        return build_memberships_api_response(self.memberships)

