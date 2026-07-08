"""
Characterization tests for the alta_open_lambda webhook handler.

These tests will pin down exactly what ``lambda_handler`` does TODAY, before the
planned refactor that unifies handling of the two Neon webhook payload formats.
The suite is green against the pre-refactor handler; as the refactor converges
the formats, the relevant assertions get flipped one at a time.

Incoming event formats:
------------------------------------------------------------
legacy (old_webhooks.json / events.json):
  - integer account IDs (e.g. 9058)
  - nested shapes (membershipEnrollment + transaction; tickets as
    ``{"ticket": [...]}``);
  - customParameters may be null or tagged ``legacy: "true"``

new (post 2026-05-09):
  - string account IDs (e.g. "1877")
  - flat shapes (membership fields hoisted to the data top level; tickets as
    plain arrays);
  - customParameters is ``null`` today -- the new webhook was activated without
    the ``legacy``/``webhook_name`` parameters, so its events arrive unmarked.
    Once those parameters are added it will be tagged ``legacy: "false"``.
    Either way the handler treats anything that is not explicitly
    ``legacy: "true"`` as the new format, so both null and "false" route to the
    flat (status/enrollType) fields.

Verified against 306 real createMembership events captured 2026-06-02..07-02:
every ``null`` event was flat/new (string id) and every ``legacy: "true"`` event
was nested/legacy (int id) -- a clean 155/151 split with no crossover.
"""

import datetime
import json
import logging
import random
import sys
from pathlib import Path

import pytest

# lambda_function lives in alta_open_lambda/, which is not a package
sys.path.insert(0, str(Path(__file__).parent.parent / "alta_open_lambda"))

import lambda_function as lf


@pytest.fixture
def openpath(mocker):
    """Mock the OpenPath update so we only exercise webhook parsing."""
    return mocker.patch.object(lf, "openPathUpdateSingle")


@pytest.fixture
def neon_account(mocker):
    """Mock the Neon account fetch used by handle_joins. Default membershipDates
    are in the past, so should_add_member is False and the Mailjet add never
    fires -- these tests assert only whether the join path was entered."""
    return mocker.patch.object(
        lf,
        "getMemberById",
        return_value={"membershipDates": {"2020-01-01": ["2020-12-31"]}},
    )


@pytest.fixture
def mailjet(mocker):
    """Mock the Mailjet add so handle_joins' decision is observable without
    touching SSM or the network."""
    return mocker.patch.object(lf, "add_member_to_mailjet")


def make_event(event_trigger, data, custom_parameters):
    """Wrap a webhook body in the Lambda Function URL envelope. Production
    always delivers body as a JSON string."""
    return {
        "body": json.dumps(
            {
                "eventTrigger": event_trigger,
                "eventTimestamp": "2026-06-10T12:00:00.000-05:00",
                "organizationId": "asmbly",
                "data": data,
                "customParameters": custom_parameters,
            }
        )
    }


# customParameters variants seen in production.
# NOTE: post-cutover (2026-05-09), a null customParameters means the NEW webhook
# firing without its legacy/webhook_name params -- not a legacy event. The
# handler keys off the legacy flag, treating anything not "true" as new format.
NULL_PARAMS = None  # new webhook today: activated without legacy/webhook_name
LEGACY_PARAMS = {"webhook_name": "NewMembershipLegacy", "legacy": "true"}
NEW_PARAMS = {"webhook_name": "NewMembership", "legacy": "false"}  # future: once params added

# Back-compat alias: older tests below used UNKNOWN_PARAMS for null customParameters.
UNKNOWN_PARAMS = NULL_PARAMS


def rand_id():
    """A random Neon-style numeric id. The handler passes ids straight through,
    so the exact value is irrelevant -- randomizing makes that explicit and
    keeps arbitrary numbers from looking meaningful."""
    return random.randint(1, 9_999_999)


# ===========================================================================
# Guard clauses -- trigger-independent; these exercise the harness end to end
# ===========================================================================


def test_ignores_event_without_body(openpath):
    lf.lambda_handler({"requestContext": {}}, {})
    openpath.assert_not_called()


def test_ignores_unknown_trigger(openpath):
    lf.lambda_handler(make_event("somethingElse", {"accountId": 1}, NEW_PARAMS), {})
    openpath.assert_not_called()


