"""
Unit tests for classFeedbackAutomation.py

Tests the main() function by mocking only network interactions.
"""

import pytest
import json
from unittest.mock import MagicMock, mock_open

from neonUtil import N_baseURL


def test_main_runs_with_no_events(requests_mock, mocker):
    """Test that main() runs successfully when there are no events to process"""
    # Mock Google credentials file read
    mocker.patch('builtins.open', mock_open(read_data='{}'))

    # Mock Google credentials
    mock_creds = MagicMock()
    mock_creds.with_subject.return_value = mock_creds
    mocker.patch(
        'google.oauth2.service_account.Credentials.from_service_account_file',
        return_value=mock_creds
    )

    # Mock Google API service builders
    mock_drive_service = MagicMock()
    mock_forms_service = MagicMock()

    def mock_build(service_name, version, credentials):
        if service_name == "drive":
            return mock_drive_service
        elif service_name == "forms":
            return mock_forms_service
        return MagicMock()

    mocker.patch('googleapiclient.discovery.build', side_effect=mock_build)

    # Mock SMTP
    mock_smtp = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp)
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

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
    mock_smtp.send_message.assert_not_called()

    # Verify Google Drive was not called (no surveys needed)
    mock_drive_service.files.assert_not_called()


def test_main_handles_existing_survey_link(requests_mock, mocker):
    """Test that main() reuses existing survey links from cache"""
    # Mock file operations - existing survey link in cache
    existing_links = {
        "John Doe": {
            "Woodshop Safety with John": "https://forms.google.com/existing_survey"
        }
    }
    mock_file = mock_open(read_data=json.dumps(existing_links))
    mocker.patch('builtins.open', mock_file)

    # Mock Google credentials
    mock_creds = MagicMock()
    mock_creds.with_subject.return_value = mock_creds
    mocker.patch(
        'google.oauth2.service_account.Credentials.from_service_account_file',
        return_value=mock_creds
    )

    # Mock Google APIs (should not be called for survey creation)
    mock_drive_service = MagicMock()
    mock_forms_service = MagicMock()

    def mock_build(service_name, version, credentials):
        if service_name == "drive":
            return mock_drive_service
        elif service_name == "forms":
            return mock_forms_service
        return MagicMock()

    mocker.patch('googleapiclient.discovery.build', side_effect=mock_build)

    # Mock SMTP
    mock_smtp = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp)
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

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
    mock_drive_service.files.assert_not_called()

    # Verify email was sent (sendmail is used, not send_message)
    assert mock_smtp.sendmail.called, "Email should be sent to attendee"
