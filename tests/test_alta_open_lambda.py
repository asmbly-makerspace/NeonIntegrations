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

new (new_webhooks.json, post 2026-05-09):
  - string account IDs (e.g. "1877")
  - flat shapes (membership fields hoisted to the data top level; tickets as
    plain arrays);
  - customParameters tagged ``legacy: "false"``
"""

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


# customParameters variants seen in production
UNKNOWN_PARAMS = None  # truly-legacy events send customParameters: null
LEGACY_PARAMS = {"webhook_name": "UpdateMembershipLegacy", "legacy": "true"}
NEW_PARAMS = {"webhook_name": "UpdateMembership20260509", "legacy": "false"}


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
