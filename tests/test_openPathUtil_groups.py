"""
Characterization tests for the door-access rules:
  openPathUtil.getOpGroups           which Alta (OpenPath) groups a Neon account earns
  neonUtil.accountHasFacilityAccess  whether the account counts as having facility access
  openPathUtil.updateGroups          how Alta is brought in line, including revocation

These tests pin down what the code does TODAY so that a refactor or a rule
change that alters who can open which doors fails CI instead of passing
silently. They are not a statement of policy.

POLICY QUESTIONS
Some rows pin behaviour the owners have not confirmed. Each such row carries
one of these tags so they can be found and flipped together once a decision
is made (change the expected value in the same PR as the code):

  [suspension]  AccessSuspended (Neon field 180) does not remove groups that
                come from an Individual Type (Paid Staff, Leader, Space Lead,
                Super Steward, Instructor, Volunteer, Ceramics Volunteer).
                NEON_USER_TYPES_GUIDE.md lines 30, 65 and 330 say the flag
                overrides the type; the code does not do that.
  [coworking]   A CoWorking Tenant whose membership has lapsed keeps
                SUBSCRIBERS and COWORKING (plus STEWARDS and tool groups where
                they apply) while waiver and tour are on file. The code comment
                in neonUtil.accountHasFacilityAccess says this is intended; the
                guide (line 128) says SUBSCRIBERS needs a valid membership.
  [leadership]  Leader and Super Steward get MANAGEMENT, but unlike Space Lead
                the type alone does not count as facility access. Without a
                valid membership they get MANAGEMENT only (no SUBSCRIBERS or
                tool groups), and openPathUpdateSingle/openPathUpdateAll do not
                create an Alta user for them. The guide (lines 52-57 and
                102-107) says they need no membership.

A suspended Leader or Super Steward row carries both [suspension] and
[leadership], because either decision could change it.
"""
import pytest

import neonUtil
import openPathUtil
from neonUtil import (
    STAFF_TYPE, DIRECTOR_TYPE, LEAD_TYPE, SUPER_TYPE, COWORKING_TYPE, STEWARD_TYPE,
    INSTRUCTOR_TYPE, WIKI_ADMIN_TYPE, ONDUTY_TYPE, ONDUTY_TYPE_CERAMICS,
    MEMBERSHIP_ID_REGULAR as REGULAR,
)
from openPathUtil import (
    GROUP_MANAGEMENT as MANAGEMENT,
    GROUP_SUBSCRIBERS as SUBSCRIBERS,
    GROUP_CERAMICS as CERAMICS,
    GROUP_COWORKING as COWORKING,
    GROUP_STEWARDS as STEWARDS,
    GROUP_INSTRUCTORS as INSTRUCTORS,
    GROUP_SHAPER_ORIGIN as SHAPER_ORIGIN,
    GROUP_DOMINO as DOMINO,
    GROUP_ONDUTY as ONDUTY,
    GROUP_CERAMICS_ONDUTY as CERAMICS_ONDUTY,
    GROUP_SPECIAL_EVENT as SPECIAL_EVENT,
    O_baseURL,
)
from openPathUpdateAll import openPathUpdateAll
from openPathUpdateSingle import openPathUpdateSingle
from neon_mocker import NeonUserMock, today_plus


# The code only checks that these fields are non-empty, so any date will do
DATE = "2025-01-01"
SHAPER_SIGNOFF = {"Shaper Origin": DATE}
DOMINO_SIGNOFF = {"Woodshop Specialty Tools": DATE}

# A hand-assigned Alta group the sync does not manage
UNMANAGED_GROUP = 999999

# Every group getOpGroups can hand out (and so updateGroups can take away)
MANAGED_GROUPS = [
    MANAGEMENT, SUBSCRIBERS, CERAMICS, COWORKING, STEWARDS, INSTRUCTORS,
    SHAPER_ORIGIN, DOMINO, ONDUTY, CERAMICS_ONDUTY,
]

# What getOpGroups gives a Paid Staff account
STAFF_GROUPS = [SUBSCRIBERS, STEWARDS, INSTRUCTORS, COWORKING, CERAMICS]


