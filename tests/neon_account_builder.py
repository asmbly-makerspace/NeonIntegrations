"""
Helper for building complete Neon account fixtures for tests.

This module provides utilities for creating test accounts that work with
requests-mock to simulate the full NeonCRM API workflow (GET account + GET memberships).

Example usage:
    def test_something(neon_api_mock):
        from tests.neon_account_builder import setup_neon_account

        # Setup a complete account with membership API responses
        account = setup_neon_account(
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
from datetime import timedelta

import neonUtil


def today_plus(days_offset):
    """Return a date string relative to today."""
    return str(neonUtil.today + timedelta(days=days_offset))


from tests.neon_api_fixtures import (
    build_account_response,
    build_custom_field,
    NeonMock
)


def setup_neon_account(
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
    # Mock GET /accounts/{id} and /accounts/{id}/memberships
    builder = NeonMock(
        account_id,
        firstName=first_name,
        lastName=last_name,
        email=email,
        individualTypes=individual_types,
        custom_fields=custom_fields,
        open_path_id=open_path_id,
        waiver_date=waiver_date,
        facility_tour_date=facility_tour_date,
        access_suspended=access_suspended,
   )
    if memberships:
        for membership in memberships:
            if len(membership) == 5:
                start, end, fee, level_id, auto_renew = membership
                builder.add_membership(level_id, start, end, fee=fee, autoRenewal=auto_renew)
            elif len(membership) == 4:
                start, end, fee, level_id = membership
                builder.add_membership(level_id, start, end, fee=fee)
            else:
                raise ValueError(f"Membership tuple must have 4 or 5 elements, got {len(membership)}")
    builder.mock(requests_mock)

    # Return what the account would look like after calling getMemberById
    # (for convenience in tests that need to check the account structure)
    return neonUtil.getMemberById(account_id)