def test_body_as_dict_currently_raises(openpath):
    """Production delivers body as a JSON string; the handler always
    json.loads(body). A dict body (as some saved fixtures store it) raises
    TypeError today. Pinned so the refactor can decide whether to accept it."""
    event = make_event("editAccount", {"individualAccount": {"accountId": 1}}, NEW_PARAMS)
    event["body"] = json.loads(event["body"])
    with pytest.raises(TypeError):
        lf.lambda_handler(event, {})
    openpath.assert_not_called()


# ===========================================================================
# editAccount
# ===========================================================================


def legacy_edit_account(account_id=None):
    # legacy: integer accountId, nested individualAccount
    account_id = rand_id() if account_id is None else account_id
    return make_event(
        "editAccount",
        {
            "individualAccount": {
                "accountId": account_id,
                "primaryContact": {"contactId": account_id},
                "customFieldDataList": {"customFieldData": []},
            }
        },
        UNKNOWN_PARAMS,
    )


def test_legacy_edit_account_passes_int_id(openpath):
    account_id = rand_id()
    lf.lambda_handler(legacy_edit_account(account_id), {})
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# updateMembership
# ===========================================================================


def legacy_update_membership(account_id=None):
    # legacy: nested membershipEnrollment + transaction
    account_id = rand_id() if account_id is None else account_id
    return make_event(
        "updateMembership",
        {
            "membershipEnrollment": {
                "accountId": account_id,
                "membershipId": rand_id(),
                "enrollmentType": "RENEW",
            },
            "transaction": {
                "transactionId": rand_id(),
                "transactionStatus": "SUCCEEDED",
            },
        },
        LEGACY_PARAMS,
    )


def test_legacy_update_membership_passes_int_id(openpath):
    account_id = rand_id()
    lf.lambda_handler(legacy_update_membership(account_id), {})
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# Legacy-flag detection -- customParameters.legacy
# ===========================================================================

def test_null_custom_parameters_does_not_warn_or_crash(openpath, caplog):
    # Truly-legacy events deliver customParameters: null. This must not warn
    # and must not raise (regression guard for the historical NoneType bug).
    account_id = rand_id()
    event = make_event("editAccount", {"individualAccount": {"accountId": account_id}}, UNKNOWN_PARAMS)
    with caplog.at_level(logging.WARNING):
        lf.lambda_handler(event, {})
    assert "LEGACY EVENT DETECTED" not in caplog.text
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# createMembership -- join detection (enrollmentType + transactionStatus)
# ===========================================================================


def legacy_create_membership(enrollment_type, transaction_status, account_id=None):
    # legacy: nested membershipEnrollment.enrollmentType + transaction.transactionStatus
    account_id = rand_id() if account_id is None else account_id
    return make_event(
        "createMembership",
        {
            "membershipEnrollment": {
                "accountId": account_id,
                "membershipId": rand_id(),
                "termStartDate": "2026-06-10T05:00:00.000+0000",
                "enrollmentType": enrollment_type,
            },
            "transaction": {
                "transactionId": rand_id(),
                "transactionStatus": transaction_status,
                "payments": {"payment": [{"paymentId": rand_id(), "amount": 95.0}]},
            },
        },
        LEGACY_PARAMS,
    )


@pytest.mark.parametrize("enrollment_type", ["JOIN", "REJOIN"])
def test_legacy_successful_join_enters_join_path(openpath, neon_account, enrollment_type):
    # A successful JOIN/REJOIN runs handle_joins (which fetches the account)
    # before the usual OpenPath update.
    account_id = rand_id()
    lf.lambda_handler(legacy_create_membership(enrollment_type, "SUCCEEDED", account_id), {})
    neon_account.assert_called_once_with(id=account_id)
    openpath.assert_called_once_with(account_id)


def test_legacy_renew_skips_join_path(openpath, neon_account):
    # RENEW is not a join, so handle_joins is never entered.
    account_id = rand_id()
    lf.lambda_handler(legacy_create_membership("RENEW", "SUCCEEDED", account_id), {})
    neon_account.assert_not_called()
    openpath.assert_called_once_with(account_id)