def account(*types, member=True, waiver=True, tour=True, suspended=False, **fields):
    """Build a Neon account dict in the shape getMemberById()/getRealAccounts() return:
    custom fields raised to top-level keys, Individual Types as [{"name": ...}], and
    validMembership/ceramicsMembership as set by appendMemberships()."""
    acct = {
        "Account ID": "1234",
        "fullName": "Pat Example",
        "Email 1": "pat@example.com",
        "validMembership": member,
    }
    if types:
        acct["individualTypes"] = [{"name": t} for t in types]
    if waiver:
        acct["WaiverDate"] = DATE
    if tour:
        acct["FacilityTourDate"] = DATE
    if suspended:
        acct["AccessSuspended"] = "Yes"
    acct.update(fields)
    return acct


def row(id, acct, groups, facility):
    return pytest.param(acct, groups, facility, id=id)


# Each row: account, expected getOpGroups (any order), expected accountHasFacilityAccess.
# "non-member" means validMembership is False but waiver and tour are on file.
ACCESS_TABLE = [
    # --- No Individual Type: needs valid membership + waiver + tour, and not suspended ---
    row("member", account(), [SUBSCRIBERS], True),
    row("member-lapsed", account(member=False), [], False),
    row("member-no-waiver", account(waiver=False), [], False),
    row("member-no-tour", account(tour=False), [], False),
    row("member-suspended", account(suspended=True), [], False),

    # --- Ceramics: needs a ceramics membership AND a CSI date on top of facility access ---
    row("ceramics-member-with-csi",
        account(ceramicsMembership=True, CsiDate=DATE), [SUBSCRIBERS, CERAMICS], True),
    row("ceramics-member-no-csi", account(ceramicsMembership=True), [SUBSCRIBERS], True),
    row("regular-member-with-csi", account(CsiDate=DATE), [SUBSCRIBERS], True),
    row("ceramics-member-with-csi-suspended",
        account(ceramicsMembership=True, CsiDate=DATE, suspended=True), [], False),
    row("ceramics-member-with-csi-no-waiver",
        account(ceramicsMembership=True, CsiDate=DATE, waiver=False), [], False),

    # --- Tool sign-offs: only granted on top of facility access ---
    row("member-shaper", account(**SHAPER_SIGNOFF), [SUBSCRIBERS, SHAPER_ORIGIN], True),
    row("member-domino", account(**DOMINO_SIGNOFF), [SUBSCRIBERS, DOMINO], True),
    row("member-lapsed-shaper-domino",
        account(member=False, **SHAPER_SIGNOFF, **DOMINO_SIGNOFF), [], False),
    row("member-suspended-shaper-domino",
        account(suspended=True, **SHAPER_SIGNOFF, **DOMINO_SIGNOFF), [], False),

    # --- Paid Staff: membership, waiver and tour are not checked ---
    row("staff-member", account(STAFF_TYPE), STAFF_GROUPS, True),
    row("staff-non-member", account(STAFF_TYPE, member=False), STAFF_GROUPS, True),
    row("staff-non-member-no-waiver-no-tour",
        account(STAFF_TYPE, member=False, waiver=False, tour=False), STAFF_GROUPS, True),
    # [suspension]
    row("staff-suspended", account(STAFF_TYPE, suspended=True), STAFF_GROUPS, True),

    # --- Leader: MANAGEMENT (24x7) from the type; SUBSCRIBERS only via membership ---
    row("leader-member", account(DIRECTOR_TYPE), [SUBSCRIBERS, MANAGEMENT], True),
    # [leadership]
    row("leader-non-member", account(DIRECTOR_TYPE, member=False), [MANAGEMENT], False),
    # [leadership]
    row("leader-non-member-shaper-domino",
        account(DIRECTOR_TYPE, member=False, **SHAPER_SIGNOFF, **DOMINO_SIGNOFF),
        [MANAGEMENT], False),
    # [suspension] [leadership]
    row("leader-suspended", account(DIRECTOR_TYPE, suspended=True), [MANAGEMENT], False),

    # --- Space Lead: MANAGEMENT, and facility access without membership, waiver or tour ---
    row("space-lead-member", account(LEAD_TYPE), [SUBSCRIBERS, MANAGEMENT], True),
    row("space-lead-non-member",
        account(LEAD_TYPE, member=False), [SUBSCRIBERS, MANAGEMENT], True),
    row("space-lead-non-member-no-waiver-no-tour",
        account(LEAD_TYPE, member=False, waiver=False, tour=False),
        [SUBSCRIBERS, MANAGEMENT], True),
    row("space-lead-non-member-shaper",
        account(LEAD_TYPE, member=False, **SHAPER_SIGNOFF),
        [SUBSCRIBERS, MANAGEMENT, SHAPER_ORIGIN], True),
    # [suspension]
    row("space-lead-suspended",
        account(LEAD_TYPE, suspended=True), [SUBSCRIBERS, MANAGEMENT], True),

    # --- Super Steward: same as Leader ---
    row("super-steward-member", account(SUPER_TYPE), [SUBSCRIBERS, MANAGEMENT], True),
    # [leadership]
    row("super-steward-non-member", account(SUPER_TYPE, member=False), [MANAGEMENT], False),
    # [suspension] [leadership]
    row("super-steward-suspended", account(SUPER_TYPE, suspended=True), [MANAGEMENT], False),

    # --- Steward: STEWARDS only on top of normal member facility access ---
    row("steward-member", account(STEWARD_TYPE), [SUBSCRIBERS, STEWARDS], True),
    row("steward-member-shaper-domino",
        account(STEWARD_TYPE, **SHAPER_SIGNOFF, **DOMINO_SIGNOFF),
        [SUBSCRIBERS, STEWARDS, SHAPER_ORIGIN, DOMINO], True),
    row("steward-non-member", account(STEWARD_TYPE, member=False), [], False),
    row("steward-suspended", account(STEWARD_TYPE, suspended=True), [], False),

    # --- Instructor: instructor storage even without membership ---
    row("instructor-member", account(INSTRUCTOR_TYPE), [SUBSCRIBERS, INSTRUCTORS], True),
    row("instructor-non-member", account(INSTRUCTOR_TYPE, member=False), [INSTRUCTORS], False),
    # [suspension]
    row("instructor-suspended",
        account(INSTRUCTOR_TYPE, suspended=True), [INSTRUCTORS], False),

    # --- Volunteer (on-duty): clock in/out buttons even without membership ---
    row("volunteer-member", account(ONDUTY_TYPE), [SUBSCRIBERS, ONDUTY], True),
    row("volunteer-non-member", account(ONDUTY_TYPE, member=False), [ONDUTY], False),
    # [suspension]
    row("volunteer-suspended", account(ONDUTY_TYPE, suspended=True), [ONDUTY], False),

    # --- Ceramics Volunteer: interior ceramics door even without membership ---
    row("ceramics-volunteer-member",
        account(ONDUTY_TYPE_CERAMICS), [SUBSCRIBERS, CERAMICS_ONDUTY], True),
    row("ceramics-volunteer-non-member",
        account(ONDUTY_TYPE_CERAMICS, member=False), [CERAMICS_ONDUTY], False),
    # [suspension]
    row("ceramics-volunteer-suspended",
        account(ONDUTY_TYPE_CERAMICS, suspended=True), [CERAMICS_ONDUTY], False),

    # --- CoWorking Tenant: may ride out a lapsed membership, but needs waiver + tour ---
    row("coworking-member", account(COWORKING_TYPE), [SUBSCRIBERS, COWORKING], True),
    # [coworking]
    row("coworking-lapsed",
        account(COWORKING_TYPE, member=False), [SUBSCRIBERS, COWORKING], True),
    # [coworking]
    row("coworking-steward-lapsed-shaper",
        account(COWORKING_TYPE, STEWARD_TYPE, member=False, **SHAPER_SIGNOFF),
        [SUBSCRIBERS, COWORKING, STEWARDS, SHAPER_ORIGIN], True),
    row("coworking-lapsed-no-waiver",
        account(COWORKING_TYPE, member=False, waiver=False), [], False),
    row("coworking-lapsed-no-tour",
        account(COWORKING_TYPE, member=False, tour=False), [], False),
    row("coworking-lapsed-suspended",
        account(COWORKING_TYPE, member=False, suspended=True), [], False),
    row("coworking-member-suspended",
        account(COWORKING_TYPE, suspended=True), [], False),

    # --- Types that grant nothing by themselves ---
    row("wiki-admin-member", account(WIKI_ADMIN_TYPE), [SUBSCRIBERS], True),
    row("wiki-admin-non-member", account(WIKI_ADMIN_TYPE, member=False), [], False),

    # --- Combinations ---
    # Paid Staff who is also a Leader gets MANAGEMENT *instead of* the staff bundle
    # (the staff branch in getOpGroups is an `elif`), plus SUBSCRIBERS via the staff type.
    row("staff-and-leader",
        account(STAFF_TYPE, DIRECTOR_TYPE, member=False), [SUBSCRIBERS, MANAGEMENT], True),
    row("instructor-and-volunteer-non-member",
        account(INSTRUCTOR_TYPE, ONDUTY_TYPE, member=False), [INSTRUCTORS, ONDUTY], False),
]


