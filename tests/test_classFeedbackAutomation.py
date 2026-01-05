"""
Unit tests for classFeedbackAutomation.py

Tests the main() function by mocking only network interactions.
"""

import pytest
import json
from unittest.mock import mock_open

from neon_mocker import NeonUserMock, NeonEventMock


class TestClassFeedbackAutomation:
    """Test suite for classFeedbackAutomation.main()"""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_smtp, mock_google_apis):
        """Setup SMTP and Google API mocks for all tests in this class."""
        self.mock_smtp = mock_smtp
        self.mock_google_apis = mock_google_apis

    def test_main_runs_with_no_events(self, requests_mock):
        """Test that main() runs successfully when there are no events to process"""
        search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

        import classFeedbackAutomation
        classFeedbackAutomation.main()

        # Verify event search API was called
        assert search_mock.called, "Neon event search API should be called"

        # Verify no emails were sent (no events)
        self.mock_smtp.send_message.assert_not_called()

        # Verify Google Drive was not called (no surveys needed)
        self.mock_google_apis['drive'].files.assert_not_called()

    def test_main_handles_existing_survey_link(self, requests_mock, mocker):
        """Test that main() reuses existing survey links from cache"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)
        search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(
            requests_mock, [event]
        )

        # Override builtins.open to return existing survey links
        existing_links = {
            event.teacher: {
                event.event_name: "https://forms.google.com/existing_survey"
            }
        }
        mocker.patch('builtins.open', mock_open(read_data=json.dumps(existing_links)))

        import classFeedbackAutomation
        classFeedbackAutomation.main()

        # Verify Neon APIs were called
        assert search_mock.called, "Neon event search should be called"
        assert registrants_mock.called, "Neon registrants API should be called"
        assert account_mocks[0].called, "Neon account API should be called"

        # Verify Drive API was NOT called (should use cached link)
        self.mock_google_apis['drive'].files.assert_not_called()

        # Verify email was sent (sendmail is used, not send_message)
        assert self.mock_smtp.sendmail.called, "Email should be sent to attendee"
