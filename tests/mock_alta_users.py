from typing import Any, Dict, List, Self
import random

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

class MockAltaUserBuilder():
    def __init__(self):
        self.reset()

    def reset(self):
        # Alta IDs are only numeric - pick an integer between 1 and 100,000
        self._alta_id = random.randint(1, 100000)
        self._name = "John Doe"
        self._email = "john@example.com"
        self._groups = []
        return self

    def with_groups(self, groups: List[str]) -> Self:
        self._groups.extend(groups)
        return self

    def with_id(self, alta_id: int) -> Self:
        self._alta_id = alta_id
        return self

    def build(self) -> Dict[str, Any]:
        return {
            'OpenPathID': self._alta_id,
            'name': self._name,
            'email': self._email,
            'groups': self._groups,
        }

