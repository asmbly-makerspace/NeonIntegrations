import pytest

from neonUtil import MEMBERSHIP_ID_REGULAR, MEMBERSHIP_ID_CERAMICS
import openPathUpdateAll
from mock_alta_users import MockAltaUserBuilder
from tests.neon_account_builder import today_plus, setup_neon_account

def _create_alta_accounts(*group_lists):
    accts = {}
    for i, groups in enumerate(group_lists):
        # Cannot have a user with id 0
        acct = (MockAltaUserBuilder()
                .with_id(i + 1)
                .with_groups(groups)
                .build()
                )
        accts[acct['OpenPathID']] = acct
    return accts


class TestOpenPathUpdateAll:

    @pytest.fixture
    def setup_mocks(self, mocker):
        return {
            'getAllUsers': mocker.patch('openPathUtil.getAllUsers'),
            'updateGroups': mocker.patch('openPathUtil.updateGroups'),
            'createUser': mocker.patch('openPathUtil.createUser'),
            'createMobileCredential': mocker.patch('openPathUtil.createMobileCredential'),
        }

    def test_update_all_basic(self, neon_api_mock, mocker, setup_mocks):
        """Test basic bulk update with users that have existing OpenPathIDs"""
        # Create Alta accounts with different groups
        test_groups = (['test_group'], ['test_group_2'])
        alta_accounts = _create_alta_accounts(*test_groups)

        # Create matching Neon accounts with OpenPathIDs
        neon_accounts = {}
        for i, (alta_id, groups) in enumerate(zip(alta_accounts.keys(), test_groups), start=1):
            account_id = i
            neon_accounts[str(account_id)] = setup_neon_account(
                neon_api_mock,
                account_id=account_id,
                first_name=f"User{i}",
                last_name=f"Test{i}",
                email=f"user{i}@example.com",
                open_path_id=alta_id
            )

        # When `openPathUtil.getAllUsers()` is called, return our fake accounts
        setup_mocks['getAllUsers'].return_value = alta_accounts

        # Run the openPathUpdateAll script with our fake accounts.
        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify that openPathUtil.updateGroups was called with the correct arguments
        expected_calls = [
            mocker.call(neon_acct, openPathGroups=group_list)
            for neon_acct, group_list
            in zip(neon_accounts.values(), test_groups)
        ]
        setup_mocks['updateGroups'].assert_has_calls(expected_calls)

    def test_bulk_update_with_mixed_membership_types(self, neon_api_mock, mocker, setup_mocks):
        """Test bulk update with mix of paid regular, paid ceramics, and comped users"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User 1: Paid regular membership with facility access
        neon_accounts["1001"] = setup_neon_account(
            neon_api_mock,
            account_id=1001,
            first_name="Alice",
            last_name="Regular",
            email="alice@example.com",
            memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=1001,
            waiver_date=start,
            facility_tour_date=tour
        )
        alta_accounts[1001] = MockAltaUserBuilder().with_id(1001).with_groups(['facility_access']).build()

        # User 2: Paid ceramics membership with facility access
        neon_accounts["1002"] = setup_neon_account(
            neon_api_mock,
            account_id=1002,
            first_name="Bob",
            last_name="Ceramics",
            email="bob@example.com",
            memberships=[(start, end, 150.0, MEMBERSHIP_ID_CERAMICS, False)],
            open_path_id=1002,
            waiver_date=start,
            facility_tour_date=tour
        )
        alta_accounts[1002] = MockAltaUserBuilder().with_id(1002).with_groups(['ceramics_access']).build()

        # User 3: Comped regular membership (no waiver/tour - no facility access)
        neon_accounts["1003"] = setup_neon_account(
            neon_api_mock,
            account_id=1003,
            first_name="Carol",
            last_name="Comped",
            email="carol@example.com",
            memberships=[(start, end, 0.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=1003
        )
        alta_accounts[1003] = MockAltaUserBuilder().with_id(1003).with_groups([]).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify updateGroups is called for users with existing OpenPathID
        assert setup_mocks['updateGroups'].call_count == 3
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_creates_user_for_facility_access_without_openpathid(self, neon_api_mock, mocker, setup_mocks):
        """Test that bulk update creates new OpenPath user for member with facility access but no OpenPathID"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User 1: Has facility access but NO OpenPathID
        facility_user = setup_neon_account(
            neon_api_mock,
            account_id=2001,
            first_name="Dave",
            last_name="NewFacility",
            email="dave@example.com",
            memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            waiver_date=start,
            facility_tour_date=tour
        )
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

    def test_bulk_update_ignores_no_membership_no_openpathid(self, neon_api_mock, mocker, setup_mocks):
        """Test that bulk update ignores users without membership and no OpenPathID"""
        neon_accounts = {}
        alta_accounts = {}

        # User without membership and no OpenPathID - should be skipped
        neon_accounts["3001"] = setup_neon_account(
            neon_api_mock,
            account_id=3001,
            first_name="Eve",
            last_name="NoAccess",
            email="eve@example.com"
        )

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify no OpenPath operations are called
        setup_mocks['updateGroups'].assert_not_called()
        setup_mocks['createUser'].assert_not_called()
        setup_mocks['createMobileCredential'].assert_not_called()

    def test_bulk_update_warns_missing_waiver(self, neon_api_mock, mocker, setup_mocks):
        """Test that bulk update warns about users with OpenPathID but missing waiver"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User has OpenPathID and facility access but missing waiver
        neon_accounts["4001"] = setup_neon_account(
            neon_api_mock,
            account_id=4001,
            first_name="Frank",
            last_name="NoWaiver",
            email="frank@example.com",
            memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=4001,
            facility_tour_date=tour
        )
        alta_accounts[4001] = MockAltaUserBuilder().with_id(4001).with_groups(['facility_access']).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Verify updateGroups is called (they have OpenPathID)
        setup_mocks['updateGroups'].assert_called_once()

    def test_bulk_update_handles_multiple_accounts_in_batches(self, neon_api_mock, mocker, setup_mocks):
        """Test bulk update with large batch of accounts to verify loop handling"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # Create 20 users with varying membership statuses
        for i in range(20):
            account_id = 5000 + i
            open_path_id = 5000 + i

            if i % 3 == 0:  # Every 3rd user gets paid membership with facility access
                neon_accounts[str(account_id)] = setup_neon_account(
                    neon_api_mock,
                    account_id=account_id,
                    first_name=f"User{i}",
                    last_name=f"Batch{i}",
                    email=f"user{i}@example.com",
                    memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
                    open_path_id=open_path_id,
                    waiver_date=start,
                    facility_tour_date=tour
                )
            else:
                neon_accounts[str(account_id)] = setup_neon_account(
                    neon_api_mock,
                    account_id=account_id,
                    first_name=f"User{i}",
                    last_name=f"Batch{i}",
                    email=f"user{i}@example.com",
                    open_path_id=open_path_id
                )
            alta_accounts[open_path_id] = MockAltaUserBuilder().with_id(open_path_id).with_groups([f'group_{i}']).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # All users have OpenPathID, so updateGroups should be called 20 times
        assert setup_mocks['updateGroups'].call_count == 20

    def test_bulk_update_counts_subscription_types_accurately(self, neon_api_mock, mocker, setup_mocks):
        """Test that bulk update correctly counts paid regular vs ceramics subscriptions"""
        start0 = today_plus(-365 * 2)
        end0 = today_plus(-366)
        start1 = today_plus(-365)
        end1 = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User 1: Paid regular only
        neon_accounts["6001"] = setup_neon_account(
            neon_api_mock,
            account_id=6001,
            first_name="Grace",
            last_name="RegularOnly",
            email="grace@example.com",
            memberships=[(start1, end1, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=6001
        )
        alta_accounts[6001] = MockAltaUserBuilder().with_id(6001).build()

        # User 2: Paid ceramics only
        neon_accounts["6002"] = setup_neon_account(
            neon_api_mock,
            account_id=6002,
            first_name="Helen",
            last_name="CeramicsOnly",
            email="helen@example.com",
            memberships=[(start1, end1, 150.0, MEMBERSHIP_ID_CERAMICS, False)],
            open_path_id=6002
        )
        alta_accounts[6002] = MockAltaUserBuilder().with_id(6002).build()

        # User 3: Both paid regular AND paid ceramics (upgrade case)
        # Create account with both memberships
        neon_accounts["6003"] = setup_neon_account(
            neon_api_mock,
            account_id=6003,
            first_name="Ivan",
            last_name="BothPaid",
            email="ivan@example.com",
            memberships=[
                (start0, end0, 100.0, MEMBERSHIP_ID_REGULAR, False),
                (start1, end1, 150.0, MEMBERSHIP_ID_CERAMICS, False),
            ],
            open_path_id=6003
        )
        alta_accounts[6003] = MockAltaUserBuilder().with_id(6003).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # All should call updateGroups (all have OpenPathID)
        assert setup_mocks['updateGroups'].call_count == 3

    def test_bulk_update_missing_required_access_fields(self, neon_api_mock, mocker, setup_mocks):
        """Test bulk update with users missing required facility access fields"""
        start = today_plus(-365)
        end = today_plus(365)

        neon_accounts = {}
        alta_accounts = {}

        # User with membership but missing both waiver AND tour - should not get facility access
        neon_accounts["7001"] = setup_neon_account(
            neon_api_mock,
            account_id=7001,
            first_name="Jack",
            last_name="Incomplete",
            email="jack@example.com",
            memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=7001
        )
        alta_accounts[7001] = MockAltaUserBuilder().with_id(7001).build()

        setup_mocks['getAllUsers'].return_value = alta_accounts

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Has OpenPathID so updateGroups is called, but no createUser (missing access requirements)
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()

    def test_bulk_update_openpathid_as_integer_conversion(self, neon_api_mock, mocker, setup_mocks):
        """Test that bulk update correctly converts OpenPathID to int for Alta lookup"""
        # User with OpenPathID that might come as string from Neon
        neon_accounts = {"8001": setup_neon_account(
            neon_api_mock,
            account_id=8001,
            first_name="Karen",
            last_name="StringID",
            email="karen@example.com",
            open_path_id=8001
        )}
        setup_mocks['getAllUsers'].return_value = {
            8001: MockAltaUserBuilder().with_id(8001).with_groups(['test_group']).build(),
        }

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Should successfully find user in Alta accounts via int conversion
        setup_mocks['updateGroups'].assert_called_once()
        call_args = setup_mocks['updateGroups'].call_args
        assert call_args[1]['openPathGroups'] == ['test_group']

    def test_bulk_update_with_access_suspended(self, neon_api_mock, mocker, setup_mocks):
        """Test that suspended accounts don't get facility access even with waiver/tour"""
        start = today_plus(-365)
        tour = today_plus(-364)
        end = today_plus(365)

        # User with facility access requirements but access is suspended
        neon_accounts = {"9001": setup_neon_account(
            neon_api_mock,
            account_id=9001,
            first_name="Liam",
            last_name="Suspended",
            email="liam@example.com",
            memberships=[(start, end, 100.0, MEMBERSHIP_ID_REGULAR, False)],
            open_path_id=9001,
            waiver_date=start,
            facility_tour_date=tour,
            custom_fields={'AccessSuspended': 'Yes'}
        )}
        setup_mocks['getAllUsers'].return_value = {
            9001: MockAltaUserBuilder().with_id(9001).build()
        }

        openPathUpdateAll.openPathUpdateAll(neon_accounts)

        # Should still update groups (has OpenPathID), but not create new access
        setup_mocks['updateGroups'].assert_called_once()
        setup_mocks['createUser'].assert_not_called()


