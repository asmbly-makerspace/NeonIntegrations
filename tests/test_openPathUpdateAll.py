import pytest
import pdb


##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import openPathUpdateAll
from mock_neon_users import MockNeonUserBuilder
from mock_alta_users import MockAltaUserBuilder

class TestOpenPathUpdateAll:
    def test_update_all(self, mocker):
        mock_func = mocker.patch('openPathUtil.getAllUsers')
        mock_alta_account = (MockAltaUserBuilder()
                             .with_groups(['test_group'])
                             .build()
                            )
        alta_accts = {}
        # This puts the accounts into the format that the scripts are
        # expecting: Each account is a dict, and they're contained within a
        # dict, indexed by the account ID. For example:
        # { '123': { 'OpenPathID': '123' } }
        alta_accts[mock_alta_account['OpenPathID']] = mock_alta_account
        mock_func.return_value = alta_accts

        accounts = {}
        acct = (MockNeonUserBuilder()
            .build())
        accounts[acct['id']] = acct

        mock_update_groups = mocker.patch('openPathUtil.updateGroups')
        expected_calls = [
            mocker.call(acct, openPathGroups=['test_group']),
        ]
        openPathUpdateAll.openPathUpdateAll(accounts)
        mock_update_groups.assert_has_calls(expected_calls)