def test_legacy_failed_transaction_skips_join_path(openpath, neon_account):
    # Even a JOIN skips handle_joins when the transaction did not succeed.
    account_id = rand_id()
    lf.lambda_handler(legacy_create_membership("JOIN", "FAILED", account_id), {})
    neon_account.assert_not_called()
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# createMembership -- Mailjet add decision (handle_joins.should_add_member)
# ===========================================================================
#
# handle_joins compares the latest membership start date against "today"
# (America/Chicago, read live -- no frozen clock), so these membershipDates are
# built relative to the current run date.


def test_fresh_first_join_adds_to_mailjet(openpath, neon_account, mailjet):
    # First-ever membership, starting today -> add to Mailjet.
    today = datetime.datetime.now(lf.TZ).date()
    neon_account.return_value = {
        "membershipDates": {
            today.isoformat(): [(today + datetime.timedelta(days=30)).isoformat()],
        }
    }
    lf.lambda_handler(legacy_create_membership("JOIN", "SUCCEEDED"), {})
    mailjet.assert_called_once()


def test_rejoin_with_recent_membership_does_not_add_to_mailjet(openpath, neon_account, mailjet):
    # Latest membership starts today, but a prior one ended < 365 days ago, so
    # this is a continuation rather than a true rejoin -- no Mailjet add.
    today = datetime.datetime.now(lf.TZ).date()
    prior_start = today - datetime.timedelta(days=60)
    prior_end = today - datetime.timedelta(days=30)
    neon_account.return_value = {
        "membershipDates": {
            prior_start.isoformat(): [prior_end.isoformat()],
            today.isoformat(): [(today + datetime.timedelta(days=30)).isoformat()],
        }
    }
    lf.lambda_handler(legacy_create_membership("REJOIN", "SUCCEEDED"), {})
    mailjet.assert_not_called()


def test_rejoin_after_long_lapse_adds_to_mailjet(openpath, neon_account, mailjet):
    # Prior membership ended > 365 days ago -> treated as a genuine rejoin.
    today = datetime.datetime.now(lf.TZ).date()
    lapsed_start = today - datetime.timedelta(days=1000)
    lapsed_end = today - datetime.timedelta(days=800)
    neon_account.return_value = {
        "membershipDates": {
            lapsed_start.isoformat(): [lapsed_end.isoformat()],
            today.isoformat(): [(today + datetime.timedelta(days=30)).isoformat()],
        }
    }
    lf.lambda_handler(legacy_create_membership("REJOIN", "SUCCEEDED"), {})
    mailjet.assert_called_once()


# ===========================================================================
# mergedAccount -- resolves the surviving (matched) account
# ===========================================================================
#
# Real captured shape (June 2026): string IDs and customParameters null. The
# handler pulls matchedAccountId (the account that survives the merge), not the
# merged-away mergedAccountId, and passes that string straight to OpenPath.


def merged_account(matched_account_id=None):
    matched_account_id = str(rand_id()) if matched_account_id is None else matched_account_id
    return make_event(
        "mergedAccount",
        {
            "mergedAccountId": str(rand_id()),
            "matchedAccountId": matched_account_id,
            "mergeTime": "2026-06-07T20:38:57.000-05:00",
            "mergedBy": "Account Match",
        },
        UNKNOWN_PARAMS,
    )


def test_merged_account_resolves_matched_account_string_id(openpath):
    matched_account_id = str(rand_id())
    lf.lambda_handler(merged_account(matched_account_id), {})
    openpath.assert_called_once_with(matched_account_id)


# ===========================================================================
# updateEventRegistration -- ignored (no OpenPath update)
# ===========================================================================
#
# Real captured shape (fires ~1700x/yr): a flat tickets array. The handler logs
# an "Ignoring..." line and returns without touching OpenPath. Pinned so a
# refactor keeps event registrations out of the OpenPath path.


def update_event_registration(account_id=None):
    account_id = str(rand_id()) if account_id is None else account_id
    return make_event(
        "updateEventRegistration",
        {
            "id": str(rand_id()),
            "eventId": str(rand_id()),
            "registrantAccountId": account_id,
            "tickets": [
                {
                    "attendees": [
                        {
                            "attendeeId": rand_id(),
                            "accountId": account_id,
                            "markedAttended": False,
                            "registrantAccountId": account_id,
                            "registrationStatus": "SUCCEEDED",
                        }
                    ]
                }
            ],
            "payments": [],
        },
        UNKNOWN_PARAMS,
    )