@pytest.mark.parametrize("acct, expected_groups, expected_facility", ACCESS_TABLE)
def test_getOpGroups(acct, expected_groups, expected_facility):
    # getOpGroups builds a set, so order is not meaningful; sorting also catches duplicates
    assert sorted(openPathUtil.getOpGroups(acct)) == sorted(expected_groups)


@pytest.mark.parametrize("acct, expected_groups, expected_facility", ACCESS_TABLE)
def test_accountHasFacilityAccess(acct, expected_groups, expected_facility):
    assert neonUtil.accountHasFacilityAccess(acct) is expected_facility


@pytest.mark.parametrize("group", MANAGED_GROUPS)
def test_isManagedGroup_true_for_groups_the_sync_assigns(group):
    assert openPathUtil.isManagedGroup(group)


@pytest.mark.parametrize("group", [SPECIAL_EVENT, UNMANAGED_GROUP])
def test_isManagedGroup_false_for_other_groups(group):
    assert not openPathUtil.isManagedGroup(group)


def test_every_group_getOpGroups_assigns_is_managed():
    # updateGroups only removes groups that isManagedGroup() knows about and keeps
    # everything else as hand-assigned. A group added to getOpGroups but not to
    # isManagedGroup could be granted by the sync but never revoked.
    assigned = set()
    for param in ACCESS_TABLE:
        assigned.update(openPathUtil.getOpGroups(param.values[0]))
    assert [g for g in sorted(assigned) if not openPathUtil.isManagedGroup(g)] == []
    # ...and the table above exercises every one of them
    assert assigned == set(MANAGED_GROUPS)


