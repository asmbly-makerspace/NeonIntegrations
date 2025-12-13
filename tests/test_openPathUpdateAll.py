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
        accts = {}
        for i, groups in enumerate(group_lists):
            # Cannot have a user with id 0
            acct = (MockAltaUserBuilder()
                    .with_id(i+1)
                    .with_groups(groups)
                    .build()
                   )
            accts[acct['OpenPathID']] = acct
        return accts

    def _create_neon_accounts(self, alta_ids):
        accts = {}
        for aid in alta_ids:
            acct = (MockNeonUserBuilder()
                    .with_alta_id(aid)
                    .build())
            # Key neon accounts by their canonical 'Account ID'
            accts.update({acct['Account ID']: acct})
        return accts

    def _create_matching_alta_and_neon_accounts(self, group_lists):
        # Create two users with accounts in Alta and in Neon (linked by OpenPathID)
        alta_accounts = self._create_alta_accounts(*group_lists)
        neon_accounts = self._create_neon_accounts(alta_accounts.keys())
        return (alta_accounts, neon_accounts)


    @pytest.fixture
    def setup_mocks(self, mocker):
        return {
            'getAllUsers': mocker.patch('openPathUtil.getAllUsers'),
            'updateGroups': mocker.patch('openPathUtil.updateGroups'),
        }

    def test_update_all(self, mocker, setup_mocks):
        # Create a set of fake accounts in Neon and Alta
        test_groups = (['test_group'], ['test_group_2'])
        (alta_accounts, neon_accounts) = self._create_matching_alta_and_neon_accounts(test_groups)

        # When `openPathUtil.getAllUsers()` is called, return our fake accounts
        # instead of actually connecting to OpenPath/Alta.
        setup_mocks['getAllUsers'].return_value = alta_accounts

        # Based on the fake user accounts we've just created, figure out what
        # arguments should be passed in when `openPathUtil.updateGroups` gets
        # called in openPathUpdateAll.py. We'll then check these arguments
        # against what actually gets passed in when the openPathUpdateAll
        # script runs.
        expected_calls = [
            mocker.call(neon_acct, openPathGroups=group_list)
            for neon_acct, group_list
            in zip(neon_accounts.values(), test_groups)
        ]

        # Run the openPathUpdateAll script with our fake accounts.
        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify that openPathUtil.updateGroups was called with the correct
        # arguments, based on our fake accounts.
        setup_mocks['updateGroups'].assert_has_calls(expected_calls)