def test_event_registration_is_ignored(openpath, caplog):
    with caplog.at_level(logging.INFO):
        lf.lambda_handler(update_event_registration(), {})
    assert "Ignoring updateEventRegistration" in caplog.text
    openpath.assert_not_called()


# ===========================================================================
# createAccount -- currently dropped (no handler case)
# ===========================================================================
#
# Real captured shape (fires ~235x/yr): string IDs, nested individualAccount.
# There is NO match case for createAccount, so even though the payload carries a
# usable accountId the handler resolves no neon_id and returns without an
# OpenPath update. Pinned to flag this gap for the refactor.


def create_account(account_id=None):
    account_id = str(rand_id()) if account_id is None else account_id
    return make_event(
        "createAccount",
        {
            "individualAccount": {
                "accountId": account_id,
                "primaryContact": {"contactId": str(rand_id())},
                "accountCustomFields": [],
                "individualTypes": [],
            }
        },
        {"key": ""},
    )


def test_create_account_is_currently_dropped(openpath):
    # No case for createAccount -> no neon_id -> no OpenPath update, even though
    # the payload contains a valid accountId.
    lf.lambda_handler(create_account(), {})
    openpath.assert_not_called()


# ###########################################################################
# NEW FORMAT (post 2026-05-09) -- string IDs, flat shapes, legacy:"false".
# Characterizing how today's handler treats new-format payloads; the
# divergences from the legacy behavior above are flagged inline for the
# refactor to converge.
# ###########################################################################


# ===========================================================================
# editAccount (new) -- string id passthrough
# ===========================================================================


def new_edit_account(account_id=None):
    # new: string accountId, accountCustomFields array
    account_id = str(rand_id()) if account_id is None else account_id
    return make_event(
        "editAccount",
        {
            "individualAccount": {
                "accountId": account_id,
                "primaryContact": {"contactId": str(rand_id())},
                "accountCustomFields": [],
                "individualTypes": [],
            }
        },
        NEW_PARAMS,
    )


def test_new_edit_account_passes_string_id(openpath):
    # DIVERGENCE (id type): new yields a string id where legacy yields an int;
    # both are passed straight through. The refactor decides whether to
    # normalize the type.
    account_id = str(rand_id())
    lf.lambda_handler(new_edit_account(account_id), {})
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# updateMembership (new) -- flat shape, string id passthrough
# ===========================================================================


def new_update_membership(account_id=None):
    # new: flat fields hoisted to the data top level (no membershipEnrollment /
    # transaction wrappers)
    account_id = str(rand_id()) if account_id is None else account_id
    return make_event(
        "updateMembership",
        {
            "id": str(rand_id()),
            "accountId": account_id,
            "enrollType": "RENEW",
            "status": "SUCCEEDED",
            "termStartDate": "2026-06-07",
            "payments": [{"id": str(rand_id()), "paymentStatus": "Succeeded"}],
        },
        NEW_PARAMS,
    )


def test_new_update_membership_passes_string_id(openpath):
    # DIVERGENCE (id type only): like legacy, the account is resolved and reaches
    # OpenPath -- just as a string.
    account_id = str(rand_id())
    lf.lambda_handler(new_update_membership(account_id), {})
    openpath.assert_called_once_with(account_id)


# ===========================================================================
# createMembership (new) -- join detection
# ===========================================================================
#
# Real captured shape (306 events, 2026-06-02..07-02): flat data with
# enrollType/status at the top level and string ids, wrapped around a rich
# membership body and a payments[] array carrying card details. Verified values:
# status in {SUCCEEDED, FAILED}, enrollType in {JOIN, RENEW} (REJOIN was not seen
# in the window but is handled identically). These events arrive with
# customParameters null today, and will carry legacy:"false" once the new
# webhook's params are added -- both take the handler's non-legacy branch, so the
# join tests below run against both variants.


