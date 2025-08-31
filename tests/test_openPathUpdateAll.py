import pytest
from typing import Tuple

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import openPathUpdateAll
from mock_neon_users import MockNeonUserBuilder
from mock_alta_users import MockAltaUserBuilder

class TestOpenPathUpdateAll:
    def _create_alta_accounts(self, *group_lists):
        mock_alta_accounts = {}
        for i, groups in enumerate(group_lists):
            # Cannot have a user with id 0
            mock_alta_account = (MockAltaUserBuilder()
                                 .with_id(i+1)
                                 .with_groups(groups)
                                 .build()
                                )
            mock_alta_accounts[mock_alta_account['OpenPathID']] = mock_alta_account
        return mock_alta_accounts

    def _create_neon_accounts(self, alta_ids):
        mock_neon_accounts = {}
        for aid in alta_ids:
            mock_neon_acct = (MockNeonUserBuilder()
                              .with_alta_id(aid)
                              .build())
            mock_neon_accounts.update({mock_neon_acct['id']: mock_neon_acct})
        return mock_neon_accounts

    @pytest.fixture
    def setup_mocks(self, mocker):
        return {
            'getAllUsers': mocker.patch('openPathUtil.getAllUsers'),
            'updateGroups': mocker.patch('openPathUtil.updateGroups'),
        }

    def test_update_all(self, mocker, setup_mocks):
        # Create two users with accounts in Alta and in Neon (linked by OpenPathID)
        test_groups = (['test_group'], ['test_group_2'])
        alta_accts = self._create_alta_accounts(*test_groups)
        neon_accounts = self._create_neon_accounts(alta_accts.keys())

        setup_mocks['getAllUsers'].return_value = alta_accts

        expected_calls = [
            mocker.call(neon_acct, openPathGroups=group_list)
            for neon_acct, group_list
            in zip(neon_accounts.values(), test_groups)
        ]

        openPathUpdateAll.openPathUpdateAll(neon_accounts)
        setup_mocks['updateGroups'].assert_has_calls(expected_calls)
