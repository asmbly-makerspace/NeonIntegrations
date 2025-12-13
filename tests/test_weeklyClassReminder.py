import pytest
from unittest.mock import patch, MagicMock, call, mock_open
from typing import Dict, List, Any
import datetime
import sys
import os

##### Needed for importing script files (as opposed to classes)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

from mock_events import MockEventBuilder
import mock_config_call # Mock out the config module for the gmail helper


class TestWeeklyClassReminder:
    """
    Tests for weeklyClassReminder.py
    Note: This script executes at module level, so we need to reload it for each test
    """
    
    def _reload_weekly_reminder(self):
        """Helper to reload the weeklyClassReminder module for testing"""
        if 'weeklyClassReminder' in sys.modules:
            del sys.modules['weeklyClassReminder']
        import weeklyClassReminder
        return weeklyClassReminder
    
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
    
    def _setup_mock_registrations(self, mock_get_registrants, mock_get_count, mock_get_account):
        """Setup mock registration data"""
        mock_get_registrants.return_value = {
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
        
        mock_get_count.return_value = 1
        
        mock_get_account.return_value = {
            "individualAccount": {
                "primaryContact": {
                    "email1": "student@example.com",
                    "addresses": [{"phone1": "555-1234"}]
                }
            }
        }
    
    @patch('datetime.date')
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com", "Jane Smith": "jane@example.com", "Bob Teacher": "bob@example.com"}'))
    @patch('builtins.print')  # Suppress print output
    def test_teacher_deduplication_with_multiple_events(
        self, mock_print, mock_open_file, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search, mock_date
    ):
        """Test that teacher deduplication works correctly when a teacher has multiple events"""
        # Create events: John Doe teaching 3 different classes
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101", "Advanced Woodworking", "Furniture Making"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Verify sendMIMEmessage was called exactly once for John Doe
        assert mock_send.call_count == 1
        
        # Verify the email contains all three events
        email_call = mock_send.call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        
        assert "Woodworking 101" in email_body
        assert "Advanced Woodworking" in email_body
        assert "Furniture Making" in email_body
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com", "Jane Smith": "jane@example.com", "Bob Teacher": "bob@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_multiple_teachers_get_separate_emails(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test that different teachers get separate emails"""
        events = self._create_mock_events({
            "John Doe": ["Woodworking 101"],
            "Jane Smith": ["Metalworking 101"],
            "Bob Teacher": ["Welding Basics"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Should send three emails, one for each teacher
        assert mock_send.call_count == 3
        
        # Verify correct recipients
        email_calls = mock_send.call_args_list
        recipients = [call[0][0]['to'] for call in email_calls]
        
        assert "john@example.com" in recipients
        assert "jane@example.com" in recipients
        assert "bob@example.com" in recipients
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_duplicate_events_only_send_one_email(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test that duplicate events for same teacher only trigger one email"""
        # Create duplicate events (same teacher, same event)
        events = [
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class A").with_event_id("1").build(),  # Exact duplicate
            MockEventBuilder().with_teacher("John Doe").with_event_name("Class B").with_event_id("2").build(),
        ]
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Should still only send one email despite duplicate events
        assert mock_send.call_count == 1
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_empty_events_no_emails(
        self, mock_pprint, mock_print, mock_send, mock_post_search
    ):
        """Test that no emails are sent when there are no events"""
        mock_post_search.return_value = {"searchResults": []}
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # No emails should be sent
        assert mock_send.call_count == 0
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_none_teacher_sends_to_fallback_email(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test that events with no teacher assigned send to board@asmbly.org"""
        events = [
            MockEventBuilder()
                .with_teacher(None)
                .with_event_name("Unassigned Class")
                .with_event_id("1")
                .build()
        ]
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Should send one email
        assert mock_send.call_count == 1
        
        # Verify it goes to board@asmbly.org (weekly script uses different fallback)
        email_call = mock_send.call_args[0][0]
        assert email_call['to'] == "board@asmbly.org"
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_no_registrants_shows_appropriate_message(
        self, mock_pprint, mock_print, mock_send, mock_get_count, 
        mock_get_registrants, mock_post_search
    ):
        """Test that events with no registrants show appropriate message"""
        events = self._create_mock_events({
            "John Doe": ["Empty Class"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        
        # Mock no registrations
        mock_get_registrants.return_value = {"eventRegistrations": []}
        mock_get_count.return_value = 0
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Verify email was sent
        assert mock_send.call_count == 1
        
        # Verify message about no attendees
        email_call = mock_send.call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "No attendees registered currently" in email_body
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_mixed_registration_statuses(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test handling of different registration statuses"""
        events = self._create_mock_events({
            "John Doe": ["Mixed Status Class"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        
        # Mock registrations with different statuses
        mock_get_registrants.return_value = {
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
                            "firstName": "Canceled",
                            "lastName": "Student",
                            "registrationStatus": "CANCELED"
                        }]
                    }]
                }
            ]
        }
        
        mock_get_count.return_value = 2
        
        mock_get_account.return_value = {
            "individualAccount": {
                "primaryContact": {
                    "email1": "student@example.com",
                    "addresses": [{"phone1": "555-1234"}]
                }
            }
        }
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Verify email was sent
        assert mock_send.call_count == 1
        
        # Verify only SUCCEEDED registrants appear in email
        email_call = mock_send.call_args[0][0]
        email_body = str(email_call.get_payload()[0])
        assert "Success Student" in email_body
        # CANCELED registrants should appear (they're in registrantDict for weekly)
        assert "Canceled Student" in email_body
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_subject_line_contains_date_range(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test that the email subject line includes 'week of' and the date"""
        events = self._create_mock_events({
            "John Doe": ["Test Class"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Verify email was sent
        assert mock_send.call_count == 1
        
        # Verify subject line format
        email_call = mock_send.call_args[0][0]
        subject = email_call['subject']
        assert "week of" in subject
        assert "Your upcoming classes at Asmbly" in subject
    
    @patch('helpers.neon.postEventSearch')
    @patch('helpers.neon.getEventRegistrants')
    @patch('helpers.neon.getEventRegistrantCount')
    @patch('helpers.neon.getAccountIndividual')
    @patch('helpers.gmail.sendMIMEmessage')
    @patch('builtins.open', mock_open(read_data='{"John Doe": "john@example.com"}'))
    @patch('builtins.print')
    @patch('weeklyClassReminder.pprint')
    def test_cc_to_classes_email(
        self, mock_pprint, mock_print, mock_send, mock_get_account, 
        mock_get_count, mock_get_registrants, mock_post_search
    ):
        """Test that classes@asmbly.org is CC'd on all emails"""
        events = self._create_mock_events({
            "John Doe": ["Test Class"]
        })
        
        mock_post_search.return_value = {"searchResults": events}
        self._setup_mock_registrations(mock_get_registrants, mock_get_count, mock_get_account)
        
        # Reload and execute the weekly reminder script
        self._reload_weekly_reminder()
        
        # Verify email was sent with CC
        assert mock_send.call_count == 1
        email_call = mock_send.call_args[0][0]
        assert email_call['cc'] == "classes@asmbly.org"
