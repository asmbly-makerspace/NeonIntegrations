###############################################################################
# The tools Claude can call. Shared by the local server (local.py) and the
# hosted server on AWS (hosted.py).
#
# Everything here is READ ONLY: it looks things up in Neon and Alta Open but
# never changes them. Keep it that way unless a tool is clearly named as a write.
###############################################################################

import logging

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

INSTRUCTIONS = (
    "Tools for Asmbly Makerspace staff and volunteers. "
    "Use check_door_access when someone can't get in the door."
)


def _caller():
    # Who is asking. Only known when hosted and signed in; local use has no sign-in.
    try:
        token = get_access_token()
    except Exception:
        return "local"
    if token is None:
        return "local"
    return token.claims.get("email") or token.claims.get("sub") or "signed-in user"


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
        # log who asked, but not who they asked about (member PII stays out of the logs)
        logging.info("check_door_access called by %s", _caller())
        try:
            return door_access.checkMember(member)
        except Exception as err:
            logging.exception("check_door_access failed")
            return f"The check crashed: {door_access._explainHttpError(err)}"

    @mcp.tool
    def find_member(query: str) -> str:
        """Search Neon for members by Neon account ID, email address, or name.

        Use this when the user isn't sure who they mean, then pass the Neon
        account ID to check_door_access.
        """
        logging.info("find_member called by %s", _caller())
        try:
            matches = door_access.findMembers(query)
        except Exception as err:
            return f"Couldn't search Neon: {door_access._explainHttpError(err)}"
        if not matches:
            return f"No Neon account found for \"{query}\"."
        return door_access.formatMatches(matches)

    return mcp
