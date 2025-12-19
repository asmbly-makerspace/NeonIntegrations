import openPathUpdateSingle
from tests.neon_account_builder import build_member_with_facility_access, setup_neon_account_with_membership


def test_creates_user_when_has_facility_access(neon_api_mock, mocker):
    # Reality: any user with facility access should already have an Alta/OpenPath account.
    neon_id = 1001

    # Setup Neon API to return a member with facility access and existing OpenPathID
    build_member_with_facility_access(
        neon_api_mock,
        account_id=neon_id,
        membership_start='2020-01-01',
        membership_end='2025-12-31',
        fee=100.0,
        waiver_date='2020-01-01',
        facility_tour_date='2020-01-02',
        open_path_id=777
    )

    # Patch OpenPath interactions - because the account already has an OpenPathID
    update_groups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')

    openPathUpdateSingle.openPathUpdateSingle(str(neon_id))

    # With an existing OpenPathID we should call update_groups (not createUser)
    update_groups.assert_called_once()
    call_args = update_groups.call_args[0][0]
    assert call_args['Account ID'] == str(neon_id)
    assert call_args['OpenPathID'] == '777'


def test_does_not_create_user_for_expired_or_no_access(neon_api_mock, mocker):
    neon_id = 2002

    # Setup account with no valid membership
    setup_neon_account_with_membership(
        neon_api_mock,
        account_id=neon_id,
        first_name="Expired",
        last_name="User",
        memberships=[]  # No memberships
    )

    create_user = mocker.patch('openPathUpdateSingle.openPathUtil.createUser')
    update_groups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')
    create_mobile = mocker.patch('openPathUpdateSingle.openPathUtil.createMobileCredential')

    openPathUpdateSingle.openPathUpdateSingle(str(neon_id))

    # No OpenPathID and no facility access --> should NOT create or update OpenPath
    create_user.assert_not_called()
    update_groups.assert_not_called()
    create_mobile.assert_not_called()


def test_updates_existing_user_when_openpathid_present(neon_api_mock, mocker):
    neon_id = 3003

    # Setup member with valid membership, waiver, tour, and existing OpenPathID
    build_member_with_facility_access(
        neon_api_mock,
        account_id=neon_id,
        membership_start='2020-01-01',
        membership_end='2025-12-31',
        fee=100.0,
        waiver_date='2020-01-01',
        facility_tour_date='2020-01-02',
        open_path_id=777
    )

    update_groups = mocker.patch('openPathUpdateSingle.openPathUtil.updateGroups')

    openPathUpdateSingle.openPathUpdateSingle(str(neon_id))

    # Should call update_groups with the account returned from neonUtil.getMemberById
    update_groups.assert_called_once()
    call_args = update_groups.call_args[0][0]
    assert call_args['Account ID'] == str(neon_id)
    assert call_args['validMembership'] is True
