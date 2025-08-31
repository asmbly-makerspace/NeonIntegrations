from typing import Self
import string
import random

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import neonUtil

class MockNeonUserBuilder():
    def __init__(self):
        self.reset()

    def random_alphanumeric(self, length):
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    def reset(self):
        # TODO: Determine whether Neon IDs are alphanumeric or just numeric
        self._id = self.random_alphanumeric(6)
        self._name = "John Doe"
        self._email = "john@example.com"
        self._individual_types = []
        # TODO: Does this need to match the value in the MockAltaUserBuilder?
        self._open_path_id = '123'
        return self

    def with_type(self, neon_type):
        self._individual_types.append({'name': neon_type})
        return self

    def with_alta_id(self, alta_id: int) -> Self:
        self._open_path_id = alta_id
        return self

    def build(self):
        return {
            'id': self._id,
            'name': self._name,
            'email': self._email,
            'individualTypes': self._individual_types,
            'OpenPathID': self._open_path_id,
        }

