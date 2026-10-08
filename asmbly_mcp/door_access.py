###############################################################################
# Door access troubleshooter (READ ONLY - never changes Neon or Alta Open)
#
# Walks through every reason a member's door access might not work and
# reports a pass/fail checklist with a suggested fix for each failure.
#
# Usage from the command line (run from the repo root):
#   uv run --project asmbly_mcp python -m asmbly_mcp.door_access 1234
#   uv run --project asmbly_mcp python -m asmbly_mcp.door_access jane@example.com
#   uv run --project asmbly_mcp python -m asmbly_mcp.door_access "Jane Doe"
#
# The same functions back the MCP tools in tools.py
###############################################################################

import datetime
import logging
import sys

import pytz
import requests
import tenacity

import neonUtil
import openPathUtil

PASS = "pass"
FAIL = "fail"
WARN = "warn"
SKIP = "skip"

ICONS = {PASS: "✅", FAIL: "❌", WARN: "⚠️", SKIP: "➖"}

# Friendly names for the Alta Open groups we manage
GROUP_NAMES = {
    openPathUtil.GROUP_MANAGEMENT: "Management",
    openPathUtil.GROUP_SUBSCRIBERS: "Subscribers",
    openPathUtil.GROUP_CERAMICS: "Ceramics",
    openPathUtil.GROUP_COWORKING: "CoWorking",
    openPathUtil.GROUP_STEWARDS: "Stewards",
    openPathUtil.GROUP_INSTRUCTORS: "Instructors",
    openPathUtil.GROUP_SHAPER_ORIGIN: "Shaper Origin",
    openPathUtil.GROUP_DOMINO: "Domino",
    openPathUtil.GROUP_ONDUTY: "On Duty",
    openPathUtil.GROUP_CERAMICS_ONDUTY: "Ceramics On Duty",
    openPathUtil.GROUP_SPECIAL_EVENT: "Special Event",
}

# Alta Open user status codes
ALTA_STATUS = {"A": "Active", "I": "Inactive", "S": "Suspended", "P": "Pending"}

# Account types that get door access without meeting any of the member requirements.
# Keep in step with neonUtil.accountHasFacilityAccess() and openPathUtil.getOpGroups()
# (asmbly_mcp/tests/test_door_access.py fails if these drift apart).
EXEMPT_TYPES = (
    neonUtil.STAFF_TYPE,
    neonUtil.LEAD_TYPE,
    neonUtil.DIRECTOR_TYPE,
    neonUtil.SUPER_TYPE,
)
# CoWorking tenants keep access through a lapsed membership, but still need everything else
MEMBERSHIP_OPTIONAL_TYPES = EXEMPT_TYPES + (neonUtil.COWORKING_TYPE,)

SEARCH_OUTPUT_FIELDS = [
    "Account ID",
    "First Name",
    "Last Name",
    "Preferred Name",
    "Email 1",
    "Account Current Membership Status",
    "Membership Expiration Date",
]
MAX_SEARCH_RESULTS = 25


def _refreshToday():
    # neonUtil computes "today" once at import time. A long-running MCP server
    # would otherwise judge memberships against the day it started.
    neonUtil.today = datetime.datetime.now(pytz.timezone("America/Chicago")).date()
    neonUtil.yesterday = neonUtil.today - datetime.timedelta(days=1)


def _groupName(groupId):
    return GROUP_NAMES.get(groupId, f"group {groupId}")


def _typesIn(account, wanted):
    return [t.get("name") for t in account.get("individualTypes") or [] if t.get("name") in wanted]


def _check(name, status, detail, fix=None):
    return {"check": name, "status": status, "detail": detail, "fix": fix}


def _explainHttpError(err):
    # neonUtil retries searches; report the underlying error, not the retry wrapper
    if isinstance(err, tenacity.RetryError):
        err = err.last_attempt.exception()
    text = str(err)
    if isinstance(err, requests.ConnectionError):
        return f"couldn't connect ({text}). Check your internet connection."
    if "status code 401" in text or "status code 403" in text:
        return f"{text} (the API key or user in config.py is probably wrong or lacks permission)"
    return text


