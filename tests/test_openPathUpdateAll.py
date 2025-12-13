import pytest
from typing import Tuple
import datetime

##### Needed for importing script files (as opposed to classes)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
##### End block

import openPathUpdateAll
import neonUtil
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
            'createUser': mocker.patch('openPathUtil.createUser'),
            'createMobileCredential': mocker.patch('openPathUtil.createMobileCredential'),
        }

    def test_update_all_basic(self, mocker, setup_mocks):
        """Test basic bulk update with users that have existing OpenPathIDs"""
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

    def test_bulk_update_with_mixed_membership_types(self, mocker, setup_mocks):
        """Test bulk update with mix of paid regular, paid ceramics, and comped users"""
        neon_accounts = {}
        alta_accounts = {}

        # User 1: Paid regular membership with facility access
        paid_regular = (MockNeonUserBuilder()
                       .with_id("1001")
                       .with_alta_id(1001)
                       .with_names("Alice", "Regular")
                       .with_email("alice@example.com")
                       .with_membership("2024-01-01", "2025-12-31", fee=100.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_REGULAR)
                       .with_waiver_date("2024-01-15")
                       .with_tour_date("2024-01-16")
                       .build())
        neon_accounts["1001"] = paid_regular
        alta_accounts[1001] = MockAltaUserBuilder().with_id(1001).with_groups(['facility_access']).build()

        # User 2: Paid ceramics membership with facility access
        paid_ceramics = (MockNeonUserBuilder()
                        .with_id("1002")
                        .with_alta_id(1002)
                        .with_names("Bob", "Ceramics")
                        .with_email("bob@example.com")
                        .with_membership("2024-01-01", "2025-12-31", fee=150.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_CERAMICS)
                        .with_waiver_date("2024-01-15")
                        .with_tour_date("2024-01-16")
                        .build())
        neon_accounts["1002"] = paid_ceramics
        alta_accounts[1002] = MockAltaUserBuilder().with_id(1002).with_groups(['ceramics_access']).build()

        # User 3: Comped regular membership (no waiver/tour - no facility access)
        comped_regular = (MockNeonUserBuilder()
                         .with_id("1003")
                         .with_alta_id(1003)
                         .with_names("Carol", "Comped")
                         .with_email("carol@example.com")
                         .with_membership("2024-01-01", "2025-12-31", fee=0.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_REGULAR)
                         .build())
        neon_accounts["1003"] = comped_regular
        alta_accounts[1003] = MockAltaUserBuilder().with_id(1003).with_groups([]).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify updateGroups is called for users with existing OpenPathID
        assert setup_mocks['updateGroups'].call_count == 3
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_creates_user_for_facility_access_without_openpathid(self, mocker, setup_mocks):
        """Test that bulk update creates new OpenPath user for member with facility access but no OpenPathID"""
        neon_accounts = {}
        alta_accounts = {}

        # User 1: Has facility access but NO OpenPathID
        facility_user = (MockNeonUserBuilder()
                        .with_id("2001")
                        .with_alta_id(None)  # No OpenPathID
                        .with_names("Dave", "NewFacility")
                        .with_email("dave@example.com")
                        .with_membership("2024-01-01", "2025-12-31", fee=100.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_REGULAR)
                        .with_waiver_date("2024-01-15")
                        .with_tour_date("2024-01-16")
                        .build())
        neon_accounts["2001"] = facility_user

        # Create returned user with OpenPathID assigned by createUser
        created_user = facility_user.copy()
        created_user['OpenPathID'] = 2001
        setup_mocks['createUser'].return_value = created_user

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify createUser is called for this user
        setup_mocks['createUser'].assert_called_once()
        setup_mocks['createMobileCredential'].assert_called_once()
        # updateGroups should be called with empty groups list per openPathUpdateAll implementation
        setup_mocks['updateGroups'].assert_called_once()
        call_args = setup_mocks['updateGroups'].call_args
        assert call_args[1]['openPathGroups'] == []

    def test_bulk_update_ignores_no_membership_no_openpathid(self, mocker, setup_mocks):
        """Test that bulk update ignores users without membership and no OpenPathID"""
        neon_accounts = {}
        alta_accounts = {}

        # User without membership and no OpenPathID - should be skipped
        no_access = (MockNeonUserBuilder()
                    .with_id("3001")
                    .with_alta_id(None)
                    .with_names("Eve", "NoAccess")
                    .with_email("eve@example.com")
                    .with_valid_membership(False)
                    .build())
        neon_accounts["3001"] = no_access

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify no OpenPath operations are called
        setup_mocks['updateGroups'].assert_not_called()
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_warns_missing_waiver(self, mocker, setup_mocks):
        """Test that bulk update warns about users with OpenPathID but missing waiver"""
        neon_accounts = {}
        alta_accounts = {}

        # User has OpenPathID and facility access but missing waiver
        missing_waiver = (MockNeonUserBuilder()
                         .with_id("4001")
                         .with_alta_id(4001)
                         .with_names("Frank", "NoWaiver")
                         .with_email("frank@example.com")
                         .with_membership("2024-01-01", "2025-12-31", fee=100.0)
                         .with_waiver_date(None)  # Missing waiver!
                         .with_tour_date("2024-01-16")
                         .build())
        neon_accounts["4001"] = missing_waiver
        alta_accounts[4001] = MockAltaUserBuilder().with_id(4001).with_groups(['facility_access']).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify updateGroups is called (they have OpenPathID)
        setup_mocks['updateGroups'].assert_called_once()

    def test_bulk_update_handles_multiple_accounts_in_batches(self, mocker, setup_mocks):
        """Test bulk update with large batch of accounts to verify loop handling"""
        neon_accounts = {}
        alta_accounts = {}

        # Create 20 users with varying membership statuses
        for i in range(20):
            user = (MockNeonUserBuilder()
                   .with_id(str(5000 + i))
                   .with_alta_id(5000 + i)
                   .with_names(f"User{i}", f"Batch{i}")
                   .with_email(f"user{i}@example.com")
                   .build())

            if i % 3 == 0:  # Every 3rd user gets paid membership with facility access
                user = (MockNeonUserBuilder()
                       .with_id(str(5000 + i))
                       .with_alta_id(5000 + i)
                       .with_names(f"User{i}", f"Batch{i}")
                       .with_email(f"user{i}@example.com")
                       .with_membership("2024-01-01", "2025-12-31", fee=100.0)
                       .with_waiver_date("2024-01-15")
                       .with_tour_date("2024-01-16")
                       .build())

            neon_accounts[str(5000 + i)] = user
            alta_accounts[5000 + i] = MockAltaUserBuilder().with_id(5000 + i).with_groups([f'group_{i}']).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # All users have OpenPathID, so updateGroups should be called 20 times
        assert setup_mocks['updateGroups'].call_count == 20

    def test_bulk_update_counts_subscription_types_accurately(self, mocker, setup_mocks):
        """Test that bulk update correctly counts paid regular vs ceramics subscriptions"""
        neon_accounts = {}
        alta_accounts = {}

        # User 1: Paid regular only
        paid_regular = (MockNeonUserBuilder()
                       .with_id("6001")
                       .with_alta_id(6001)
                       .with_names("Grace", "RegularOnly")
                       .with_email("grace@example.com")
                       .with_membership("2024-01-01", "2025-12-31", fee=100.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_REGULAR)
                       .build())
        neon_accounts["6001"] = paid_regular
        alta_accounts[6001] = MockAltaUserBuilder().with_id(6001).build()

        # User 2: Paid ceramics only
        paid_ceramics = (MockNeonUserBuilder()
                        .with_id("6002")
                        .with_alta_id(6002)
                        .with_names("Helen", "CeramicsOnly")
                        .with_email("helen@example.com")
                        .with_membership("2024-01-01", "2025-12-31", fee=150.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_CERAMICS)
                        .build())
        neon_accounts["6002"] = paid_ceramics
        alta_accounts[6002] = MockAltaUserBuilder().with_id(6002).build()

        # User 3: Both paid regular AND paid ceramics (upgrade case - should count as ceramics only)
        both_paid = (MockNeonUserBuilder()
                    .with_id("6003")
                    .with_alta_id(6003)
                    .with_names("Ivan", "BothPaid")
                    .with_email("ivan@example.com")
                    .with_membership("2024-01-01", "2025-12-31", fee=100.0, membershipLevelId=neonUtil.MEMBERSHIP_ID_REGULAR)
                    .build())
        # Add ceramics membership to same user
        both_paid['paidCeramics'] = True
        both_paid['paidRegular'] = True
        neon_accounts["6003"] = both_paid
        alta_accounts[6003] = MockAltaUserBuilder().with_id(6003).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # All should call updateGroups (all have OpenPathID)
        assert setup_mocks['updateGroups'].call_count == 3

    def test_bulk_update_missing_required_access_fields(self, mocker, setup_mocks):
        """Test bulk update with users missing required facility access fields"""
        neon_accounts = {}
        alta_accounts = {}

        # User with membership but missing both waiver AND tour - should not get facility access
        incomplete_access = (MockNeonUserBuilder()
                            .with_id("7001")
                            .with_alta_id(7001)
                            .with_names("Jack", "Incomplete")
                            .with_email("jack@example.com")
                            .with_membership("2024-01-01", "2025-12-31", fee=100.0)
                            .with_waiver_date(None)
                            .with_tour_date(None)
                            .build())
        neon_accounts["7001"] = incomplete_access
        alta_accounts[7001] = MockAltaUserBuilder().with_id(7001).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Has OpenPathID so updateGroups is called, but no createUser (missing access requirements)
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()

    def test_bulk_update_openpathid_as_integer_conversion(self, mocker, setup_mocks):
        """Test that bulk update correctly converts OpenPathID to int for Alta lookup"""
        neon_accounts = {}
        alta_accounts = {}

        # User with OpenPathID that might come as string from Neon
        user_with_id = (MockNeonUserBuilder()
                       .with_id("8001")
                       .with_alta_id(8001)
                       .with_names("Karen", "StringID")
                       .with_email("karen@example.com")
                       .build())
        neon_accounts["8001"] = user_with_id
        alta_accounts[8001] = MockAltaUserBuilder().with_id(8001).with_groups(['test_group']).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Should successfully find user in Alta accounts via int conversion
        setup_mocks['updateGroups'].assert_called_once()
        call_args = setup_mocks['updateGroups'].call_args
        assert call_args[1]['openPathGroups'] == ['test_group']

    def test_bulk_update_with_access_suspended(self, mocker, setup_mocks):
        """Test that suspended accounts don't get facility access even with waiver/tour"""
        neon_accounts = {}
        alta_accounts = {}

        # User with facility access requirements but access is suspended
        suspended_user = (MockNeonUserBuilder()
                         .with_id("9001")
                         .with_alta_id(9001)
                         .with_names("Liam", "Suspended")
                         .with_email("liam@example.com")
                         .with_membership("2024-01-01", "2025-12-31", fee=100.0)
                         .with_waiver_date("2024-01-15")
                         .with_tour_date("2024-01-16")
                         .build())
        suspended_user['AccessSuspended'] = True
        neon_accounts["9001"] = suspended_user
        alta_accounts[9001] = MockAltaUserBuilder().with_id(9001).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Should still update groups (has OpenPathID), but not create new access
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()

