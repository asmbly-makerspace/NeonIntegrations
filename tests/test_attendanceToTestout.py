"""
Unit tests for attendanceToTestout.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from neonUtil import N_baseURL
from tests.neon_mocker import NeonUserMock, NeonEventMock


def test_main_processes_attended_event(requests_mock):
    """Test that main() processes an event where someone attended and updates their account"""
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=True)

    search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(requests_mock, [event])

    # Mock the PATCH to update the account with the new field
    patch_mock = requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify all expected API calls were made
    assert search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"
    assert account_mocks[0].called, "Account info API should be called"
    assert patch_mock.called, "Account PATCH API should be called to update custom field"

    # Verify the PATCH request contains the correct custom field ID
    patch_body = patch_mock.last_request.json()
    assert "individualAccount" in patch_body
    assert "accountCustomFields" in patch_body["individualAccount"]
    assert patch_body["individualAccount"]["accountCustomFields"][0]["id"] == "84"


def test_main_skips_already_marked_accounts(requests_mock):
    """Test that main() skips accounts that already have the field marked"""
    student = NeonUserMock(custom_fields={'Woodshop Safety': '01/01/2025'})
    event = NeonEventMock(event_name="Woodshop Safety").add_registrant(student, marked_attended=True)

    search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(requests_mock, [event])

    # Mock PATCH but it should NOT be called
    patch_mock = requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify API calls were made
    assert search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"
    assert account_mocks[0].called, "Account info API should be called"

    # Verify PATCH was NOT called since account already has the field
    assert not patch_mock.called, "PATCH should not be called when field already exists"


def test_main_handles_empty_search_results(requests_mock):
    """Test that main() handles empty event search results gracefully"""
    search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify event search was called
    assert search_mock.called, "Event search API should be called"


def test_main_skips_event_with_no_matching_field(requests_mock):
    student = NeonUserMock()
    event = NeonEventMock(event_name="Basket Weaving")\
        .add_registrant(student, marked_attended=True)

    search_mock, [(registrants_mock, _)] = NeonEventMock.mock_events(requests_mock, [event])

    import attendanceToTestout
    attendanceToTestout.main()

    assert search_mock.called, "Event search API should be called"
    assert not registrants_mock.called, "Event registrants API should not be called for unmapped events"


def test_main_handles_no_registrants(requests_mock):
    event = NeonEventMock(event_name="Woodshop Safety")

    search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": [event.search_result()]}
    )
    registrants_mock = requests_mock.get(
        f'{N_baseURL}/events/{event.event_id}/eventRegistrations',
        json={"eventRegistrations": None}
    )

    import attendanceToTestout
    attendanceToTestout.main()

    assert search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"


def test_main_skips_event_with_no_attended_registrants(requests_mock):
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=False)

    search_mock, [(registrants_mock, _)] = NeonEventMock.mock_events(requests_mock, [event])

    patch_mock = requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    assert search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"
    assert not patch_mock.called, "PATCH should not be called when no one attended"