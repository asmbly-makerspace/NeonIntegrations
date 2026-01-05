"""
Unit tests for attendanceToTestout.py

Tests the main() function by mocking only network interactions (HTTP requests).
"""

import pytest
from neonUtil import N_baseURL
from tests.mock_events import MockEventBuilder


def test_main_processes_attended_event(requests_mock):
    """Test that main() processes an event where someone attended and updates their account"""
    # Mock event search - return one event
    event = (MockEventBuilder()
             .with_event_name("Woodshop Safety with John")
             .with_event_id("123")
             .build())

    event_search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": [event]}
    )

    # Mock registrants - one person attended
    registrants_mock = requests_mock.get(
        f'{N_baseURL}/events/123/eventRegistrations',
        json={
            "eventRegistrations": [{
                "registrantAccountId": 456,
                "tickets": [{
                    "attendees": [{
                        "markedAttended": True,
                        "firstName": "Test",
                        "lastName": "User"
                    }]
                }]
            }]
        }
    )

    # Mock account info - no existing Woodshop Safety field (id 84)
    account_mock = requests_mock.get(
        f'{N_baseURL}/accounts/456',
        json={
            "individualAccount": {
                "accountCustomFields": []
            }
        }
    )

    # Mock the PATCH to update the account with the new field
    patch_mock = requests_mock.patch(
        f'{N_baseURL}/accounts/456',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify all expected API calls were made
    assert event_search_mock.called, "Event search API should be called"
    assert registrants_mock.called, "Event registrants API should be called"
    assert account_mock.called, "Account info API should be called"
    assert patch_mock.called, "Account PATCH API should be called to update custom field"

    # Verify the PATCH request contains the correct custom field ID
    patch_body = patch_mock.last_request.json()
    assert "individualAccount" in patch_body
    assert "accountCustomFields" in patch_body["individualAccount"]
    assert patch_body["individualAccount"]["accountCustomFields"][0]["id"] == "84"


def test_main_skips_already_marked_accounts(requests_mock):
    """Test that main() skips accounts that already have the field marked"""
    # Mock event search
    event = (MockEventBuilder()
             .with_event_name("Woodshop Safety with John")
             .with_event_id("123")
             .build())

    requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": [event]}
    )

    # Mock registrants
    requests_mock.get(
        f'{N_baseURL}/events/123/eventRegistrations',
        json={
            "eventRegistrations": [{
                "registrantAccountId": 456,
                "tickets": [{
                    "attendees": [{
                        "markedAttended": True,
                        "firstName": "Test",
                        "lastName": "User"
                    }]
                }]
            }]
        }
    )

    # Mock account info - already has Woodshop Safety field (id 84)
    requests_mock.get(
        f'{N_baseURL}/accounts/456',
        json={
            "individualAccount": {
                "accountCustomFields": [
                    {"id": "84", "name": "Woodshop Safety", "value": "01/01/2025"}
                ]
            }
        }
    )

    # Mock PATCH but it should NOT be called
    patch_mock = requests_mock.patch(
        f'{N_baseURL}/accounts/456',
        status_code=200
    )

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify PATCH was NOT called since account already has the field
    assert not patch_mock.called, "PATCH should not be called when field already exists"


def test_main_handles_empty_search_results(requests_mock):
    """Test that main() handles empty event search results gracefully"""
    # Mock event search - return no events
    event_search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": []}
    )

    import attendanceToTestout
    attendanceToTestout.main()

    # Verify event search was called
    assert event_search_mock.called, "Event search API should be called"
    assert event_search_mock.call_count == 1
