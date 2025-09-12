import pytest
from unittest.mock import patch, MagicMock, call
from typing import Dict, List, Any
import datetime


class MockEventBuilder:
    def __init__(self):
        self.reset()

    def reset(self):
        self._event_id = "12345"
        self._event_name = "Test Class"
        self._event_topic = "John Doe"  # Teacher name
        self._event_start_date = datetime.date.today().isoformat()
        self._event_start_time = "10:00:00"
        self._event_end_date = datetime.date.today().isoformat()
        self._event_end_time = "12:00:00"
        self._registrants = 5
        self._registration_count = 5
        return self

    def with_teacher(self, teacher_name: str):
        self._event_topic = teacher_name
        return self

    def with_date(self, date: str):
        self._event_start_date = date
        self._event_end_date = date
        return self

    def with_event_id(self, event_id: str):
        self._event_id = event_id
        return self

    def with_event_name(self, name: str):
        self._event_name = name
        return self

    def build(self) -> Dict[str, Any]:
        return {
            "Event ID": self._event_id,
            "Event Name": self._event_name,
            "Event Topic": self._event_topic,
            "Event Start Date": self._event_start_date,
            "Event Start Time": self._event_start_time,
            "Event End Date": self._event_end_date,
            "Event End Time": self._event_end_time,
            "Event Registration Attendee Count": self._registration_count,
            "Registrants": self._registrants,
            "Hold To Waiting List": "No",
            "Waiting List Status": "Open"
        }