####################################################################
# Find Neon accounts by account ID, email, or name
####################################################################
def findMembers(query: str):
    query = (query or "").strip()
    if not query:
        return []

    if query.isdigit():
        searchFields = [{"field": "Account ID", "operator": "EQUAL", "value": query}]
    elif "@" in query:
        searchFields = [{"field": "Email", "operator": "EQUAL", "value": query}]
    else:
        names = query.split()
        if len(names) >= 2:
            searchFields = [
                {"field": "First Name", "operator": "CONTAIN", "value": names[0]},
                {"field": "Last Name", "operator": "CONTAIN", "value": " ".join(names[1:])},
            ]
        else:
            searchFields = [{"field": "Last Name", "operator": "CONTAIN", "value": query}]

    data = {
        "searchFields": searchFields,
        "outputFields": SEARCH_OUTPUT_FIELDS,
        "pagination": {"currentPage": 0, "pageSize": MAX_SEARCH_RESULTS},
    }
    results = neonUtil._neon_search(data).json().get("searchResults") or []

    # A single word might be a first name rather than a last name
    if not results and not query.isdigit() and "@" not in query and len(query.split()) == 1:
        data["searchFields"] = [{"field": "First Name", "operator": "CONTAIN", "value": query}]
        results = neonUtil._neon_search(data).json().get("searchResults") or []

    return results


####################################################################
# Neon side: membership, suspension, waiver, orientation
####################################################################
def _neonChecks(account):
    checks = []
    exempt = " / ".join(_typesIn(account, EXEMPT_TYPES))
    membershipOptional = " / ".join(_typesIn(account, MEMBERSHIP_OPTIONAL_TYPES))

    # Membership paid and current (our definition, not just Neon's "Active" label)
    expiration = account.get("Membership Expiration Date")
    currentStatuses = [
        m.get("status")
        for m in account.get("MembershipDetails") or []
        if m.get("termStartDate", "9999") <= str(neonUtil.today) <= m.get("termEndDate", "0000")
    ]
    if account.get("validMembership"):
        level = "Ceramics" if account.get("ceramicsMembership") else "Regular"
        checks.append(_check(
            "Membership paid and current", PASS,
            f"{level} membership, paid through {expiration}"))
    else:
        if currentStatuses and all(s != "SUCCEEDED" for s in currentStatuses):
            detail = (f"There is a membership for today but its payment status is "
                      f"{', '.join(currentStatuses)} (not SUCCEEDED). Neon may still show 'Active'.")
            fix = "Payment failed or is pending. Have the member update their card / retry payment in Neon."
        elif expiration:
            detail = f"Last paid membership ended {expiration}."
            fix = "Membership has lapsed. Member needs to renew."
        else:
            detail = "No paid membership found in Neon."
            fix = "Member needs to purchase a membership."
        if membershipOptional:
            checks.append(_check(
                "Membership paid and current", SKIP,
                f"{detail} That's OK: a {membershipOptional} account doesn't need a paid membership."))
        else:
            checks.append(_check("Membership paid and current", FAIL, detail, fix))

    # Access suspended
    suspended = account.get("AccessSuspended")
    if suspended and exempt:
        checks.append(_check(
            "Access not suspended", WARN,
            f"AccessSuspended is set in Neon: \"{suspended}\", but the door sync ignores it "
            f"for a {exempt} account, so they still have access.",
            "If they really should be locked out, remove that account type in Neon "
            "or deactivate them in Alta Open."))
    elif suspended:
        checks.append(_check(
            "Access not suspended", FAIL,
            f"AccessSuspended is set in Neon: \"{suspended}\"",
            "Find out why it was suspended before clearing it (ask leadership). "
            "Clearing AccessSuspended in Neon restores access (saving the Neon account triggers a sync)."))
    else:
        checks.append(_check("Access not suspended", PASS, "AccessSuspended is blank"))

    # Waiver
    if account.get("WaiverDate"):
        checks.append(_check("Waiver signed", PASS, f"WaiverDate {account.get('WaiverDate')}"))
    elif exempt:
        checks.append(_check(
            "Waiver signed", SKIP, f"WaiverDate is blank. That's OK: not required for a {exempt} account."))
    else:
        checks.append(_check(
            "Waiver signed", FAIL, "WaiverDate is blank",
            "Member needs to sign the waiver (or staff needs to record the WaiverDate in Neon)."))

    # Orientation
    if account.get("FacilityTourDate"):
        checks.append(_check(
            "Orientation completed", PASS, f"FacilityTourDate {account.get('FacilityTourDate')}"))
    elif exempt:
        checks.append(_check(
            "Orientation completed", SKIP,
            f"FacilityTourDate is blank. That's OK: not required for a {exempt} account."))
    else:
        checks.append(_check(
            "Orientation completed", FAIL, "FacilityTourDate is blank",
            "Member needs to take the orientation class. If they took it in the last few hours, "
            "wait: attendance is copied to Neon every 3 hours. If it's been longer, check that the "
            "instructor marked them attended in Neon."))

    return checks


