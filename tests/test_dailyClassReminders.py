import pytest
from unittest.mock import patch, MagicMock, call
from typing import Dict, List, Any
import datetime

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

from mock_events import MockEventBuilder

import mock_config_call # Mock out the config module for the gmail helper
import dailyClassReminder 


class TestClassReminders:
    
    @pytest.fixture
    def setup_mocks(self, mocker):
        """Setup all the mocks needed for testing"""
        return {
            'postEventSearch': mocker.patch('helpers.neon.postEventSearch'),
            'getEventRegistrants': mocker.patch('helpers.neon.getEventRegistrants'),
            'getEventRegistrantCount': mocker.patch('helpers.neon.getEventRegistrantCount'),
            'getAccountIndividual': mocker.patch('helpers.neon.getAccountIndividual'),
            # I think this is because we call the method directly in dailyClassReminder.
            # That is, we call `sendMIMEmessage` rather than `gmail.sendMIMEmessage`.
            'sendMIMEmessage': mocker.patch('dailyClassReminder.sendMIMEmessage'),
            'open': mocker.patch('builtins.open', mocker.mock_open(
                read_data='{"John Doe": "john@example.com", "Jane Smith": "jane@example.com"}'
            ))
        }
    
    def _create_mock_events(self, teacher_events: Dict[str, List[str]]) -> List[Dict]:
        """
        Create mock events for testing
        teacher_events: Dict mapping teacher names to list of event names
        """
        events = []
        event_id = 1
        
        for teacher, event_names in teacher_events.items():
            for event_name in event_names:
                event = (MockEventBuilder()
                        .with_teacher(teacher)
                        .with_event_name(event_name)
                        .with_event_id(str(event_id))
                        .build())
                events.append(event)
                event_id += 1
        
        return events
    
    def _setup_mock_registrations(self, mocks):
        """Setup mock registration data"""
        mocks['getEventRegistrants'].return_value = {
            "eventRegistrations": [
                {
                    "registrantAccountId": "123",
                    "tickets": [{
                        "attendees": [{
                            "firstName": "Test",
                            "lastName": "Student",
                            "registrationStatus": "SUCCEEDED"
                        }]
                    }]
                }
            ]
        }
        
        mocks['getEventRegistrantCount'].return_value = 1
        
        mocks['getAccountIndividual'].return_value = {
            "individualAccount": {
                "primaryContact": {
                    "email1": "student@example.com",
                    "addresses": [{"phone1": "555-1234"}]
                }
            }
        }
    
    def test_no_duplicate_emails_single_teacher_multiple_events(self, setup_mocks):
        """Test that a teacher with multiple events only gets one email"""
        mocks = setup_mocks
        
        # Create events: John Doe teaching 2 different classes
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101", "Advanced Woodworking"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Run the main function
        dailyClassReminder.main()
        
        # Verify sendMIMEmessage was called exactly once for John Doe
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify the email contains both events
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        
        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body
    
    def test_duplicate_teacher_names_cause_single_email(self, setup_mocks):
        """Test that duplicate teacher names in search results don't cause duplicate emails"""
        mocks = setup_mocks
        
        # Create duplicate events with same teacher name (simulating the bug condition)
        events = [
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),  # Exact duplicate
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class B").with_event_id("2").build(),
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Run the main function
        dailyClassReminder.main()
        
        # Should still only send one email despite duplicate events
        assert mocks['sendMIMEmessage'].call_count == 1
    
    def test_multiple_teachers_get_separate_emails(self, setup_mocks):
        """Test that different teachers get separate emails"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101"],
            "Jane Smith": ["Metalworking 101"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Run the main function
        dailyClassReminder.main()
        
        # Should send two emails, one for each teacher
        assert mocks['sendMIMEmessage'].call_count == 2
        
        # Verify correct recipients
        email_calls = mocks['sendMIMEmessage'].call_args_list
        recipients = [call[0][0]['To'] for call in email_calls]
        
        assert "john@example.com" in recipients
        assert "jane@example.com" in recipients
   
    @patch('dailyClassReminder.logging')
    def test_logging_shows_duplicate_detection(self, mock_logging, setup_mocks):
        """Test that logging helps identify duplicate issues"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Class A", "Class B"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Run the main function
        dailyClassReminder.main()
        
        # Check that logging was called with information about multiple events
        log_calls = mock_logging.info.call_args_list
        
        # Should log that John Doe has 2 events
        event_count_logged = any([
            'John Doe' in args and 2 in args
            for args, _ in log_calls
        ])

        assert event_count_logged, "Should log the number of events per teacher"

    def test_multiple_teachers_with_same_class(self, setup_mocks):
        """Test that multiple teachers teaching the same class get separate emails"""
        mocks = setup_mocks
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101"],
            "Jane Smith": ["Woodworking 101"],
        })
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)

        dailyClassReminder.main()

        # Should send one email per teacher
        assert mocks['sendMIMEmessage'].call_count == 2

        # Verify correct recipients
        email_calls = mocks['sendMIMEmessage'].call_args_list
        recipients = [call[0][0]['To'] for call in email_calls]

        assert "john@example.com" in recipients
        assert "jane@example.com" in recipients

    def test_date_boundary_today_class(self, setup_mocks):
        """Test that classes happening TODAY are included and labeled correctly"""
        mocks = setup_mocks
        today = datetime.date.today()
        
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Today's Class")
                .with_event_id("1")
                .with_date(today.isoformat())
                .build()
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        dailyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify "TODAY" appears in the email body
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "TODAY" in email_body

    def test_date_boundary_tomorrow_class(self, setup_mocks):
        """Test that classes happening TOMORROW are included and labeled correctly"""
        mocks = setup_mocks
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Tomorrow's Class")
                .with_event_id("1")
                .with_date(tomorrow.isoformat())
                .build()
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        dailyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify "Tomorrow" appears in the email body
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "Tomorrow" in email_body

    def test_date_boundary_two_days_out(self, setup_mocks):
        """Test that classes 2 days out are included (at the boundary)"""
        mocks = setup_mocks
        two_days = datetime.date.today() + datetime.timedelta(days=2)
        
        events = [
            MockEventBuilder()
                .with_teacher("John Doe")
                .with_event_name("Two Days Out")
                .with_event_id("1")
                .with_date(two_days.isoformat())
                .build()
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        dailyClassReminder.main()
        
        # Verify email was sent (should be included)
        assert mocks['sendMIMEmessage'].call_count == 1

    def test_empty_events_no_emails(self, setup_mocks):
        """Test that no emails are sent when there are no events"""
        mocks = setup_mocks
        
        mocks['postEventSearch'].return_value = {"searchResults": []}
        
        dailyClassReminder.main()
        
        # No emails should be sent
        assert mocks['sendMIMEmessage'].call_count == 0

    def test_none_teacher_sends_to_fallback_email(self, setup_mocks):
        """Test that events with no teacher assigned send to classes@asmbly.org"""
        mocks = setup_mocks
        
        events = [
            MockEventBuilder()
                .with_teacher(None)
                .with_event_name("Unassigned Class")
                .with_event_id("1")
                .build()
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        dailyClassReminder.main()
        
        # Should send one email
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify it goes to classes@asmbly.org
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        assert email_call['To'] == "classes@asmbly.org"

    def test_unknown_teacher_sends_to_fallback_email(self, setup_mocks):
        """Test that teachers not in teachers.json send to classes@asmbly.org"""
        mocks = setup_mocks
        
        events = [
            MockEventBuilder()
                .with_teacher("Unknown Teacher")
                .with_event_name("Mystery Class")
                .with_event_id("1")
                .build()
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        dailyClassReminder.main()
        
        # Should send one email
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify it goes to classes@asmbly.org (KeyError handling)
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        assert email_call['To'] == "classes@asmbly.org"

    def test_no_registrants_shows_appropriate_message(self, setup_mocks):
        """Test that events with no registrants show appropriate message"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Empty Class"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        
        # Mock no registrations
        mocks['getEventRegistrants'].return_value = {"eventRegistrations": []}
        mocks['getEventRegistrantCount'].return_value = 0
        
        dailyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify message about no attendees
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "No attendees registered currently" in email_body

    def test_mixed_registration_statuses(self, setup_mocks):
        """Test handling of different registration statuses (SUCCEEDED, FAILED, etc.)"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Mixed Status Class"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        
        # Mock registrations with different statuses
        mocks['getEventRegistrants'].return_value = {
            "eventRegistrations": [
                {
                    "registrantAccountId": "123",
                    "tickets": [{
                        "attendees": [{
                            "firstName": "Success",
                            "lastName": "Student",
                            "registrationStatus": "SUCCEEDED"
                        }]
                    }]
                },
                {
                    "registrantAccountId": "456",
                    "tickets": [{
                        "attendees": [{
                            "firstName": "Failed",
                            "lastName": "Student",
                            "registrationStatus": "FAILED"
                        }]
                    }]
                }
            ]
        }
        
        mocks['getEventRegistrantCount'].return_value = 2
        
        mocks['getAccountIndividual'].return_value = {
            "individualAccount": {
                "primaryContact": {
                    "email1": "student@example.com",
                    "addresses": [{"phone1": "555-1234"}]
                }
            }
        }
        
        dailyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify only SUCCEEDED registrants appear in email
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "Success Student" in email_body
        # FAILED registrants should not appear
        assert "Failed Student" not in email_body

    def test_error_handling_continues_to_next_teacher(self, setup_mocks):
        """Test that errors in processing one teacher don't prevent processing others"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Class 1"],
            "Jane Smith": ["Class 2"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        
        # Make getEventRegistrants fail for first call, succeed for second
        mocks['getEventRegistrants'].side_effect = [
            Exception("API Error"),
            {"eventRegistrations": []}
        ]
        mocks['getEventRegistrantCount'].return_value = 0
        
        dailyClassReminder.main()
        
        # Should still send one email (for Jane Smith)
        assert mocks['sendMIMEmessage'].call_count == 1

    def test_multiple_attendees_per_registration(self, setup_mocks):
        """Test that registrations with multiple attendees are handled correctly"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Family Class"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        
        # Mock registration with multiple attendees
        mocks['getEventRegistrants'].return_value = {
            "eventRegistrations": [
                {
                    "registrantAccountId": "123",
                    "tickets": [{
                        "attendees": [
                            {
                                "firstName": "Parent",
                                "lastName": "Smith",
                                "registrationStatus": "SUCCEEDED"
                            },
                            {
                                "firstName": "Child",
                                "lastName": "Smith",
                                "registrationStatus": "SUCCEEDED"
                            }
                        ]
                    }]
                }
            ]
        }
        
        mocks['getEventRegistrantCount'].return_value = 2
        
        mocks['getAccountIndividual'].return_value = {
            "individualAccount": {
                "primaryContact": {
                    "email1": "parent@example.com",
                    "addresses": [{"phone1": "555-1234"}]
                }
            }
        }
        
        dailyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify both attendees appear in email
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "Parent Smith" in email_body
        assert "Child Smith" in email_body

    def test_neon_api_returns_duplicate_event_ids(self, setup_mocks):
        """Test that duplicate event IDs from Neon API are handled correctly
        
        This test verifies:
        1. Mock Neon API returns duplicate event records (same event ID)
        2. Both duplicate events are processed and shown in the email (this is acceptable)
        3. Only ONE email is sent to the teacher (no duplicate emails)
        """
        mocks = setup_mocks
        
        # Simulate Neon API returning duplicate event records with same event ID
        # This tests the hypothesis that the API might return duplicates
        events = [
            MockEventBuilder().with_teacher("John Doe").with_event_name("Woodworking 101").with_event_id("12345").build(),
            MockEventBuilder().with_teacher("John Doe").with_event_name("Woodworking 101").with_event_id("12345").build(),  # Duplicate event ID
            MockEventBuilder().with_teacher("John Doe").with_event_name("Advanced Woodworking").with_event_id("12346").build(),
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Run the main function
        dailyClassReminder.main()
        
        # CRITICAL: Should still only send ONE email to John Doe (deduplication by teacher works)
        # This confirms that duplicate events from API don't cause duplicate EMAILS
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify email contains the class names
        # Note: Due to duplicate event processing, "Woodworking 101" may appear twice in the email body
        # This is acceptable - showing both events is fine, as long as we don't send duplicate emails
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body
        
        # Both events are processed (getEventRegistrants called for each event in the list)
        # This is inefficient but doesn't cause duplicate emails
        assert mocks['getEventRegistrants'].call_count == 3  # Called once for each event in the list
        
        # Test conclusion: Teacher deduplication prevents duplicate EMAILS 
        # even when API returns duplicate event records
