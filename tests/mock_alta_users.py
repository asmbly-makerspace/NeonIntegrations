from typing import List

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

# import openPathUtil

class MockAltaUserBuilder():
    def __init__(self):
        self.reset()

    def reset(self):
        # Alta IDs are only numeric
        self._alta_id = 123
        self._name = "John Doe"
        self._email = "john@example.com"
        self._groups = []
        return self

    def with_groups(self, groups: List[str]):
        self._groups.extend(groups)
        return self

    def build(self):
        return {
            'OpenPathID': self._alta_id,
            'name': self._name,
            'email': self._email,
            'groups': self._groups,
        }

