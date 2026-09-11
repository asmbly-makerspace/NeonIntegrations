"""
Unit tests for update_discourse_ids() in discourseUpdateGroups.py

update_discourse_ids() is pure - both sides are injected, and it returns the
[(account, discourseID), ...] it wants written - so these build the inputs
directly and assert on the return value.  Only getActiveUsers() needs the network.
"""

import pytest
from discourseUtil import D_baseURL, USERS_PER_PAGE
from discourseUpdateGroups import update_discourse_ids
import discourseUtil

DISCOURSE_PAGE_0 = f'{D_baseURL}/admin/users/list/active.json?page=0&show_emails=true'


def neonAccount(neonID, first, last, email, dID=None):
    """A Neon account shaped the way neonUtil.getRealAccounts() hands them over.
    Optional custom fields are absent rather than None, and neonUtil lowercases
    DiscourseID on read, so dID is always lowercase here."""
    account = {
        "Account ID": str(neonID),
        "First Name": first,
        "Last Name": last,
        "fullName": f"{first} {last}",
    }
    if email is not None:
        account["Email 1"] = email
    if dID is not None:
        account["DiscourseID"] = dID
    return account


def neonAccounts(*accounts):
    return {account["Account ID"]: account for account in accounts}


def discourseUsers(*users):
    """(username, email) or (username, email, name).  getActiveUsers() lowercases the
    username in place and keys on it, so mirror that here."""
    return {u[0].lower(): {"username": u[0].lower(), "email": u[1],
                           "name": u[2] if len(u) > 2 else ""}
            for u in users}


def applied(updates):
    """{account id: value} for whatever the function decided to write."""
    return {account["Account ID"]: dID for account, dID in updates}


class TestMatching:
    def test_case_0b_shared_address_resolved_by_name(self):
        accounts = neonAccounts(neonAccount(1, "Jack", "Adams", "family@example.com"),
                                neonAccount(2, "Jane", "Adams", "family@example.com"))
        discourse = discourseUsers(("janea", "family@example.com", "Jane Adams"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"2": "janea"}

    def test_case_0b_shared_address_with_no_name_match_is_skipped(self):
        """Discourse's name field is freeform - 'Jane' doesn't identify anyone here."""
        accounts = neonAccounts(neonAccount(1, "Jack", "Adams", "family@example.com"),
                                neonAccount(2, "Jane", "Adams", "family@example.com"))
        discourse = discourseUsers(("janea", "family@example.com", "Jane"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_case_0b_shared_address_with_duplicate_names_is_skipped(self):
        """Two Neon records for one person - we can't tell which to link."""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com"),
                                neonAccount(2, "Bob", "Smith", "bob@example.com"))
        discourse = discourseUsers(("bobs", "bob@example.com", "Bob Smith"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_case_0e_excluded_discourse_account_is_never_linked(self):
        """janedoe is a test account, so it's not moved"""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com", dID="bob"))
        discourse = discourseUsers(("bob", "bob@yahoo.com"),
                                   ("janedoe", "bob@example.com"))

        # without the exclusion this would be {"1": "janedoe"}
        assert update_discourse_ids(accounts, discourse) == []

    def test_case_1a_links_on_email(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com"))
        discourse = discourseUsers(("BobS", "bob@example.com"))

        # store lowercase usernames
        assert applied(update_discourse_ids(accounts, discourse)) == {"1": "bobs"}

    def test_email_match_is_case_and_whitespace_insensitive(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", " Bob@Example.com "))
        discourse = discourseUsers(("bobs", "bob@example.COM"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"1": "bobs"}

    def test_case_1b_no_match_changes_nothing(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com"))
        discourse = discourseUsers(("someoneelse", "nobody@example.com"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_case_2_clears_a_dead_id(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com", dID="oldbob"))
        discourse = discourseUsers(("someoneelse", "nobody@example.com"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"1": ""}

    def test_case_3_already_correct_changes_nothing(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com", dID="bobs"),
                                neonAccount(2, "Jane", "Doe", "jane@example.com"))
        discourse = discourseUsers(("bobs", "bob@example.com"), ("janed", "jane@example.com"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"2": "janed"}

    def test_case_3_tolerates_uppercase_discourse_username(self):
        """neonUtil lowercases DiscourseID on read and ~40% of Discourse usernames carry
        uppercase.  A case-sensitive comparison here would clear ~540 valid links."""
        accounts = neonAccounts(neonAccount(1, "Perla", "Ayora", "perla@example.com", dID="perlaayora"))
        discourse = discourseUsers(("PerlaAyora", "perla@example.com"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_case_4a_replaces_a_dead_id_with_the_new_match(self):
        """Re-matching beats clearing - the member made a new forum account."""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com", dID="oldbob"))
        discourse = discourseUsers(("newbob", "bob@example.com"))

        updates = update_discourse_ids(accounts, discourse)

        assert applied(updates) == {"1": "newbob"}
        assert len(updates) == 1, "must not also queue a clear for the same account"

    def test_case_4a_replaces_a_live_id_when_a_newer_account_matches(self):
        """The old account still exists, but a newer one has their address."""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "bob@example.com", dID="bobs"))
        discourse = discourseUsers(("bobs", "old@example.com"), ("bob2", "bob@example.com"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"1": "bob2"}

    def test_case_4b_keeps_an_unclaimed_id_when_emails_diverge(self):
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "new@example.com", dID="bobs"))
        discourse = discourseUsers(("bobs", "old@example.com"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_correct_id_is_not_rewritten_on_the_next_run(self):
        """Whatever we write has to settle, or it churns daily."""
        accounts = neonAccounts(neonAccount(1, "Josh", "Ua", "josh@example.com", dID="joshua"))
        discourse = discourseUsers(("Joshua", "josh@example.com"))

        assert update_discourse_ids(accounts, discourse) == []

    def test_case_4c_clears_an_id_claimed_by_another_neon_account(self):
        """Two Neon accounts pointing at one forum user - only the one whose email
        matches keeps it, otherwise a lapsed membership props up the other's access."""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "old@example.com", dID="bobs"),
                                neonAccount(2, "Bob", "Smith", "bob@example.com"))
        discourse = discourseUsers(("bobs", "bob@example.com"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"1": "", "2": "bobs"}

    def test_case_4c_check_is_case_insensitive(self):
        """discourseMatches holds Discourse's casing; DiscourseID is lowercased on read."""
        accounts = neonAccounts(neonAccount(1, "Bob", "Smith", "old@example.com", dID="perlaayora"),
                                neonAccount(2, "Perla", "Ayora", "perla@example.com"))
        discourse = discourseUsers(("PerlaAyora", "perla@example.com"))

        assert applied(update_discourse_ids(accounts, discourse)) == {"1": "", "2": "perlaayora"}

    def test_empty_accounts_dict_changes_nothing(self):
        assert update_discourse_ids({}, discourseUsers(("bobs", "bob@example.com"))) == []
