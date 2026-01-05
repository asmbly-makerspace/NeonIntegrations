"""
Unit tests for dailyClassReminder.py

Tests the main() function by mocking only network interactions (HTTP requests and SMTP).
"""

import json
import pytest
from unittest.mock import mock_open

from neonUtil import N_baseURL
from mock_events import MockEventBuilder
from neon_mocker import NeonMock


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

    def _mock_registrant_response(self, requests_mock, event_id, registrants):
        """Helper to mock event registrant API response."""
        requests_mock.get(
            f'{N_baseURL}/events/{event_id}/eventRegistrations',
            json={"eventRegistrations": registrants}
        )

    def _create_registrant(self, account: NeonMock, status="SUCCEEDED"):
        """Helper to create a registrant data structure from a NeonMock."""
        return {
            "registrantAccountId": account.account_id,
            "tickets": [{
                "attendees": [{
                    "firstName": account.firstName,
                    "lastName": account.lastName,
                    "registrationStatus": status
                }]
            }]
        }

    def test_no_duplicate_emails_single_teacher_multiple_events(
        self, requests_mock, mock_teachers_file
    ):
        """Test that a teacher with multiple events only gets one email"""
        # Create events: John Doe teaching 2 different classes
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Woodworking 101")
                .with_event_id("1")
                .build(),
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Advanced Woodworking")
                .with_event_id("2")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        student = NeonMock(123, "Test", "Student", phone="555-1234")
        registrant = self._create_registrant(student)
        self._mock_registrant_response(requests_mock, "1", [registrant])
        self._mock_registrant_response(requests_mock, "2", [registrant])
        student.mock(requests_mock)

        import dailyClassReminder
        dailyClassReminder.main()

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
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Woodworking 101")
                .with_event_id("1")
                .build(),
            MockEventBuilder()
                .with_teacher("Jane Smith")
                .with_event_name("Metalworking 101")
                .with_event_id("2")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        student1 = NeonMock(123, "Test", "Student1", phone="555-1234")
        student2 = NeonMock(456, "Test", "Student2", phone="555-5678")
        self._mock_registrant_response(requests_mock, "1", [self._create_registrant(student1)])
        self._mock_registrant_response(requests_mock, "2", [self._create_registrant(student2)])
        student1.mock(requests_mock)
        student2.mock(requests_mock)

        import dailyClassReminder
        dailyClassReminder.main()

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
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Empty Class")
                .with_event_id("1")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        # No registrants for this event
        self._mock_registrant_response(requests_mock, "1", [])

        import dailyClassReminder
        dailyClassReminder.main()

        # Should still send email to teacher
        assert self.mock_smtp.send_message.call_count == 1

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert "No attendees registered" in email_body

    def test_unknown_teacher_sends_to_classes_email(
        self, requests_mock, mock_teachers_file
    ):
        """Test that unknown teachers have emails sent to classes@asmbly.org"""
        events = [
            MockEventBuilder()
                .with_teacher("Unknown Teacher")
                .with_event_name("Mystery Class")
                .with_event_id("1")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        self._mock_registrant_response(requests_mock, "1", [])

        import dailyClassReminder
        dailyClassReminder.main()

        # Should still send email
        assert self.mock_smtp.send_message.call_count == 1

        email_message = self.mock_smtp.send_message.call_args[0][0]
        assert email_message["To"] == "classes@asmbly.org"
        assert "Failed Class Reminder" in email_message["Subject"]

    def test_no_events_sends_no_emails(
        self, requests_mock, mock_teachers_file
    ):
        """Test that no events means no emails are sent"""
        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": []}
        )

        import dailyClassReminder
        dailyClassReminder.main()

        # No emails should be sent
        self.mock_smtp.send_message.assert_not_called()

    def test_email_includes_registrant_details(
        self, requests_mock, mock_teachers_file
    ):
        """Test that email includes registrant name, email and phone"""
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Test Class")
                .with_event_id("1")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        student = NeonMock(123, "Alice", "Wonderland", phone="555-ALICE")
        self._mock_registrant_response(requests_mock, "1", [self._create_registrant(student)])
        student.mock(requests_mock)

        import dailyClassReminder
        dailyClassReminder.main()

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{student.firstName} {student.lastName}" in email_body
        assert student.email in email_body
        assert student.phone in email_body

    def test_canceled_registrants_not_included(
        self, requests_mock, mock_teachers_file
    ):
        """Test that canceled registrants are not included in the email"""
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Test Class")
                .with_event_id("1")
                .build()
        ]

        requests_mock.post(
            f'{N_baseURL}/events/search',
            json={"searchResults": events}
        )

        good_student = NeonMock(123, "Good", "Student", phone="555-1234")
        canceled_student = NeonMock(456, "Canceled", "Student", phone="555-5678")
        self._mock_registrant_response(requests_mock, "1", [
            self._create_registrant(good_student),
            self._create_registrant(canceled_student, status="CANCELED")
        ])
        good_student.mock(requests_mock)
        canceled_student.mock(requests_mock)

        import dailyClassReminder
        dailyClassReminder.main()

        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{good_student.firstName} {good_student.lastName}" in email_body
        assert f"{canceled_student.firstName} {canceled_student.lastName}" not in email_body
