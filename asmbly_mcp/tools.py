###############################################################################
# The tools Claude can call. Shared by the local server (local.py) and the
# hosted server on AWS (hosted.py).
#
# Everything here is READ ONLY: it looks things up in Neon and Alta Open but
# never changes them. Keep it that way unless a tool is clearly named as a write.
###############################################################################

import logging
import re

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

# -----------------------------------------------------------------------------
# WHAT MAY GO IN THE LOGS
#
# When hosted, everything logged is kept in CloudWatch for 90 days. No personal
# details go there: no names, emails, phone numbers, nothing a person typed, and
# no report contents. People are identified by ID number only.
#
# That includes error messages. Neon's error text can quote back the name or
# email that was searched for, so log the kind of error, never its message.
# -----------------------------------------------------------------------------
log = logging.getLogger("asmbly_mcp")

# Audit trail: one line per lookup saying who looked, with which tool, and which Neon
# account numbers they were shown. The hosted server turns this on (hosted.py).
AUDIT_LOGGER = "asmbly_mcp.audit"


def _audit(tool: str, neonIds: list):
    logging.getLogger(AUDIT_LOGGER).info(
        "AUDIT tool=%s by=%s neon_accounts=%s", tool, _caller(), ",".join(neonIds) or "none")


def _errorKind(err: Exception) -> str:
    # e.g. "ValueError (status 401)". The status code is safe; the rest of the message isn't.
    status = re.search(r"status code (\d{3})", str(err))
    return type(err).__name__ + (f" (status {status.group(1)})" if status else "")


INSTRUCTIONS = (
    "Tools for Asmbly Makerspace staff and volunteers. "
    "Use check_door_access when someone can't get in the door."
)


def _caller():
    # Who is asking, as an ID. Never their name or email: this goes in the audit log.
    # Only known when hosted and signed in; local use has no sign-in.
    #
    # "sub" is the ID every sign-in system provides. When sign-in is built, switch this
    # to the person's Neon account number, so an audit line can be traced in Neon.
    try:
        token = get_access_token()
    except Exception:
        return "local"
    if token is None:
        return "local"
    return str(token.claims.get("sub") or "unknown")


def buildServer(auth=None) -> FastMCP:
    # Imported here, not at the top: door_access pulls in neonUtil, which reads the
    # API keys the moment it's imported. When hosted, the keys have to be loaded first.
    from asmbly_mcp import door_access

    mcp = FastMCP("asmbly", instructions=INSTRUCTIONS, auth=auth)

    @mcp.tool
    def check_door_access(member: str) -> str:
        """Troubleshoot why an Asmbly member can't get in the door.

        Checks, in order: Neon membership is paid and current, AccessSuspended is
        not set, WaiverDate is set, FacilityTourDate (orientation) is set, the
        member's Alta Open (OpenPath) user is active, has the right access groups
        (e.g. Subscribers -> General Member Access), and has a door credential.

        Returns a checklist with ✅/❌/⚠️ per item, a suggested fix for each
        problem, and an overall verdict. Present the checklist to the user as-is.
        ➖ means the item isn't met but isn't required for this account type
        (e.g. Paid Staff don't need a paid membership), so it is not a problem.

        Args:
            member: Neon account ID, email address, or "First Last" name.
                If several people match, a list is returned so the user can pick;
                call again with the chosen Neon account ID.
        """
        try:
            report, neonIds = door_access.lookUp(member)
        except Exception as err:
            log.error("check_door_access failed: %s", _errorKind(err))
            _audit("check_door_access", [])
            return f"The check crashed: {door_access._explainHttpError(err)}"
        _audit("check_door_access", neonIds)
        return report

    @mcp.tool
    def find_member(query: str) -> str:
        """Search Neon for members by Neon account ID, email address, or name.

        Use this when the user isn't sure who they mean, then pass the Neon
        account ID to check_door_access.
        """
        try:
            matches = door_access.findMembers(query)
            neonIds = door_access.accountIds(matches)
            found = door_access.formatMatches(matches)
        except Exception as err:
            log.error("find_member failed: %s", _errorKind(err))
            _audit("find_member", [])
            return f"Couldn't search Neon: {door_access._explainHttpError(err)}"
        _audit("find_member", neonIds)
        return found if matches else f"No Neon account found for \"{query}\"."

    return mcp
