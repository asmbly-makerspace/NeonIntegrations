from unittest.mock import MagicMock, Mock, patch

import pytest

# Import after conftest has set up mocks
from mailjetUtil import (
    MJService,
    MJCredentials,
    Subscriber,
    MailjetAction,
)


@pytest.fixture
def mock_mailjet_client(mocker):
    """Mock the Mailjet client."""
    mock_client = MagicMock()

    # Mock the contactslist.get() for list ID retrieval
    mock_list_response = Mock()
    mock_list_response.ok = True
    mock_list_response.status_code = 200
    mock_list_response.content = b'{"Count":2,"Data":[{"ID":123,"Name":"NewMembers","IsDeleted":false,"SubscriberCount":10,"CreatedAt":"2024-01-01T00:00:00Z"},{"ID":456,"Name":"AllContacts","IsDeleted":false,"SubscriberCount":100,"CreatedAt":"2024-01-01T00:00:00Z"}],"Total":2}'

    mock_client.contactslist.get.return_value = mock_list_response

    # Patch Client at import time
    with patch('mailjetUtil.Client', return_value=mock_client):
        yield mock_client


@pytest.fixture
def mj_service(mock_mailjet_client):
    """Create a MJService instance with mocked client."""
    credentials = MJCredentials(public_key="test_key", secret_key="test_secret")
    with patch('mailjetUtil.Client', return_value=mock_mailjet_client):
        service = MJService(credentials)
        service.client = mock_mailjet_client
        return service


