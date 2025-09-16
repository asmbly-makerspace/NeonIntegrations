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
