"""
Unit tests for dailyClassReminder.py

Tests the main() function by mocking only network interactions (HTTP requests and SMTP).
"""

import json
import pytest
from unittest.mock import mock_open

from neonUtil import N_baseURL
from neon_mocker import NeonUserMock, NeonEventMock, build_account_api_response

# Sentinel for leaving a key out of the mocked response
MISSING = object()


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

        assert self.mock_smtp.send_message.call_count == 1
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

    def test_none_teacher_sends_to_classes_email(
        self, requests_mock, mock_teachers_file
    ):
        """Test that events with None as teacher are handled properly"""
        student = NeonUserMock()
        event = NeonEventMock(event_name="Orphaned Class", teacher=None).add_registrant(student)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        # Should still send email
        assert self.mock_smtp.send_message.call_count == 1

        # Email should go to classes@asmbly.org
        email_message = self.mock_smtp.send_message.call_args[0][0]
        assert email_message["To"] == "classes@asmbly.org"

    def test_registrant_without_phone_shows_na(
        self, requests_mock, mock_teachers_file
    ):
        """Test that a registrant with no phone number is listed with N/A"""
        student = NeonUserMock(phone=None)
        event = NeonEventMock().add_registrant(student)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        assert self.mock_smtp.send_message.call_count == 1
        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{student.firstName} {student.lastName}" in email_body
        assert f"{student.email}, N/A" in email_body

    def test_canceled_registrant_without_phone_does_not_block_email(
        self, requests_mock, mock_teachers_file
    ):
        """Test that a canceled registrant with no phone doesn't block the teacher's email"""
        good_student = NeonUserMock(1, "Good", "Student")
        canceled_student = NeonUserMock(2, "Canceled", "Student", phone=None)

        event1 = NeonEventMock(1, event_name="Woodworking 101")\
            .add_registrant(good_student)\
            .add_registrant(canceled_student, status="CANCELED")
        event2 = NeonEventMock(2, event_name="Advanced Woodworking")

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event1, event2])

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        assert self.mock_smtp.send_message.call_count == 1
        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert email_message["To"] == "john@example.com"
        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body
        assert f"{good_student.firstName} {good_student.lastName}" in email_body
        assert f"{canceled_student.firstName} {canceled_student.lastName}" not in email_body

    @pytest.mark.parametrize("addresses, expected_phone", [
        pytest.param(MISSING, "N/A", id="no-addresses-key"),
        pytest.param(None, "N/A", id="addresses-null"),
        pytest.param([{"addressLine1": "1 Main St"}], "N/A", id="address-without-phone1"),
        pytest.param([{"phone1": None}], "N/A", id="phone1-null"),
        pytest.param([{"phone1": None}, {"phone1": "555-0100"}], "555-0100", id="phone-on-second-address"),
    ])
    def test_phone_lookup_handles_address_shapes(
        self, requests_mock, mock_teachers_file, addresses, expected_phone
    ):
        """Test that the first phone in the account's addresses is used, or N/A if none"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)

        search_mock, _ = NeonEventMock.mock_events(requests_mock, [event])

        # Override the account response with the address shape under test
        account = build_account_api_response(
            student.account_id, student.firstName, student.lastName, student.email
        )
        primary_contact = account["individualAccount"]["primaryContact"]
        if addresses is MISSING:
            del primary_contact["addresses"]
        else:
            primary_contact["addresses"] = addresses
        requests_mock.get(f'{N_baseURL}/accounts/{student.account_id}', json=account)

        import dailyClassReminder
        dailyClassReminder.main()

        # Verify event search API was called
        assert search_mock.called

        assert self.mock_smtp.send_message.call_count == 1
        email_message = self.mock_smtp.send_message.call_args[0][0]
        email_body = email_message.as_string()

        assert f"{student.email}, {expected_phone}" in email_body