###############################################################################
# updateGroups: starting from groups the account already has in Alta
###############################################################################

OP_ID = 456
PUT_URL = f"{O_baseURL}/users/{OP_ID}/groupIds"


def alta_groups(*ids):
    """Group list in the shape Alta returns it (GET /users and GET /users/{id}/groups)."""
    return [{"id": i} for i in ids]


def test_updateGroups_revokes_all_managed_groups_from_lapsed_member(requests_mock):
    acct = account(member=False, OpenPathID=OP_ID, **SHAPER_SIGNOFF)
    put = requests_mock.put(PUT_URL, status_code=204)

    openPathUtil.updateGroups(acct, openPathGroups=alta_groups(SUBSCRIBERS, SHAPER_ORIGIN))

    assert put.call_count == 1
    assert put.last_request.json() == {"groupIds": []}


def test_updateGroups_revokes_only_groups_no_longer_earned(requests_mock):
    # e.g. the Steward type was removed in Neon, membership still valid
    acct = account(OpenPathID=OP_ID)
    put = requests_mock.put(PUT_URL, status_code=204)

    openPathUtil.updateGroups(acct, openPathGroups=alta_groups(SUBSCRIBERS, STEWARDS))

    assert put.call_count == 1
    assert put.last_request.json() == {"groupIds": [SUBSCRIBERS]}