class TestGetJobStatus:
    """Test suite for get_job_status method with retry functionality."""

    def test_get_job_status_success_first_try(self, mj_service, mock_mailjet_client):
        """Test successful job status retrieval on first attempt."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Data": [{"Status": "Completed", "JobID": 12345}]
        }

        mock_mailjet_client.contact_managemanycontacts.get.return_value = mock_response

        status = mj_service.get_job_status(12345)

        assert status == "Completed"
        assert mock_mailjet_client.contact_managemanycontacts.get.call_count == 1

    def test_get_job_status_404_then_success(self, mj_service, mock_mailjet_client):
        """Test job status retrieval with 404 (not ready) then success."""
        # First call returns 404, second call returns success
        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.json.return_value = {
            "ErrorInfo": "",
            "ErrorMessage": "Object not found",
            "StatusCode": 404
        }

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "Data": [{"Status": "Completed", "JobID": 12345}]
        }

        mock_mailjet_client.contact_managemanycontacts.get.side_effect = [
            mock_404_response,
            mock_success_response
        ]

        status = mj_service.get_job_status(12345)

        assert status == "Completed"
        assert mock_mailjet_client.contact_managemanycontacts.get.call_count == 2

    def test_get_job_status_multiple_404s_then_success(self, mj_service, mock_mailjet_client):
        """Test job status retrieval with multiple 404s before success."""
        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.json.return_value = {
            "ErrorInfo": "",
            "ErrorMessage": "Object not found",
            "StatusCode": 404
        }

        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {
            "Data": [{"Status": "Completed", "JobID": 12345}]
        }

        # 3 404s, then success
        mock_mailjet_client.contact_managemanycontacts.get.side_effect = [
            mock_404_response,
            mock_404_response,
            mock_404_response,
            mock_success_response
        ]

        status = mj_service.get_job_status(12345)

        assert status == "Completed"
        assert mock_mailjet_client.contact_managemanycontacts.get.call_count == 4

    def test_get_job_status_max_retries_exhausted(self, mj_service, mock_mailjet_client):
        """Test job status retrieval when max retries are exhausted (all 404s)."""
        from tenacity import RetryError

        mock_404_response = Mock()
        mock_404_response.status_code = 404
        mock_404_response.json.return_value = {
            "ErrorInfo": "",
            "ErrorMessage": "Object not found",
            "StatusCode": 404
        }

        # Always return 404
        mock_mailjet_client.contact_managemanycontacts.get.return_value = mock_404_response

        # Should raise RetryError after exhausting retries
        with pytest.raises(RetryError):
            mj_service.get_job_status(12345)

        # Should attempt 5 times (initial + 4 retries)
        assert mock_mailjet_client.contact_managemanycontacts.get.call_count == 5

    def test_get_job_status_error_response(self, mj_service, mock_mailjet_client):
        """Test job status retrieval with non-404 error response."""
        mock_error_response = Mock()
        mock_error_response.status_code = 500
        mock_error_response.json.return_value = {
            "ErrorInfo": "",
            "ErrorMessage": "Internal Server Error",
            "StatusCode": 500
        }

        mock_mailjet_client.contact_managemanycontacts.get.return_value = mock_error_response

        status = mj_service.get_job_status(12345)

        assert status is None
        # Should not retry on 500 error
        assert mock_mailjet_client.contact_managemanycontacts.get.call_count == 1


class TestGetIndContact:
    """Test suite for get_ind_contact method."""

    def test_get_ind_contact_success(self, mj_service, mock_mailjet_client):
        """Test successful individual contact retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"Count":1,"Data":[{"ContactID":789,"ID":999,"Data":[{"Name":"first_name","Value":"John"},{"Name":"last_name","Value":"Doe"},{"Name":"attended_orientation","Value":true},{"Name":"signed_waiver","Value":true},{"Name":"active_member","Value":false}]}],"Total":1}'

        mock_mailjet_client.contactdata.get.return_value = mock_response

        subscriber = mj_service.get_ind_contact("john.doe@example.com")

        assert subscriber is not None
        assert subscriber.first_name == "John"
        assert subscriber.last_name == "Doe"
        assert subscriber.attended_orientation is True
        assert subscriber.signed_waiver is True
        assert subscriber.active_member is False

    def test_get_ind_contact_404_not_found(self, mj_service, mock_mailjet_client):
        """Test individual contact retrieval when contact not found (404)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {
            "ErrorInfo": "",
            "ErrorMessage": "Object not found",
            "StatusCode": 404
        }

        mock_mailjet_client.contactdata.get.return_value = mock_response

        subscriber = mj_service.get_ind_contact("notfound@example.com")

        assert subscriber is None
        assert mock_mailjet_client.contactdata.get.call_count == 1


class TestBulkUpdateSubscribersInLists:
    """Test suite for bulk_update_subscribers_in_lists method."""

    def test_bulk_update_empty_subscribers(self, mj_service):
        """Test bulk update with empty subscriber list."""
        result = mj_service.bulk_update_subscribers_in_lists(
            list_ids=[123],
            subscribers=[],
            action=MailjetAction.ADD_NOFORCE
        )

        assert result is None

    def test_bulk_update_no_list_ids(self, mj_service):
        """Test bulk update with no valid list IDs."""
        subscriber = Subscriber(
            email_="test@example.com",
            id_=None,
            first_name="Test",
            last_name="User",
            attended_orientation=False,
            orientation_date=None,
            signed_waiver=False,
            active_member=False,
            latest_membership_end=None
        )

        result = mj_service.bulk_update_subscribers_in_lists(
            list_ids=[None],
            subscribers=[subscriber],
            action=MailjetAction.ADD_NOFORCE
        )

        assert result is None

    def test_bulk_update_success(self, mj_service, mock_mailjet_client):
        """Test successful bulk update."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "Data": [{"JobID": 54321}]
        }

        mock_mailjet_client.contact_managemanycontacts.create.return_value = mock_response

        subscriber = Subscriber(
            email_="test@example.com",
            id_=None,
            first_name="Test",
            last_name="User",
            attended_orientation=True,
            orientation_date=None,  # Simplified to avoid timezone issues
            signed_waiver=True,
            active_member=True,
            latest_membership_end=None  # Simplified to avoid timezone issues
        )

        job_id = mj_service.bulk_update_subscribers_in_lists(
            list_ids=[123, 456],
            subscribers=[subscriber],
            action=MailjetAction.ADD_NOFORCE
        )

        assert job_id == 54321
        assert mock_mailjet_client.contact_managemanycontacts.create.call_count == 1


class TestSubscriberModel:
    """Test suite for Subscriber model validation."""

    def test_subscriber_requires_email_or_id(self):
        """Test that Subscriber requires either email or ID."""
        with pytest.raises(ValueError, match="Either email_ or id_ must be provided"):
            Subscriber(
                email_=None,
                id_=None,
                first_name="Test",
                last_name="User",
                attended_orientation=False,
                orientation_date=None,
                signed_waiver=False,
                active_member=False,
                latest_membership_end=None
            )

    def test_subscriber_email_lowercase(self):
        """Test that subscriber email property returns lowercase."""
        subscriber = Subscriber(
            email_="TEST@EXAMPLE.COM",
            id_=None,
            first_name="Test",
            last_name="User",
            attended_orientation=False,
            orientation_date=None,
            signed_waiver=False,
            active_member=False,
            latest_membership_end=None
        )

        assert subscriber.email == "test@example.com"

    def test_subscriber_full_name(self):
        """Test subscriber full_name property."""
        subscriber = Subscriber(
            email_="test@example.com",
            id_=None,
            first_name="John",
            last_name="Doe",
            attended_orientation=False,
            orientation_date=None,
            signed_waiver=False,
            active_member=False,
            latest_membership_end=None
        )

        assert subscriber.full_name == "John Doe"
