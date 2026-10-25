import logging

import pytest

from neonUtil import (
    accountHasFacilityAccess,
    STAFF_TYPE, DIRECTOR_TYPE, LEAD_TYPE, SUPER_TYPE, COWORKING_TYPE, STEWARD_TYPE,
    INSTRUCTOR_TYPE, WIKI_ADMIN_TYPE, ONDUTY_TYPE, ONDUTY_TYPE_CERAMICS,
)


def makeAccount(types=None, member=False, waiver=False, tour=False, suspended=False):
    """Build a Neon account dict with only the fields facility access reads.

    types: list of Individual Type names, or None to leave "individualTypes"
        out, as Neon does for accounts with no type.
    member: value for "validMembership", or None to leave the key out.
    waiver, tour, suspended: whether to set WaiverDate, FacilityTourDate and
        AccessSuspended. Unset fields are left out, as Neon does.

    Returns the account dict. Raises nothing.
    """
    account = {"fullName": "Test Account"}
    if types is not None:
        account["individualTypes"] = [{"name": individualType} for individualType in types]
    if member is not None:
        account["validMembership"] = member
    if waiver:
        account["WaiverDate"] = "2025-01-01"
    if tour:
        account["FacilityTourDate"] = "2025-01-02"
    if suspended:
        account["AccessSuspended"] = "Yes"
    return account


def currentFacilityAccessRule(account):
    """An independent restatement of today's accountHasFacilityAccess rule.

    Kept here so any change to accountHasFacilityAccess can be checked against
    the behavior it has today.
    account: a Neon account dict, as built by makeAccount. Missing keys are
        treated the same way the real code treats them.

    Returns True if today's rule allows facility access. Raises nothing.
    """
    individualTypes = {entry["name"] for entry in account.get("individualTypes") or []}
    hasWaiverTourAndNotSuspended = (
        account.get("WaiverDate")
        and account.get("FacilityTourDate")
        and not account.get("AccessSuspended")
    )
    return bool(
        STAFF_TYPE in individualTypes
        or LEAD_TYPE in individualTypes
        or (account.get("validMembership") == True and hasWaiverTourAndNotSuspended)
        or (COWORKING_TYPE in individualTypes and hasWaiverTourAndNotSuspended)
    )


SINGLE_TYPES = [
    STAFF_TYPE, DIRECTOR_TYPE, LEAD_TYPE, SUPER_TYPE, COWORKING_TYPE, STEWARD_TYPE,
    INSTRUCTOR_TYPE, WIKI_ADMIN_TYPE, ONDUTY_TYPE, ONDUTY_TYPE_CERAMICS,
]
# no type at all, each type alone, and the pairs where the order of the checks matters
INDIVIDUAL_TYPE_COMBINATIONS = (
    [None]
    + [[individualType] for individualType in SINGLE_TYPES]
    + [[STAFF_TYPE, COWORKING_TYPE], [LEAD_TYPE, COWORKING_TYPE]]
)


@pytest.mark.parametrize("types", INDIVIDUAL_TYPE_COMBINATIONS)
@pytest.mark.parametrize("member", [True, False, None])
@pytest.mark.parametrize("waiver", [True, False])
@pytest.mark.parametrize("tour", [True, False])
@pytest.mark.parametrize("suspended", [True, False])
def test_matches_current_rule(types, member, waiver, tour, suspended):
    """accountHasFacilityAccess gives the same answer as today's rule.

    Runs once for every combination of type, membership and requirement fields.
    Fails with AssertionError on the first combination where they disagree.
    """
    account = makeAccount(types, member, waiver, tour, suspended)
    assert accountHasFacilityAccess(account) == currentFacilityAccessRule(account)


@pytest.mark.parametrize("account, allowed, warned", [
    pytest.param(makeAccount([STAFF_TYPE], suspended=True), True, False,
                 id="suspended staff keep access"),
    pytest.param(makeAccount([LEAD_TYPE], suspended=True), True, False,
                 id="suspended space lead keeps access"),
    pytest.param(makeAccount([DIRECTOR_TYPE], waiver=True, tour=True), False, False,
                 id="leader without membership is denied"),
    pytest.param(makeAccount([SUPER_TYPE], waiver=True, tour=True), False, False,
                 id="super steward without membership is denied"),
    pytest.param(makeAccount([COWORKING_TYPE], waiver=True, tour=True), True, True,
                 id="coworking with lapsed membership gets in with a warning"),
    pytest.param(makeAccount([COWORKING_TYPE], member=True, waiver=True, tour=True), True, False,
                 id="coworking with membership gets in without a warning"),
    pytest.param(makeAccount([STAFF_TYPE, COWORKING_TYPE], waiver=True, tour=True), True, False,
                 id="staff and coworking gets in without a warning"),
    pytest.param(makeAccount([COWORKING_TYPE], member=True, tour=True), False, False,
                 id="coworking without waiver is denied"),
])
def test_documented_exceptions(account, allowed, warned, caplog):
    """Specific cases where facility access departs from "member with waiver and tour".

    These are the behaviors most likely to be changed by accident when the
    rule is edited. Each case gives an account, whether it should get
    facility access, and whether the lapsed-CoWorking warning should be logged.
    Fails with AssertionError if either differs.
    """
    with caplog.at_level(logging.WARNING):
        assert accountHasFacilityAccess(account) == allowed
    assert ("despite a lapsed membership" in caplog.text) == warned
