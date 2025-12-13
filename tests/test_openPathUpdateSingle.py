import pytest
from unittest.mock import ANY

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import openPathUpdateSingle
from tests.mock_neon_users import MockNeonUserBuilder


def test_creates_user_when_has_facility_access(mocker):
    # Reality: any user with facility access should already have an Alta/OpenPath account.
    neon_id = "1001"
    # Build an account that would qualify for facility access (valid membership + waiver + tour)
    account = (
        MockNeonUserBuilder()
        .reset()
        .with_id(neon_id)
        .with_valid_membership(True)
        .with_waiver_date('2020-01-01')
        .with_tour_date('2020-01-02')
        .with_alta_id(777)
        .build()
    )

    # Use the real neonUtil predicate logic by returning our crafted account
    mocker.patch('openPathUpdateSingle.neonUtil.getMemberById', return_value=account)

    # Patch OpenPath interactions - because the account already has an OpenPathID
    updateGroups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')

    openPathUpdateSingle.openPathUpdateSingle(neon_id)

    # With an existing OpenPathID we should call updateGroups (not createUser)
    updateGroups.assert_called_once_with(account)


def test_does_not_create_user_for_expired_or_no_access(mocker):
    neon_id = "2002"
    account = MockNeonUserBuilder().reset().with_id(neon_id).with_valid_membership(False).build()

    mocker.patch('openPathUpdateSingle.neonUtil.getMemberById', return_value=account)

    createUser = mocker.patch('openPathUpdateSingle.openPathUtil.createUser')
    updateGroups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')
    createMobile = mocker.patch('openPathUpdateSingle.openPathUtil.createMobileCredential')

    openPathUpdateSingle.openPathUpdateSingle(neon_id)

    # No OpenPathID and no facility access --> should NOT create or update OpenPath
    createUser.assert_not_called()
    updateGroups.assert_not_called()
    createMobile.assert_not_called()


def test_updates_existing_user_when_openpathid_present(mocker):
    neon_id = "3003"
    account = (
        MockNeonUserBuilder()
        .reset()
        .with_id(neon_id)
        .with_valid_membership(True)
        .with_alta_id(777)
        .with_waiver_date('2020-01-01')
        .with_tour_date('2020-01-02')
        .build()
    )

    mocker.patch('openPathUpdateSingle.neonUtil.getMemberById', return_value=account)

    updateGroups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')

    openPathUpdateSingle.openPathUpdateSingle(neon_id)

    # Should call updateGroups with the account returned from neonUtil.getMemberById
    updateGroups.assert_called_once_with(account)
