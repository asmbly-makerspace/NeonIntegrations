###############################################################################
# Local server: runs on your own computer for Claude Code / Claude Desktop.
# Uses the API keys in the repo's config.py (which git ignores). No sign-in.
#
# Setup (one time), from the repo root:
#   uv run --project asmbly_mcp asmbly_mcp/setup_local.py
# See LOCAL_SETUP.md for the step-by-step guide.
###############################################################################

import logging
import sys

from asmbly_mcp.tools import buildServer

# stdout carries the MCP protocol, so logs must go to stderr
logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(message)s")

mcp = buildServer()

if __name__ == "__main__":
    mcp.run(show_banner=False)