####################################################################
# Alta Open side: user exists, active, right groups, has credential
####################################################################
def _altaChecks(account, shouldHaveAccess, expectedGroups):
    checks = []
    opId = account.get("OpenPathID")

    if not opId:
        if expectedGroups:
            checks.append(_check(
                "Alta Open account exists", FAIL,
                "Neon says this person should have access, but there is no OpenPathID in Neon.",
                f"Run `uv run openPathUpdateSingle.py {account.get('Account ID')}` "
                "or wait for the nightly sync to create it. Saving their Neon account also triggers a sync."))
        else:
            checks.append(_check(
                "Alta Open account exists", SKIP,
                "No Alta Open account. That's expected until the Neon checks above pass."))
        return checks

    # User record
    try:
        user = openPathUtil.getUser(opId) or {}
        status = user.get("status")
        statusName = ALTA_STATUS.get(status, status or "unknown")
        if status == "A":
            checks.append(_check("Alta Open account active", PASS, f"Alta Open user {opId} is {statusName}"))
        else:
            checks.append(_check(
                "Alta Open account active", FAIL if expectedGroups else WARN,
                f"Alta Open user {opId} is {statusName}",
                "Reactivate the user in the Alta Open dashboard, then re-run the sync."))
    except Exception as err:
        checks.append(_check(
            "Alta Open account active", FAIL,
            f"Could not load Alta Open user {opId}: {_explainHttpError(err)}",
            "The OpenPathID in Neon may point at a deleted Alta Open user. "
            "Clear OpenPathID in Neon and run the sync to recreate it."))
        return checks

    # Groups
    try:
        actualGroups = {g.get("id"): g.get("name") for g in openPathUtil.getGroupsById(opId) or []}
        expected = set(expectedGroups)
        actual = set(actualGroups)
        missing = expected - actual
        extra = {g for g in actual - expected if openPathUtil.isManagedGroup(g)}
        actualNames = ", ".join(actualGroups[g] or _groupName(g) for g in sorted(actual)) or "none"

        if missing:
            checks.append(_check(
                "Alta Open groups correct", FAIL,
                f"Has: {actualNames}. Missing: {', '.join(_groupName(g) for g in sorted(missing))}.",
                f"Run `uv run openPathUpdateSingle.py {account.get('Account ID')}` "
                "or wait for the nightly sync. Saving their Neon account also triggers a sync."))
        elif extra:
            checks.append(_check(
                "Alta Open groups correct", WARN,
                f"Still in {', '.join(_groupName(g) for g in sorted(extra))}, "
                "but Neon says they shouldn't be.",
                "The next sync will remove them. That's expected if the Neon checks above fail."))
        else:
            checks.append(_check("Alta Open groups correct", PASS, f"Has: {actualNames}"))
    except Exception as err:
        checks.append(_check("Alta Open groups correct", FAIL,
                             f"Could not load groups: {_explainHttpError(err)}"))

    # Credentials
    try:
        creds = openPathUtil.getCredentialsForId(opId) or []
        if creds:
            names = ", ".join(
                (c.get("mobile") or {}).get("name")
                or (c.get("card") or {}).get("number")
                or (c.get("credentialType") or {}).get("name")
                or f"credential {c.get('id')}"
                for c in creds
            )
            checks.append(_check("Has a door credential", PASS, f"{len(creds)} credential(s): {names}"))
        else:
            checks.append(_check(
                "Has a door credential", FAIL if shouldHaveAccess else WARN,
                "No credentials (no mobile credential or key card).",
                "Create a mobile credential in the Alta Open dashboard (or assign a key card), "
                "then have the member log in to the Avigilon Alta app."))
    except Exception as err:
        checks.append(_check("Has a door credential", FAIL,
                             f"Could not load credentials: {_explainHttpError(err)}"))

    return checks


