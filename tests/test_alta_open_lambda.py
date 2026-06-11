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