# customParameters values the new webhook produces now (null) and after its
# params are added ("false"); both must route to the flat status/enrollType fields.
NEW_PARAM_VARIANTS = [
    pytest.param(NULL_PARAMS, id="null-params"),
    pytest.param(NEW_PARAMS, id="legacy-false"),
]


def new_create_membership(enroll_type, status, account_id=None, custom_parameters=NEW_PARAMS):
    # Mirrors the real flat payload; PII (names, card token/last-four) is replaced
    # with obvious fakes. Only accountId/enrollType/status drive handler behavior,
    # but the surrounding structure (nested creditCardOnline.id, paymentStatus)
    # keeps the find_key_bfs lookups honest against a realistic shape.
    account_id = str(rand_id()) if account_id is None else account_id
    return make_event(
        "createMembership",
        {
            "id": str(rand_id()),
            "accountId": account_id,
            "membershipLevel": {"id": "1", "name": "Regular Membership"},
            "membershipTerm": {"id": "1", "name": "Monthly Membership"},
            "autoRenewal": True,
            "changeType": "UNCHANGED",
            "termUnit": "MONTH",
            "termDuration": 1,
            "enrollType": enroll_type,
            "transactionDate": "2026-06-10",
            "termStartDate": "2026-06-10",
            "termEndDate": "2026-07-09",
            "fee": 95.0,
            "status": status,
            "membershipCustomFields": [],
            "timestamps": {
                "createdBy": "Test Admin",
                "createdDateTime": "2026-06-10T12:00:00Z",
                "lastModifiedBy": "Test Admin",
                "lastModifiedDateTime": "2026-06-10T12:00:05Z",
            },
            "payments": [
                {
                    "id": str(rand_id()),
                    "amount": 95.0,
                    "paymentStatus": "Succeeded",
                    "tenderType": 4,
                    "creditCardOnline": {
                        "id": rand_id(),
                        "token": "nptoken_FAKE",
                        "cardNumberLastFour": "0000",
                        "cardTypeCode": "V",
                        "cardHolderName": "Test Cardholder",
                        "transactionNumber": "npcharge_FAKE",
                    },
                }
            ],
            "donorCoveredFeeFlag": False,
        },
        custom_parameters,
    )


@pytest.mark.parametrize("params", NEW_PARAM_VARIANTS)
@pytest.mark.parametrize("enroll_type", ["JOIN", "REJOIN"])
def test_new_successful_join_enters_join_path(openpath, neon_account, enroll_type, params):
    # A successful new-format JOIN/REJOIN fetches the account via handle_joins,
    # exactly like legacy -- whether unmarked (null) or tagged legacy:"false".
    account_id = str(rand_id())
    lf.lambda_handler(new_create_membership(enroll_type, "SUCCEEDED", account_id, params), {})
    neon_account.assert_called_once_with(id=account_id)
    openpath.assert_called_once_with(account_id)


@pytest.mark.parametrize("params", NEW_PARAM_VARIANTS)
def test_new_renew_skips_join_path(openpath, neon_account, params):
    # RENEW is not a join, so handle_joins is never entered.
    account_id = str(rand_id())
    lf.lambda_handler(new_create_membership("RENEW", "SUCCEEDED", account_id, params), {})
    neon_account.assert_not_called()
    openpath.assert_called_once_with(account_id)


@pytest.mark.parametrize("params", NEW_PARAM_VARIANTS)
def test_new_failed_transaction_skips_join_path(openpath, neon_account, params):
    # A failed transaction is not a join, even for JOIN.
    account_id = str(rand_id())
    lf.lambda_handler(new_create_membership("JOIN", "FAILED", account_id, params), {})
    neon_account.assert_not_called()
    openpath.assert_called_once_with(account_id)


@pytest.mark.parametrize("params", NEW_PARAM_VARIANTS)
def test_new_fresh_join_adds_to_mailjet(openpath, neon_account, mailjet, params):
    # A fresh first join in the new format adds to Mailjet, like the legacy equivalent.
    today = datetime.datetime.now(lf.TZ).date()
    neon_account.return_value = {
        "membershipDates": {today.isoformat(): [(today + datetime.timedelta(days=30)).isoformat()]}
    }
    account_id = str(rand_id())
    lf.lambda_handler(new_create_membership("JOIN", "SUCCEEDED", account_id, params), {})
    mailjet.assert_called_once()
