"""
Helper for building complete Neon account fixtures for tests.

This module provides utilities for creating test accounts that work with
requests-mock to simulate the full NeonCRM API workflow (GET account + GET memberships).

Example usage:
    def test_something(neon_api_mock):
        from tests.neon_account_builder import setup_neon_account_with_membership

        # Setup a complete account with membership API responses
        account = setup_neon_account_with_membership(
            neon_api_mock,
            account_id=123,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            memberships=[
                ('2025-01-01', '2025-12-31', 100.0, 1, False),  # (start, end, fee, level_id, auto_renew)
            ],
            custom_fields={
                'OpenPathID': 5001,
                'WaiverDate': '2024-12-01',
                'FacilityTourDate': '2024-12-02'
            }
        )

        # Now call neonUtil.getMemberById(123) and it will use the mocked responses
        result = neonUtil.getMemberById(123)
"""
import neonUtil
from tests.neon_api_fixtures import (
    build_account_response,
    build_custom_field,
    NeonMembershipBuilder
)


def setup_neon_account_with_membership(
    requests_mock,
    account_id: int,
    first_name: str = "John",
    last_name: str = "Doe",
    email: str = "john@example.com",
    individual_types: list = None,
    memberships: list = None,
    custom_fields: dict = None,
    open_path_id: int = None,
    waiver_date: str = None,
    facility_tour_date: str = None,
    access_suspended: bool = False
):
    """
    Setup complete NeonCRM API mocks for a user account with memberships.

    This creates mock responses for both:
    1. GET /accounts/{id} (account details)
    2. GET /accounts/{id}/memberships (membership history)

    Args:
        requests_mock: The requests_mock fixture
        account_id: Neon account ID
        first_name: First name
        last_name: Last name
        email: Primary email
        individual_types: List of type names (e.g., ["Paid Staff", "Instructor"])
        memberships: List of tuples (start_date, end_date, fee, level_id, auto_renew)
                    Example: [('2025-01-01', '2025-12-31', 100.0, 1, False)]
        custom_fields: Dict of custom field names to values
        open_path_id: OpenPath ID (alternative to custom_fields['OpenPathID'])
        waiver_date: Waiver date (alternative to custom_fields['WaiverDate'])
        facility_tour_date: Tour date (alternative to custom_fields['FacilityTourDate'])
        access_suspended: Whether access is suspended

    Returns:
        Dict representing the account as it would be returned by neonUtil.getMemberById()
    """
    # Build custom fields list
    custom_fields_list = []
    fields_dict = custom_fields or {}

    # Allow passing common fields as direct arguments
    if open_path_id is not None:
        fields_dict['OpenPathID'] = open_path_id
    if waiver_date is not None:
        fields_dict['WaiverDate'] = waiver_date
    if facility_tour_date is not None:
        fields_dict['FacilityTourDate'] = facility_tour_date
    if access_suspended:
        fields_dict['AccessSuspended'] = 'Yes'

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
    }

    for name, value in fields_dict.items():
        field_id = field_id_map.get(name, 999)  # Use 999 for unknown fields
        custom_fields_list.append(build_custom_field(field_id, name, value))

    # Mock GET /accounts/{id}
    account_response = build_account_response(
        accountId=account_id,
        firstName=first_name,
        lastName=last_name,
        email=email,
        individualTypes=individual_types,
        accountCustomFields=custom_fields_list
    )

    requests_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{account_id}',
        json=account_response
    )

    # Mock GET /accounts/{id}/memberships
    builder = NeonMembershipBuilder(account_id=account_id)
    if memberships:
        for membership in memberships:
            if len(membership) == 5:
                start, end, fee, level_id, auto_renew = membership
                builder.add_membership(start, end, fee=fee, membershipLevelId=level_id, autoRenewal=auto_renew)
            elif len(membership) == 4:
                start, end, fee, level_id = membership
                builder.add_membership(start, end, fee=fee, membershipLevelId=level_id)
            else:
                raise ValueError(f"Membership tuple must have 4 or 5 elements, got {len(membership)}")

    requests_mock.get(
        f'https://api.neoncrm.com/v2/accounts/{account_id}/memberships',
        json=builder.build()
    )

    # Return what the account would look like after calling getMemberById
    # (for convenience in tests that need to check the account structure)
    return {
        'Account ID': str(account_id),
        'First Name': first_name,
        'Last Name': last_name,
        'Email 1': email,
        'fullName': f"{first_name} {last_name}",
        'OpenPathID': open_path_id,
        'WaiverDate': waiver_date,
        'FacilityTourDate': facility_tour_date,
        'individualTypes': [{'name': t} for t in (individual_types or [])]
    }


def build_staff_account(requests_mock, account_id: int, **kwargs):
    """Convenience builder for staff accounts."""
    types = kwargs.pop('individual_types', [])
    types.append(neonUtil.STAFF_TYPE)
    return setup_neon_account_with_membership(
        requests_mock,
        account_id,
        individual_types=types,
        **kwargs
    )


def build_member_with_facility_access(
    requests_mock,
    account_id: int,
    membership_start: str = '2025-01-01',
    membership_end: str = '2025-12-31',
    fee: float = 100.0,
    waiver_date: str = '2024-12-01',
    facility_tour_date: str = '2024-12-02',
    **kwargs
):
    """Convenience builder for regular members with facility access."""
    return setup_neon_account_with_membership(
        requests_mock,
        account_id,
        memberships=[(membership_start, membership_end, fee, neonUtil.MEMBERSHIP_ID_REGULAR, False)],
        waiver_date=waiver_date,
        facility_tour_date=facility_tour_date,
        **kwargs
    )


def build_ceramics_member_with_access(
    requests_mock,
    account_id: int,
    membership_start: str = '2025-01-01',
    membership_end: str = '2025-12-31',
    fee: float = 150.0,
    waiver_date: str = '2024-12-01',
    facility_tour_date: str = '2024-12-02',
    csi_date: str = '2024-12-03',
    **kwargs
):
    """Convenience builder for ceramics members with full access."""
    custom_fields = kwargs.pop('custom_fields', {})
    custom_fields['CsiDate'] = csi_date

    return setup_neon_account_with_membership(
        requests_mock,
        account_id,
        memberships=[(membership_start, membership_end, fee, neonUtil.MEMBERSHIP_ID_CERAMICS, False)],
        waiver_date=waiver_date,
        facility_tour_date=facility_tour_date,
        custom_fields=custom_fields,
        **kwargs
    )