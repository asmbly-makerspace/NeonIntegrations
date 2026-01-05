"""
Unit tests for dailyClassChecker.py

Tests the main() function by mocking only network interactions (HTTP requests and SMTP).
"""

from unittest.mock import MagicMock

from neonUtil import N_baseURL


def test_main_sends_email_with_class_info(requests_mock, mocker):
    """Test that main() fetches class data and sends an email summary"""
    # Mock SMTP to avoid actual email sending
    mock_smtp = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp)
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    # Mock event search - return no events (simplest case)
    event_search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": []}
    )

    import dailyClassChecker
    dailyClassChecker.main()

    # Verify event search API was called
    assert event_search_mock.called, "Event search API should be called"

    # Verify SMTP was used to send an email
    mock_smtp.send_message.assert_called_once()

    # Verify email was sent to the correct recipient
    email_message = mock_smtp.send_message.call_args[0][0]
    assert email_message["to"] == "classes@asmbly.org"
    assert "Currently Scheduled Classes" in email_message["subject"]


def test_main_processes_scheduled_classes(requests_mock, mocker):
    """Test that main() processes scheduled classes and includes them in email"""
    # Mock SMTP
    mock_smtp = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp)
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    import datetime
    future_date = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()

    # Mock event search - return one Orientation class
    event_search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={
            "searchResults": [{
                "Event ID": "123",
                "Event Name": "Orientation with John",
                "Event Topic": "John Doe",
                "Event Start Date": future_date,
                "Event End Date": future_date,
                "Event Registration Attendee Count": 5,
                "Registrants": 5,
                "Event Capacity": 10,
            }]
        }
    )

    # Mock registrants endpoint (called when counts don't match)
    registrants_mock = requests_mock.get(
        f'{N_baseURL}/events/123/eventRegistrations',
        json={
            "eventRegistrations": [{
                "registrantAccountId": 456,
                "tickets": [{
                    "attendees": [{
                        "registrationStatus": "SUCCEEDED",
                        "firstName": "Test",
                        "lastName": "User"
                    }]
                }]
            }]
        }
    )

    import dailyClassChecker
    dailyClassChecker.main()

    # Verify API calls were made
    assert event_search_mock.called, "Event search API should be called"

    # Verify email was sent
    mock_smtp.send_message.assert_called_once()

    # Get the email that was sent
    email_message = mock_smtp.send_message.call_args[0][0]

    # Verify the email contains expected content
    email_body = email_message.as_string()
    assert "Orientation" in email_body, "Email should contain class name"
    assert email_message["to"] == "classes@asmbly.org", "Email should be sent to classes@asmbly.org"


def test_main_handles_empty_results(requests_mock, mocker):
    """Test that main() handles empty search results gracefully"""
    # Mock SMTP
    mock_smtp = MagicMock()
    mocker.patch('smtplib.SMTP_SSL', return_value=mock_smtp)
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    # Mock event search - return empty results
    event_search_mock = requests_mock.post(
        f'{N_baseURL}/events/search',
        json={"searchResults": []}
    )

    import dailyClassChecker
    dailyClassChecker.main()

    # Verify API was called
    assert event_search_mock.called, "Event search API should be called"

    # Should still send an email (with empty class tables)
    mock_smtp.send_message.assert_called_once()

    # Verify email structure
    email_message = mock_smtp.send_message.call_args[0][0]
    assert email_message["to"] == "classes@asmbly.org"
