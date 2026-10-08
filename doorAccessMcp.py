###############################################################################
# MCP server so Claude can troubleshoot member door access in chat.
# READ ONLY: it looks things up in Neon and Alta Open but never changes them.
#
# Setup (one time):   uv run --group door-access setup_door_access.py
# See DOOR_ACCESS_SETUP.md for the step-by-step guide.
###############################################################################

import logging
import sys

from mcp.server.fastmcp import FastMCP

import doorAccessCheck

# stdout carries the MCP protocol, so logs must go to stderr
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(message)s")

mcp = FastMCP("asmbly-door-access")


@mcp.tool()
def check_door_access(member: str) -> str:
    """Troubleshoot why an Asmbly member can't get in the door.

    Checks, in order: Neon membership is paid and current, AccessSuspended is
    not set, WaiverDate is set, FacilityTourDate (orientation) is set, the
    member's Alta Open (OpenPath) user is active, has the right access groups
    (e.g. Subscribers -> General Member Access), and has a door credential.

    Returns a checklist with ✅/❌/⚠️ per item, a suggested fix for each
    problem, and an overall verdict. Present the checklist to the user as-is.

    Args:
        member: Neon account ID, email address, or "First Last" name.
            If several people match, a list is returned so the user can pick;
            call again with the chosen Neon account ID.
    """
    try:
        return doorAccessCheck.checkMember(member)
    except Exception as err:
        logging.exception("check_door_access failed")
        return f"The check crashed: {doorAccessCheck._explainHttpError(err)}"


@mcp.tool()
def find_member(query: str) -> str:
    """Search Neon for members by Neon account ID, email address, or name.

    Use this when the user isn't sure who they mean, then pass the Neon
    account ID to check_door_access.
    """
    try:
        matches = doorAccessCheck.findMembers(query)
    except Exception as err:
        return f"Couldn't search Neon: {doorAccessCheck._explainHttpError(err)}"
    if not matches:
        return f"No Neon account found for \"{query}\"."
    return doorAccessCheck.formatMatches(matches)


if __name__ == "__main__":
    mcp.run()
