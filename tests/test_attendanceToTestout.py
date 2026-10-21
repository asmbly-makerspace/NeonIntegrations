"""
Unit tests for attendanceToTestout.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import datetime
import logging

import pytest
from neonUtil import N_baseURL
from neon_mocker import NeonUserMock, NeonEventMock


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


@pytest.mark.parametrize("bad_response", [
    pytest.param({"status_code": 429, "json": [{"code": "429", "message": "Too Many Requests"}]}, id="rate-limited"),
    pytest.param({"status_code": 502, "text": "<html>Bad Gateway</html>"}, id="not-json"),
    pytest.param({"status_code": 200, "json": {"companyAccount": {"accountId": "2"}}}, id="company-account"),
])
def test_main_continues_after_unreadable_account(requests_mock, caplog, bad_response):
    """An unreadable account is skipped and later attendees of the event are still updated"""
    students = [NeonUserMock(1), NeonUserMock(2), NeonUserMock(3)]
    event = NeonEventMock(event_name="Woodshop Safety")
    for student in students:
        event.add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    # The second account's GET returns something other than an individual account
    requests_mock.get(f'{N_baseURL}/accounts/2', **bad_response)

    patch_mocks = [
        requests_mock.patch(f'{N_baseURL}/accounts/{s.account_id}', status_code=200)
        for s in students
    ]

    import attendanceToTestout
    attendanceToTestout.main()

    assert patch_mocks[0].called, "Attendee before the bad account should be updated"
    assert not patch_mocks[1].called, "Unreadable account should not be PATCHed"
    assert patch_mocks[2].called, "Attendee after the bad account should still be updated"
    assert "Update failed for Account ID 2" in caplog.text


def test_main_logs_neon_response_when_patch_fails(requests_mock, caplog):
    """A failed PATCH logs the field, the date sent and Neon's response body"""
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=400,
        json=[{"code": "400", "message": "Invalid value for custom field 84"}],
    )

    import attendanceToTestout
    attendanceToTestout.main()

    expected_date = datetime.date.fromisoformat(event.date).strftime("%m/%d/%Y")
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "400 FAILED!" in errors[0]
    assert f"Account ID {student.account_id}" in errors[0]
    assert f"Event Woodshop Safety ({event.event_id})" in errors[0]
    assert f"Field 84 = {expected_date}" in errors[0]
    assert "Neon errors: 400: Invalid value for custom field 84" in errors[0]


def test_main_summarizes_every_neon_error_on_failed_patch(requests_mock, caplog):
    """All of Neon's {code, message} errors are logged, including ones about other fields"""
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=400,
        json=[
            {"code": "400", "message": "Invalid date of birth"},
            {"code": "400", "message": "Request\nfailed"},
        ],
    )

    import attendanceToTestout
    attendanceToTestout.main()

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "Neon errors: 400: Invalid date of birth; 400: Request failed" in errors[0]


def test_main_truncates_non_json_patch_error(requests_mock, caplog):
    """A non-JSON error page is logged on one line and truncated"""
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    requests_mock.patch(
        f'{N_baseURL}/accounts/{student.account_id}',
        status_code=502,
        text="<html>\n<body>Bad Gateway</body>\n</html>" + "x" * 2000,
    )

    import attendanceToTestout
    attendanceToTestout.main()

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "Neon errors: <html> <body>Bad Gateway</body> </html>xxx" in errors[0]
    assert errors[0].endswith("...")
    assert "x" * 400 not in errors[0]


def test_main_updates_attendees_past_the_first_page(requests_mock):
    """Registrants on later pages of eventRegistrations are still credited"""
    first = NeonUserMock(1)
    second = NeonUserMock(2)
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(first, marked_attended=True)\
        .add_registrant(second, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    def page(account, currentPage):
        return {
            "eventRegistrations": [{
                "registrantAccountId": account.account_id,
                "tickets": [{"attendees": [{"markedAttended": True}]}],
            }],
            "pagination": {"currentPage": currentPage, "pageSize": 30, "totalPages": 2},
        }

    registrationsUrl = f'{N_baseURL}/events/{event.event_id}/eventRegistrations'
    requests_mock.get(f'{registrationsUrl}?currentPage=0', json=page(first, 0))
    requests_mock.get(f'{registrationsUrl}?currentPage=1', json=page(second, 1))

    patch_mocks = [
        requests_mock.patch(f'{N_baseURL}/accounts/{s.account_id}', status_code=200)
        for s in (first, second)
    ]

    import attendanceToTestout
    attendanceToTestout.main()

    assert patch_mocks[0].called
    assert patch_mocks[1].called, "Attendee on the second page should be updated"


def test_main_warns_on_registration_with_several_attendees(requests_mock, caplog):
    """Registrations with more than one attendee are flagged; the first attendee is still used"""
    student = NeonUserMock()
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    requests_mock.get(
        f'{N_baseURL}/events/{event.event_id}/eventRegistrations',
        json={"eventRegistrations": [{
            "registrantAccountId": student.account_id,
            "tickets": [{"attendees": [{"markedAttended": True}, {"markedAttended": True}]}],
        }]}
    )
    patch_mock = requests_mock.patch(f'{N_baseURL}/accounts/{student.account_id}', status_code=200)

    import attendanceToTestout
    attendanceToTestout.main()

    assert patch_mock.called
    assert f"Registration for Account ID {student.account_id} in event {event.event_id} has 2 attendees" in caplog.text


def test_main_skips_registration_without_attendees(requests_mock, caplog):
    """A registration with no tickets or no attendees doesn't stop the rest of the event"""
    no_tickets = NeonUserMock(1)
    no_attendees = NeonUserMock(2)
    student = NeonUserMock(3)
    event = NeonEventMock(event_name="Woodshop Safety")\
        .add_registrant(no_tickets, marked_attended=True)\
        .add_registrant(no_attendees, marked_attended=True)\
        .add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])

    # The first registration has no tickets, the second has no attendees
    requests_mock.get(
        f'{N_baseURL}/events/{event.event_id}/eventRegistrations',
        json={"eventRegistrations": [
            {"registrantAccountId": no_tickets.account_id, "tickets": []},
            {"registrantAccountId": no_attendees.account_id, "tickets": [{"attendees": []}]},
            {"registrantAccountId": student.account_id, "tickets": [{"attendees": [{"markedAttended": True}]}]},
        ]}
    )

    patch_mocks = [
        requests_mock.patch(f'{N_baseURL}/accounts/{s.account_id}', status_code=200)
        for s in (no_tickets, no_attendees, student)
    ]

    import attendanceToTestout
    attendanceToTestout.main()

    assert not patch_mocks[0].called
    assert not patch_mocks[1].called
    assert patch_mocks[2].called, "Attended registrant should still be updated"
    assert "Skipping registration for Account ID 1" in caplog.text
    assert "Skipping registration for Account ID 2" in caplog.text
