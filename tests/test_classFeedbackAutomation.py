"""
Unit tests for classFeedbackAutomation.py

Tests the main() function by mocking only network interactions.
"""

import pytest
import json
from unittest.mock import mock_open

from neonUtil import N_baseURL


class TestClassFeedbackAutomation:
    """Test suite for classFeedbackAutomation.main()"""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_smtp, mock_google_apis):
        """Setup SMTP and Google API mocks for all tests in this class."""
        self.mock_smtp = mock_smtp
        self.mock_google_apis = mock_google_apis

    def test_main_runs_with_no_events(self, requests_mock):
        """Test that main() runs successfully when there are no events to process"""
        # Mock Neon event search - return no events
        event_search_mock = requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": []}
        )

        import classFeedbackAutomation
        classFeedbackAutomation.main()

        # Verify event search API was called
        assert event_search_mock.called, "Neon event search API should be called"

        # Verify no emails were sent (no events)
        self.mock_smtp.send_message.assert_not_called()

        # Verify Google Drive was not called (no surveys needed)
        self.mock_google_apis['drive'].files.assert_not_called()

    def test_main_handles_existing_survey_link(self, requests_mock, mocker):
        """Test that main() reuses existing survey links from cache"""
        # Override builtins.open to return existing survey links
        existing_links = {
            "John Doe": {
                "Woodshop Safety with John": "https://forms.google.com/existing_survey"
            }
        }
        mocker.patch('builtins.open', mock_open(read_data=json.dumps(existing_links)))

        # Mock Neon event search
        event_search_mock = requests_mock.post(
            f'{N_baseURL}/events/search',
            json={
                "searchResults": [{
                    "Event ID": "123",
                    "Event Name": "Woodshop Safety with John",
                    "Event Topic": "John Doe",
                }]
            }
        )

        # Mock Neon registrants
        registrants_mock = requests_mock.get(
            f'{N_baseURL}/events/123/eventRegistrations',
            json={
                "eventRegistrations": [{
                    "registrantAccountId": 456,
                    "tickets": [{
                        "attendees": [{
                            "registrationStatus": "SUCCEEDED",
                            "firstName": "Test",
                            "lastName": "Student"
                        }]
                    }]
                }]
            }
        )

        # Mock Neon get account
        account_mock = requests_mock.get(
            f'{N_baseURL}/accounts/456',
            json={
                "individualAccount": {
                    "primaryContact": {
                        "email1": "student@example.com"
                    }
                }
            }
        )

        import classFeedbackAutomation
        classFeedbackAutomation.main()

        # Verify Neon APIs were called
        assert event_search_mock.called, "Neon event search should be called"
        assert registrants_mock.called, "Neon registrants API should be called"
        assert account_mock.called, "Neon account API should be called"

        # Verify Drive API was NOT called (should use cached link)
        self.mock_google_apis['drive'].files.assert_not_called()

        # Verify email was sent (sendmail is used, not send_message)
        assert self.mock_smtp.sendmail.called, "Email should be sent to attendee"
