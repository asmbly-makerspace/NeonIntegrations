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

    # Mock the account search by attendee email
    account_search_mock = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={"searchResults": [student.search_result()], "pagination": {"totalPages": 1, "currentPage": 0}}
    )

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
    assert account_search_mock.called, "Account search API should be called"
    assert patch_mock.called, "Account PATCH API should be called to update custom field"

    # Verify the PATCH request contains the correct custom field ID
    patch_body = patch_mock.last_request.json()
    assert "individualAccount" in patch_body
    assert "accountCustomFields" in patch_body["individualAccount"]
    assert patch_body["individualAccount"]["accountCustomFields"][0]["id"] == "84"


def test_main_skips_already_marked_accounts(requests_mock):
    """Test that main() skips accounts that already have the field marked"""
    student = NeonUserMock(custom_fields={'Woodshop Safety': '01/01/2025'})
    event = NeonEventMock().add_registrant(student, marked_attended=True)

    search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(requests_mock, [event])

    # Mock the account search by attendee email
    account_search_mock = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={"searchResults": [student.search_result()], "pagination": {"totalPages": 1, "currentPage": 0}}
    )

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
    assert account_search_mock.called, "Account search API should be called"

    # Verify PATCH was NOT called since account already has the field
    assert not patch_mock.called, "PATCH should not be called when field already exists"


def test_main_handles_multiple_attendees_by_email(requests_mock):
    """Test that main() updates attendance for each attended attendee using their email"""
    registrant = NeonUserMock(firstName="Reg", lastName="Owner")
    attendee_1 = NeonUserMock(firstName="Ann", lastName="Attended")
    attendee_2 = NeonUserMock(firstName="Skip", lastName="Absent")

    attendees = [
        {
            "firstName": attendee_1.firstName,
            "lastName": attendee_1.lastName,
            "email": attendee_1.email,
            "registrationStatus": "SUCCEEDED",
            "markedAttended": True,
        },
        {
            "firstName": attendee_2.firstName,
            "lastName": attendee_2.lastName,
            "email": attendee_2.email,
            "registrationStatus": "SUCCEEDED",
            "markedAttended": False,
        },
    ]

    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(registrant, attendees=attendees)

    search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(requests_mock, [event])
    attendee_1.mock(requests_mock)

    def _matches_email(email):
        def _matcher(request):
            payload = request.json()
            return payload["searchFields"][0]["value"] == email
        return _matcher

    account_search_mock_1 = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={"searchResults": [attendee_1.search_result()], "pagination": {"totalPages": 1, "currentPage": 0}},
        additional_matcher=_matches_email(attendee_1.email),
    )
    account_search_mock_2 = requests_mock.post(
        f'{N_baseURL}/accounts/search',
        json={"searchResults": [attendee_2.search_result()], "pagination": {"totalPages": 1, "currentPage": 0}},
        additional_matcher=_matches_email(attendee_2.email),
    )

    patch_mock_1 = requests_mock.patch(
        f'{N_baseURL}/accounts/{attendee_1.account_id}',
        status_code=200
    )
    patch_mock_2 = requests_mock.patch(
        f'{N_baseURL}/accounts/{attendee_2.account_id}',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    assert search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"
    assert account_mocks[0].called, "Registrant account API should be called"
    assert account_search_mock_1.called, "Account search API should be called for attendee 1"
    assert not account_search_mock_2.called, "Account search API should not be called for non-attended attendee"
    assert patch_mock_1.called, "Attended attendee should be updated"
    assert not patch_mock_2.called, "Non-attended attendee should not be updated"


def test_main_handles_empty_search_results(requests_mock):
    """Test that main() handles empty event search results gracefully"""
    search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify event search was called
    assert search_mock.called, "Event search API should be called"
