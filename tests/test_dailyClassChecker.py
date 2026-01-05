"""
Unit tests for dailyClassChecker.py

Tests the main() function by mocking only network interactions (HTTP requests and SMTP).
"""

import pytest
from neon_mocker import NeonMock, NeonEventMock, today_plus


class TestDailyClassChecker:
    """Test suite for dailyClassChecker.main()"""

    @pytest.fixture(autouse=True)
    def setup_smtp(self, mock_smtp):
        """Setup SMTP mock for all tests in this class."""
        self.mock_smtp = mock_smtp

    def test_main_sends_email_with_class_info(self, requests_mock):
        """Test that main() fetches class data and sends an email summary"""
        # Mock event search - return no events (simplest case)
        event_search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

        import dailyClassChecker
        dailyClassChecker.main()

        # Verify event search API was called
        assert event_search_mock.called, "Event search API should be called"

        # Verify SMTP was used to send an email
        self.mock_smtp.send_message.assert_called_once()

        # Verify email was sent to the correct recipient
        email_message = self.mock_smtp.send_message.call_args[0][0]
        assert email_message["to"] == "classes@asmbly.org"
        assert "Currently Scheduled Classes" in email_message["subject"]

    def test_main_processes_scheduled_classes(self, requests_mock):
        """Test that main() processes scheduled classes and includes them in email"""
        future_date = today_plus(7)

        student = NeonMock(456, "Test", "User")
        event = NeonEventMock(
            event_id="123",
            event_name="Orientation with John",
            teacher="John Doe",
            date=future_date
        ).add_registrant(student)

        event_search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassChecker
        dailyClassChecker.main()

        # Verify API calls were made
        assert event_search_mock.called, "Event search API should be called"

        # Verify email was sent
        self.mock_smtp.send_message.assert_called_once()

        # Get the email that was sent
        email_message = self.mock_smtp.send_message.call_args[0][0]

        # Verify the email contains expected content
        email_body = email_message.as_string()
        assert "Orientation" in email_body, "Email should contain class name"
        assert email_message["to"] == "classes@asmbly.org", "Email should be sent to classes@asmbly.org"

    def test_main_handles_empty_results(self, requests_mock):
        """Test that main() handles empty search results gracefully"""
        # Mock event search - return no events
        event_search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

        import dailyClassChecker
        dailyClassChecker.main()

        # Verify API was called
        assert event_search_mock.called, "Event search API should be called"

        # Should still send an email (with empty class tables)
        self.mock_smtp.send_message.assert_called_once()

        # Verify email structure
        email_message = self.mock_smtp.send_message.call_args[0][0]
        assert email_message["to"] == "classes@asmbly.org"
