"""
Unit tests for dailyClassReminder.py

Tests the main() function by mocking only network interactions (HTTP requests and SMTP).
"""

import json
import pytest
from unittest.mock import mock_open

from neon_mocker import NeonUserMock, NeonEventMock


class TestDailyClassReminders:
    """Test suite for dailyClassReminder.main()"""

    @pytest.fixture(autouse=True)
    def setup_smtp(self, mock_smtp):
        """Setup SMTP mock for all tests in this class."""
        self.mock_smtp = mock_smtp

    @pytest.fixture
    def mock_teachers_file(self, mocker):
        """Mock the teachers.json file."""
        mocker.patch('builtins.open', mock_open(read_data=json.dumps({
            "John Doe": "john@example.com",
            "Jane Smith": "jane@example.com"
        })))

    def test_no_duplicate_emails_single_teacher_multiple_events(
        self, requests_mock, mock_teachers_file
    ):
        """Test that a teacher with multiple events only gets one email"""
        student = NeonUserMock()

        event1 = NeonEventMock(1, event_name="Woodworking 101").add_registrant(student)
        event2 = NeonEventMock(2, event_name="Advanced Woodworking").add_registrant(student)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event1, event2])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # Verify sendMIMEmessage was called exactly once for John Doe
        assert self.mock_smtp.send_message.call_count == 1

        # Verify the email contains both events
        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body

    def test_multiple_teachers_get_separate_emails(
        self, requests_mock, mock_teachers_file
    ):
        """Test that different teachers get separate emails"""
        student1 = NeonUserMock(1)
        student2 = NeonUserMock(2)

        event1 = NeonEventMock(1, event_name="Woodworking 101").add_registrant(student1)
        event2 = NeonEventMock(2, event_name="Metalworking 101", teacher="Jane Smith")\
            .add_registrant(student2)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event1, event2])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # Should send two emails, one for each teacher
        assert self.mock_smtp.send_message.call_count == 2

        # Verify correct recipients
        email_calls = self.mock_smtp.send_message.call_args_list
        recipients = [call[0][0]["To"] for call in email_calls]

        assert "john@example.com" in recipients
        assert "jane@example.com" in recipients

    def test_event_with_no_registrants(
        self, requests_mock, mock_teachers_file
    ):
        """Test that events with no registrants still send reminder emails"""
        event = NeonEventMock(event_name="Empty Class")

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # Should still send email to teacher
        assert self.mock_smtp.send_message.call_count == 1

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert "No attendees registered" in email_body

    def test_unknown_teacher_sends_to_classes_email(
        self, requests_mock, mock_teachers_file
    ):
        """Test that unknown teachers have emails sent to classes@asmbly.org"""
        event = NeonEventMock(event_name="Mystery Class", teacher="Unknown Teacher")

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # Should still send email
        assert self.mock_smtp.send_message.call_count == 1

        email_message = self.mock_smtp.send_message.call_args[0][0]
        assert email_message["To"] == "classes@asmbly.org"
        assert "Failed Class Reminder" in email_message["Subject"]

    def test_no_events_sends_no_emails(
        self, requests_mock, mock_teachers_file
    ):
        """Test that no events means no emails are sent"""
        search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # No emails should be sent
        self.mock_smtp.send_message.assert_not_called()

    def test_email_includes_registrant_details(
        self, requests_mock, mock_teachers_file
    ):
        """Test that email includes registrant name, email and phone"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{student.firstName} {student.lastName}" in email_body
        assert student.email in email_body
        assert student.phone in email_body

    def test_canceled_registrants_not_included(
        self, requests_mock, mock_teachers_file
    ):
        """Test that canceled registrants are not included in the email"""
        good_student = NeonUserMock(1, "Good", "Student")
        canceled_student = NeonUserMock(2, "Canceled", "Student")

        event = NeonEventMock()\
            .add_registrant(good_student)\
            .add_registrant(canceled_student, status="CANCELED")

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{good_student.firstName} {good_student.lastName}" in email_body
        assert f"{canceled_student.firstName} {canceled_student.lastName}" not in email_body
