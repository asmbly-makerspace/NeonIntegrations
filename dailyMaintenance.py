from discourseUpdateGroups import discourseUpdateGroups, update_discourse_ids
from openPathUpdateAll import openPathUpdateAll
from mailjetUtil import run_mailjet_maintenance

import discourseUtil
import neonUtil
import logging
import sys
import datetime, pytz

import json

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    logging.info("Starting sync cycle.")
    neonAccounts = {}

    # For real use, just get neon accounts directly
    # Be aware this takes a long time (2+ minutes)
    try:
        neonAccounts = neonUtil.getRealAccounts()
    except Exception:
        # The OpenPath and Discourse phases need the complete account list. Syncing from
        # a partial one could revoke door access or demote Makers. Mailjet doesn't need
        # the list, but it queries the same Neon API, so skip it too and stop here.
        logging.exception("Failed to fetch Neon accounts; skipping the whole sync cycle.")
        sys.exit(1)

    # Testing goes a lot faster if we're working with a cache of accounts
    # with open("Neon/neonAccounts.json") as neonFile:
    #     neonAccountJson = json.load(neonFile)
    #     for account in neonAccountJson:
    #         neonAccounts[neonAccountJson[account]["Account ID"]] = neonAccountJson[account]

    # Each phase below runs even if an earlier one failed, so one bad account or a
    # flaky API can't skip the rest of the sync. We remember what failed and exit
    # non-zero at the end so the systemd unit shows up as failed.
    failedPhases = []

    # we're going to run this multiple times per day, but we don't want to send a zillion emails
    # Compare local wall-clock time. Don't pass a pytz zone as tzinfo= (e.g. to datetime.time):
    # it gets the zone's 1800s local mean time offset (-5:51) instead of CST/CDT.
    now = datetime.datetime.now(pytz.timezone("America/Chicago"))

    try:
        if now.time() < datetime.time(6, 0):
            openPathFailures = openPathUpdateAll(neonAccounts, mailSummary=True)
        else:
            openPathFailures = openPathUpdateAll(neonAccounts, mailSummary=False)
        # openPathUpdateAll may hand back a list of the accounts it couldn't update
        if openPathFailures:
            logging.error("OpenPath sync failed for %s account(s).", len(openPathFailures))
            failedPhases.append("OpenPath sync")
    except Exception:
        logging.exception("OpenPath sync failed.")
        failedPhases.append("OpenPath sync")

    # Match Discourse with Neon accounts based on email, then
    # writes newly matched IDs back into neo and to the local account objects
    try:
        discourseAccounts = discourseUtil.getActiveUsers()
        neonUtil.batchUpdateDIDs(update_discourse_ids(neonAccounts, discourseAccounts))
    except Exception:
        logging.exception("DiscourseID sync failed.")
        failedPhases.append("DiscourseID sync")

    # still worth running if the ID sync failed; it uses whatever DiscourseIDs the accounts have
    try:
        discourseUpdateGroups(neonAccounts)
    except Exception:
        logging.exception("Discourse group sync failed.")
        failedPhases.append("Discourse group sync")

    # Mailjet does its own Neon searches, so it doesn't depend on the phases above
    try:
        run_mailjet_maintenance()
    except Exception:
        logging.exception("Mailjet sync failed.")
        failedPhases.append("Mailjet sync")

    if failedPhases:
        logging.error("Sync cycle finished, but these phases failed: %s", ", ".join(failedPhases))
        sys.exit(1)

    logging.info("Sync cycle complete.")


if __name__ == '__main__':
    main()