def test_updateGroups_suspended_member_keeps_special_event_group(requests_mock):
    acct = account(suspended=True, OpenPathID=OP_ID)
    put = requests_mock.put(PUT_URL, status_code=204)

    openPathUtil.updateGroups(acct, openPathGroups=alta_groups(SUBSCRIBERS, SPECIAL_EVENT))

    assert put.call_count == 1
    assert put.last_request.json() == {"groupIds": [SPECIAL_EVENT]}


def test_updateGroups_lapsed_member_keeps_unmanaged_groups(requests_mock):
    acct = account(member=False, OpenPathID=OP_ID)
    put = requests_mock.put(PUT_URL, status_code=204)

    openPathUtil.updateGroups(
        acct, openPathGroups=alta_groups(SUBSCRIBERS, UNMANAGED_GROUP, SPECIAL_EVENT))

    assert put.call_count == 1
    assert sorted(put.last_request.json()["groupIds"]) == sorted([UNMANAGED_GROUP, SPECIAL_EVENT])


def test_updateGroups_grant_keeps_unmanaged_groups(requests_mock):
    acct = account(ceramicsMembership=True, CsiDate=DATE, OpenPathID=OP_ID)
    put = requests_mock.put(PUT_URL, status_code=204)

    openPathUtil.updateGroups(acct, openPathGroups=alta_groups(UNMANAGED_GROUP))

    assert put.call_count == 1
    assert sorted(put.last_request.json()["groupIds"]) == sorted(
        [SUBSCRIBERS, CERAMICS, UNMANAGED_GROUP])


def test_updateGroups_no_request_when_groups_already_match(requests_mock):
    acct = account(OpenPathID=OP_ID)

    openPathUtil.updateGroups(
        acct, openPathGroups=alta_groups(SPECIAL_EVENT, SUBSCRIBERS, UNMANAGED_GROUP))

    assert requests_mock.call_count == 0


###############################################################################
# Revocation through the two production entry points
###############################################################################

start = today_plus(-395)
lapsed_end = today_plus(-30)
end = today_plus(365)


def test_openPathUpdateSingle_revokes_lapsed_member(requests_mock):
    # Lambda path: groups are fetched from Alta, then the account is set to what it earns
    rm = requests_mock
    member = NeonUserMock(waiver_date=start, facility_tour_date=start, open_path_id=OP_ID)\
        .add_membership(REGULAR, start, lapsed_end, fee=100.0)
    member.mock(rm)
    get_groups = rm.get(f"{O_baseURL}/users/{OP_ID}/groups",
                        json={"data": alta_groups(SUBSCRIBERS)})
    put = rm.put(PUT_URL, status_code=204)

    openPathUpdateSingle(member.account_id)

    assert put.call_count == 1
    assert put.last_request.json() == {"groupIds": []}
    # requests_mock answers unauthenticated calls too; in production a missing
    # Authorization header means the lookup fails and nothing is revoked
    assert get_groups.last_request.headers["Authorization"].startswith("Basic ")
    assert put.last_request.headers["Authorization"].startswith("Basic ")


def test_openPathUpdateAll_revokes_suspended_member_keeps_special_event(requests_mock):
    # daily path: current groups come from the bulk GET /users listing
    rm = requests_mock
    member = NeonUserMock(1, waiver_date=start, facility_tour_date=start, open_path_id=OP_ID,
                          access_suspended=True)\
        .add_membership(REGULAR, start, end, fee=100.0)
    accounts = {member.account_id: member.mock(rm)}
    rm.get(f"{O_baseURL}/users", json={
        "data": [{"id": OP_ID, "groups": alta_groups(SUBSCRIBERS, SPECIAL_EVENT)}],
        "totalCount": 1,
    })
    put = rm.put(PUT_URL, status_code=204)

    openPathUpdateAll(accounts)

    assert put.call_count == 1
    assert put.last_request.json() == {"groupIds": [SPECIAL_EVENT]}
