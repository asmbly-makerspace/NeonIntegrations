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
import weeklyClassReminder


class TestWeeklyClassReminder:
    """Tests for weeklyClassReminder.py"""
    
    @pytest.fixture
    def setup_mocks(self, mocker):
        """Setup all the mocks needed for testing"""
        return {
            'postEventSearch': mocker.patch('helpers.neon.postEventSearch'),
            'getEventRegistrants': mocker.patch('helpers.neon.getEventRegistrants'),
            'getEventRegistrantCount': mocker.patch('helpers.neon.getEventRegistrantCount'),
            'getAccountIndividual': mocker.patch('helpers.neon.getAccountIndividual'),
            'sendMIMEmessage': mocker.patch('weeklyClassReminder.sendMIMEmessage'),
            'open': mocker.patch('builtins.open', mocker.mock_open(
                read_data='{"John Doe": "john@example.com", "Jane Smith": "jane@example.com", "Bob Teacher": "bob@example.com"}'
            )),
            'pprint': mocker.patch('weeklyClassReminder.pprint'),
            'print': mocker.patch('builtins.print')
        }
    
    def _create_mock_events(self, teacher_events: Dict[str, List[str]], days_offset: int = 5) -> List[Dict]:
        """
        Create mock events for testing
        teacher_events: Dict mapping teacher names to list of event names
        days_offset: Number of days from today for the event
        """
        events = []
        event_id = 1
        event_date = (datetime.date.today() + datetime.timedelta(days=days_offset)).isoformat()
        
        for teacher, event_names in teacher_events.items():
            for event_name in event_names:
                event = (MockEventBuilder()
                        .with_teacher(teacher)
                        .with_event_name(event_name)
                        .with_event_id(str(event_id))
                        .with_date(event_date)
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
    
    def test_teacher_deduplication_with_multiple_events(self, setup_mocks):
        """Test that teacher deduplication works correctly when a teacher has multiple events"""
        mocks = setup_mocks
        
        # Create events: John Doe teaching 3 different classes
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101", "Advanced Woodworking", "Furniture Making"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Verify sendMIMEmessage was called exactly once for John Doe
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify the email contains all three events
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        
        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body
        assert "Furniture Making" in email_body
    
    def test_multiple_teachers_get_separate_emails(self, setup_mocks):
        """Test that different teachers get separate emails"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101"],
            "Jane Smith": ["Metalworking 101"],
            "Bob Teacher": ["Welding Basics"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Should send three emails, one for each teacher
        assert mocks['sendMIMEmessage'].call_count == 3
        
        # Verify correct recipients
        email_calls = mocks['sendMIMEmessage'].call_args_list
        recipients = [call[0][0]['To'] for call in email_calls]
        
        assert "john@example.com" in recipients
        assert "jane@example.com" in recipients
        assert "bob@example.com" in recipients
    
    def test_duplicate_events_only_send_one_email(self, setup_mocks):
        """Test that duplicate events for same teacher only trigger one email"""
        mocks = setup_mocks
        
        # Create duplicate events (same teacher, same event)
        events = [
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),  # Exact duplicate
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class B").with_event_id("2").build(),
        ]
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Should still only send one email despite duplicate events
        assert mocks['sendMIMEmessage'].call_count == 1
    
    def test_empty_events_no_emails(self, setup_mocks):
        """Test that no emails are sent when there are no events"""
        mocks = setup_mocks
        
        mocks['postEventSearch'].return_value = {"searchResults": []}
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # No emails should be sent
        assert mocks['sendMIMEmessage'].call_count == 0
    
    def test_none_teacher_sends_to_fallback_email(self, setup_mocks):
        """Test that events with no teacher assigned send to board@asmbly.org"""
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
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Should send one email
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify it goes to board@asmbly.org (weekly script uses different fallback)
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        assert email_call['To'] == "board@asmbly.org"
    
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
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify message about no attendees
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "No attendees registered currently" in email_body
    
    def test_subject_line_contains_date_range(self, setup_mocks):
        """Test that the email subject line includes 'week of' and the date"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Test Class"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Verify email was sent
        assert mocks['sendMIMEmessage'].call_count == 1
        
        # Verify subject line format
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        subject = email_call['Subject']
        assert "week of" in subject
        assert "Your upcoming classes at Asmbly" in subject
    
    def test_cc_to_classes_email(self, setup_mocks):
        """Test that classes@asmbly.org is CC'd on all emails"""
        mocks = setup_mocks
        
        events = self._create_mock_events({
            "John Doe": ["Test Class"]
        })
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Verify email was sent with CC
        assert mocks['sendMIMEmessage'].call_count == 1
        email_call = mocks['sendMIMEmessage'].call_args[0][0]
        assert email_call['CC'] == "classes@asmbly.org"
    
    def test_teacher_deduplication_efficiency(self, setup_mocks):
        """Test that teacher deduplication uses set for efficiency"""
        mocks = setup_mocks
        
        # Create many duplicate teacher entries
        events = []
        for i in range(10):
            events.append(MockEventBuilder().with_teacher("John Doe").with_event_name(f"Class {i}").with_event_id(str(i)).build())
        
        mocks['postEventSearch'].return_value = {"searchResults": events}
        self._setup_mock_registrations(mocks)
        
        # Execute the weekly reminder script
        weeklyClassReminder.main()
        
        # Should still only send one email
        assert mocks['sendMIMEmessage'].call_count == 1
