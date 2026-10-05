"""
Unit tests for classFeedbackAutomation.py

Tests the main() function by mocking only network interactions.
"""

import pytest
import json
from unittest.mock import mock_open

from neon_mocker import NeonUserMock, NeonEventMock

# classFeedbackAutomation imports the Google client libraries at module level.
# CI and EC2 get them from requirements.txt. Skip this file only where they are
# actually missing (e.g. a uv environment without google-api-python-client).
pytest.importorskip('googleapiclient.discovery')
pytest.importorskip('google.oauth2.service_account')

import classFeedbackAutomation

# Production IDs hardcoded in getSurveyLink()
TEMPLATE_FILE_ID = "1zCmHpktgblR8auKWMO6eNdTBt2frGj3Q6ExFTP9rHKI"
SURVEY_FOLDER_ID = "17aM-fE8bBZqDZA1NhnWupAFan87Tpdsd"

NEW_SURVEY_ID = "new_survey_id"
NEW_SURVEY_URL = "https://docs.google.com/forms/d/e/new_survey/viewform"


def written_survey_links(open_mock):
    """Return the dict main() wrote back to surveyLinks.json."""
    open_mock.assert_any_call('surveyLinks.json', 'w', encoding='utf-8')
    written = ''.join(c.args[0] for c in open_mock.return_value.write.call_args_list)
    return json.loads(written)


class TestClassFeedbackAutomation:
    """Test suite for classFeedbackAutomation.main()"""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_smtp, mock_google_apis, mocker):
        """Setup SMTP and Google API mocks for all tests in this class."""
        self.mock_smtp = mock_smtp
        self.mock_google_apis = mock_google_apis
        self.drive = mock_google_apis['drive']
        self.forms = mock_google_apis['forms']

        # classFeedbackAutomation does `from googleapiclient.discovery import build`,
        # so it keeps its own reference to build from the first import. The
        # conftest fixture patches googleapiclient.discovery.build, which main()
        # never looks up, so patch the module's name to hand main() this test's
        # Drive and Forms mocks. (Credentials needs no extra patch: conftest
        # patches from_service_account_file on the class, which the module shares.)
        services = {'drive': self.drive, 'forms': self.forms}
        self.mock_build = mocker.patch.object(
            classFeedbackAutomation, 'build',
            side_effect=lambda serviceName, version, credentials: services[serviceName],
        )

        # Default Google responses: no survey for the class in Drive yet, so
        # getSurveyLink() copies the template and returns the new survey's URL
        self.drive.files.return_value.list.return_value.execute.return_value = {'files': []}
        self.drive.files.return_value.copy.return_value.execute.return_value = {'id': NEW_SURVEY_ID}
        self.forms.forms.return_value.get.return_value.execute.return_value = {
            'responderUri': NEW_SURVEY_URL
        }

    def sent_email(self):
        """Return the text of the single survey email main() sent."""
        self.mock_smtp.sendmail.assert_called_once()
        return self.mock_smtp.sendmail.call_args.args[2]

    def test_main_runs_with_no_events(self, requests_mock):
        """Test that main() runs successfully when there are no events to process"""
        search_mock, _ = NeonEventMock.mock_events(requests_mock, [])

        classFeedbackAutomation.main()

        # Verify event search API was called
        assert search_mock.called, "Neon event search API should be called"

        # Verify no emails were sent (no events)
        self.mock_smtp.send_message.assert_not_called()
        self.mock_smtp.sendmail.assert_not_called()

        # Verify main() built its services from this test's mocks, so the
        # Drive assertion below can fail
        self.mock_build.assert_any_call(
            'drive', 'v3', credentials=self.mock_google_apis['credentials']
        )

        # Verify Google Drive was not called (no surveys needed)
        self.drive.files.assert_not_called()

    def test_main_handles_existing_survey_link(self, requests_mock, mocker):
        """Test that main() reuses existing survey links from cache"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)
        search_mock, [(registrants_mock, account_mocks)] = NeonEventMock.mock_events(
            requests_mock, [event]
        )

        # Override builtins.open to return existing survey links
        existing_links = {
            event.teacher: {
                event.event_name: "https://forms.google.com/existing_survey"
            }
        }
        mocker.patch('builtins.open', mock_open(read_data=json.dumps(existing_links)))

        classFeedbackAutomation.main()

        # Verify Neon APIs were called
        assert search_mock.called, "Neon event search should be called"
        assert registrants_mock.called, "Neon registrants API should be called"
        assert account_mocks[0].called, "Neon account API should be called"

        # Verify Drive and Forms APIs were NOT called (should use cached link)
        self.drive.files.assert_not_called()
        self.forms.forms.assert_not_called()

        # Verify email was sent (sendmail is used, not send_message) with the cached link
        assert "https://forms.google.com/existing_survey" in self.sent_email()

    def test_main_copies_template_when_class_has_no_survey(self, requests_mock, mocker):
        """Test that main() copies the template survey for a class with no survey yet"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)
        NeonEventMock.mock_events(requests_mock, [event])

        # Empty survey links cache
        open_mock = mocker.patch('builtins.open', mock_open(read_data='{}'))

        classFeedbackAutomation.main()

        # Verify Drive was searched for an existing survey with the class name
        list_kwargs = self.drive.files.return_value.list.call_args.kwargs
        assert f"name='{event.event_name}'" in list_kwargs['q']
        assert f"'{SURVEY_FOLDER_ID}' in parents" in list_kwargs['q']

        # Verify the template was copied into the survey folder under the class name
        self.drive.files.return_value.copy.assert_called_once_with(
            fileId=TEMPLATE_FILE_ID,
            body={'name': event.event_name, 'parents': [SURVEY_FOLDER_ID]},
            supportsAllDrives=True,
        )
        self.forms.forms.return_value.get.assert_called_once_with(formId=NEW_SURVEY_ID)

        # Verify the student got the new survey's link and the link was saved
        assert NEW_SURVEY_URL in self.sent_email()
        assert written_survey_links(open_mock) == {
            event.teacher: {event.event_name: NEW_SURVEY_URL}
        }

    def test_main_reuses_survey_found_in_drive(self, requests_mock, mocker):
        """Test that main() reuses a survey already in Drive when the cache has no link"""
        student = NeonUserMock()
        event = NeonEventMock().add_registrant(student)
        NeonEventMock.mock_events(requests_mock, [event])

        # Empty survey links cache, but Drive already has a survey for the class
        open_mock = mocker.patch('builtins.open', mock_open(read_data='{}'))
        existing_url = "https://docs.google.com/forms/d/e/existing_survey/viewform"
        self.drive.files.return_value.list.return_value.execute.return_value = {
            'files': [{'id': 'existing_survey_id'}]
        }
        self.forms.forms.return_value.get.return_value.execute.return_value = {
            'responderUri': existing_url
        }

        classFeedbackAutomation.main()

        # Verify no new survey was copied and the existing survey's link was used
        self.drive.files.return_value.copy.assert_not_called()
        self.forms.forms.return_value.get.assert_called_once_with(formId='existing_survey_id')
        assert existing_url in self.sent_email()
        assert written_survey_links(open_mock) == {
            event.teacher: {event.event_name: existing_url}
        }