####################################################################
# Run every check for one Neon account ID
####################################################################
def diagnose(neonId):
    _refreshToday()
    account = neonUtil.getMemberById(int(neonId), detailed=True)

    checks = _neonChecks(account)
    expectedGroups = openPathUtil.getOpGroups(account)
    # What the real sync would grant: general access, or the 24x7 Management group
    shouldHaveAccess = (neonUtil.accountHasFacilityAccess(account)
                        or openPathUtil.GROUP_MANAGEMENT in expectedGroups)
    types = [t.get("name") for t in account.get("individualTypes") or []]

    checks.extend(_altaChecks(account, shouldHaveAccess, expectedGroups))

    problems = [c for c in checks if c["status"] == FAIL]
    warnings = [c for c in checks if c["status"] == WARN]
    if problems:
        verdict = "Problem found: " + "; ".join(c["check"] for c in problems)
        if not shouldHaveAccess and any(c["check"] == "Alta Open groups correct" for c in warnings):
            verdict += (". Note: Alta Open still has them in access groups, so the door may keep "
                        "working until the next sync removes them.")
    elif warnings:
        verdict = "Should work, but take a look at the warnings."
    else:
        verdict = ("Everything checks out. If the door still won't open, it's likely the phone/app "
                   "(Bluetooth, location permission, logged in to the Avigilon Alta app) or the reader itself.")

    return {
        "neonId": account.get("Account ID"),
        "name": account.get("fullName"),
        "email": account.get("Email 1"),
        "accountTypes": types,
        "openPathId": account.get("OpenPathID"),
        "shouldHaveDoorAccess": shouldHaveAccess,
        "expectedAltaGroups": [_groupName(g) for g in sorted(expectedGroups)],
        "checks": checks,
        "verdict": verdict,
    }


####################################################################
# Turn a diagnose() result into a readable checklist
####################################################################
def formatReport(result):
    lines = [
        f"Door access check: {result['name']} (Neon #{result['neonId']}, {result['email']})",
        f"Account type: {', '.join(result['accountTypes']) or 'regular member (no special type)'}",
        "",
    ]
    for c in result["checks"]:
        lines.append(f"{ICONS[c['status']]} {c['check']}: {c['detail']}")
        if c["fix"] and c["status"] in (FAIL, WARN):
            lines.append(f"     → Fix: {c['fix']}")
    lines += ["", f"Verdict: {result['verdict']}"]
    return "\n".join(lines)


def formatMatches(matches):
    lines = []
    for m in matches:
        lines.append(
            f"- Neon #{m.get('Account ID')}: {m.get('First Name')} {m.get('Last Name')} "
            f"<{m.get('Email 1')}> (membership: {m.get('Account Current Membership Status') or 'none'}, "
            f"expires {m.get('Membership Expiration Date') or 'n/a'})"
        )
    return "\n".join(lines)


####################################################################
# Look someone up and check them, or explain why we couldn't
####################################################################
def checkMember(query: str):
    try:
        matches = findMembers(query)
    except (ValueError, requests.RequestException, tenacity.RetryError) as err:
        return f"Couldn't search Neon: {_explainHttpError(err)}"

    if not matches:
        return f"No Neon account found for \"{query}\". Try an email address or the Neon account ID."
    if len(matches) > 1:
        return (f"Found {len(matches)} Neon accounts matching \"{query}\". "
                f"Which one?\n{formatMatches(matches)}")

    try:
        return formatReport(diagnose(matches[0]["Account ID"]))
    except (ValueError, requests.RequestException, tenacity.RetryError) as err:
        return f"Couldn't finish the check: {_explainHttpError(err)}"


def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print('Usage: python -m asmbly_mcp.door_access <Neon ID | email | "First Last">')
        sys.exit(1)
    print(checkMember(" ".join(sys.argv[1:])))


if __name__ == "__main__":
    main()
