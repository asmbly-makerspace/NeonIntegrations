"""
Tests for the class-to-field table (helpers/class_fields.py), how
attendanceToTestout.py loads it, and the seed script.
"""

import json
import logging
import os
import subprocess
import sys

import boto3
import pytest
from botocore.stub import Stubber

from helpers import class_fields
from helpers.class_fields import ClassFieldsError, parseClassFields

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
import class_fields_seed  # noqa: E402

FIXTURE = os.path.join(REPO_ROOT, "tests", "fixtures", "class_fields.json")

# Last commit with the hard-coded EVENT_FIELDS table in attendanceToTestout.py
LAST_HARD_CODED_COMMIT = "ecb9244"


def value(fields, version=1):
    return json.dumps({"version": version, "fields": fields})


# ============================================================================
# Validation
# ============================================================================

def test_parse_returns_ordered_pairs():
    assert parseClassFields(value([["Woodshop Safety", "84"], ["CSI", "1248"]])) == [
        ("Woodshop Safety", "84"),
        ("CSI", "1248"),
    ]


@pytest.mark.parametrize("fields", [
    pytest.param([["A", "1"]], id="one-entry"),
    pytest.param([[f"Class {i}", str(i + 1)] for i in range(200)], id="200-entries"),
    pytest.param([["x" * 64, "1"]], id="64-char-phrase"),
    pytest.param([["Laser (Big) & CNC: 1/2, v.2 + O'Neil-x", "1"]], id="every-allowed-punctuation"),
    pytest.param([["A", "999999999"]], id="9-digit-id"),
    pytest.param([["Woodshop Safety", "84"], ["woodshop safety", "85"]], id="phrases-differ-by-case"),
])
def test_parse_accepts_valid_values(fields):
    assert parseClassFields(value(fields)) == [tuple(f) for f in fields]


@pytest.mark.parametrize("extra, message", [
    pytest.param({"note": "x"}, 'got extra "note"', id="one-extra-key"),
    pytest.param({"Fields": []}, 'got extra "Fields"', id="key-differs-by-case"),
    pytest.param({"b": 1, "a": 2}, 'got extra "a", "b"', id="two-extra-keys"),
    pytest.param({f"k{i}": i for i in range(7)}, "and 2 more", id="many-extra-keys"),
])
def test_parse_rejects_extra_top_level_keys(extra, message):
    # The contract (shared with AsmblyMCPs) allows exactly "version" and "fields"
    raw = json.dumps({"version": 1, "fields": [["A", "1"]], **extra})
    with pytest.raises(ClassFieldsError, match="may only have the keys 'version' and 'fields'") as excinfo:
        parseClassFields(raw)
    assert message in str(excinfo.value)


def test_parse_rejects_deeply_nested_json_as_invalid():
    with pytest.raises(ClassFieldsError, match="not valid JSON"):
        parseClassFields("[" * 100000 + "]" * 100000)


@pytest.mark.parametrize("raw", [
    pytest.param(value([["A", "1"], [["x" * 5000], "2"]]), id="huge-entry"),
    pytest.param(value([["A", "1"]], version="v" * 5000), id="huge-version"),
    pytest.param(json.dumps({"version": 1, "fields": [["A", "1"]], "k" * 5000: 1}), id="huge-extra-key"),
])
def test_errors_quote_bad_values_briefly(raw):
    with pytest.raises(ClassFieldsError) as excinfo:
        parseClassFields(raw)
    assert len(str(excinfo.value)) < 300


@pytest.mark.parametrize("raw, message", [
    # Shape
    pytest.param("not json", "not valid JSON", id="not-json"),
    pytest.param("", "not valid JSON", id="empty-string"),
    pytest.param("[]", "JSON object", id="top-level-list"),
    pytest.param("null", "JSON object", id="top-level-null"),
    # version
    pytest.param(json.dumps({"fields": [["A", "1"]]}), "'version' must be 1", id="version-missing"),
    pytest.param(value([["A", "1"]], version=2), "'version' must be 1, got 2", id="version-2"),
    pytest.param(value([["A", "1"]], version="1"), "'version' must be 1", id="version-string"),
    pytest.param(value([["A", "1"]], version=1.0), "'version' must be 1", id="version-float"),
    pytest.param(value([["A", "1"]], version=True), "'version' must be 1", id="version-true"),
    # fields
    pytest.param(json.dumps({"version": 1}), "'fields' must be a list", id="fields-missing"),
    pytest.param(json.dumps({"version": 1, "fields": {"A": "1"}}), "'fields' must be a list", id="fields-object"),
    pytest.param(value([]), "1 to 200 entries, got 0", id="no-entries"),
    pytest.param(value([[f"Class {i}", str(i + 1)] for i in range(201)]), "1 to 200 entries, got 201", id="201-entries"),
    # entries
    pytest.param(value(["A"]), "entry 0", id="entry-string"),
    pytest.param(value([{"A": "1"}]), "entry 0", id="entry-object"),
    pytest.param(value([["A"]]), "list of two strings", id="entry-one-item"),
    pytest.param(value([["A", "1", "x"]]), "list of two strings", id="entry-three-items"),
    pytest.param(value([["A", 1]]), "list of two strings", id="id-number"),
    pytest.param(value([[None, "1"]]), "list of two strings", id="phrase-null"),
    pytest.param(value([[True, "1"]]), "list of two strings", id="phrase-bool"),
    pytest.param(value([["A", True]]), "list of two strings", id="id-bool"),
    pytest.param(value([["A", 1.5]]), "list of two strings", id="id-float"),
    pytest.param(value([["A", ["1"]]]), "list of two strings", id="id-nested-list"),
    pytest.param(value([[["A"], "1"]]), "list of two strings", id="phrase-nested-list"),
    pytest.param(value([["A", {"id": "1"}]]), "list of two strings", id="id-object"),
    pytest.param(json.dumps({"version": 1, "fields": "A,1"}), "'fields' must be a list", id="fields-string"),
    pytest.param(json.dumps({"version": 1, "fields": None}), "'fields' must be a list", id="fields-null"),
    pytest.param(value([["A", "1"]], version=None), "'version' must be 1, got null", id="version-null"),
    pytest.param(value([["A", "1"]], version=[1]), "'version' must be 1", id="version-list"),
    pytest.param(value([["A", "1"]], version=0), "'version' must be 1", id="version-0"),
    pytest.param('{"version": NaN, "fields": [["A", "1"]]}', "'version' must be 1", id="version-nan"),
    # phrase
    pytest.param(value([["", "1"]]), "1 to 64 ASCII", id="phrase-empty"),
    pytest.param(value([["x" * 65, "1"]]), "1 to 64 ASCII", id="phrase-65-chars"),
    pytest.param(value([["Céramique", "1"]]), "1 to 64 ASCII", id="phrase-non-ascii"),
    pytest.param(value([["Woodshop  Safety", "1"]]), "single spaces", id="phrase-double-space"),
    pytest.param(value([[" Woodshop", "1"]]), "single spaces", id="phrase-leading-space"),
    pytest.param(value([["Woodshop ", "1"]]), "single spaces", id="phrase-trailing-space"),
    pytest.param(value([["Woodshop\tSafety", "1"]]), "single spaces", id="phrase-tab"),
    pytest.param(value([["Woodshop\n", "1"]]), "single spaces", id="phrase-trailing-newline"),
    pytest.param(value([["Woodshop!", "1"]]), "single spaces", id="phrase-bad-punctuation"),
    pytest.param(value([['Say "hi"', "1"]]), "single spaces", id="phrase-double-quote"),
    # id
    pytest.param(value([["A", ""]]), "field id", id="id-empty"),
    pytest.param(value([["A", "0"]]), "field id", id="id-zero"),
    pytest.param(value([["A", "084"]]), "field id", id="id-leading-zero"),
    pytest.param(value([["A", "1234567890"]]), "field id", id="id-10-digits"),
    pytest.param(value([["A", "-1"]]), "field id", id="id-negative"),
    pytest.param(value([["A", "8 4"]]), "field id", id="id-space"),
    pytest.param(value([["A", "84\n"]]), "field id", id="id-trailing-newline"),
    pytest.param(value([["A", "abc"]]), "field id", id="id-letters"),
    pytest.param(value([["A", "٨٤"]]), "field id", id="id-non-ascii-digits"),
    # uniqueness
    pytest.param(value([["A", "1"], ["B", "2"], ["A", "3"]]), 'entry 2 (["A", "3"]): phrase "A" appears more than once', id="duplicate-phrase"),
])
def test_parse_rejects_invalid_values(raw, message):
    with pytest.raises(ClassFieldsError) as excinfo:
        parseClassFields(raw)
    assert message in str(excinfo.value)


def test_one_bad_entry_rejects_the_whole_value():
    with pytest.raises(ClassFieldsError, match="entry 2"):
        parseClassFields(value([["A", "1"], ["B", "2"], ["C", "0"]]))


# ============================================================================
# Loading
# ============================================================================

@pytest.fixture
def on_ec2(monkeypatch):
    monkeypatch.setenv("USER", "ec2-user")
    monkeypatch.delenv("LAMBDA_TASK_ROOT", raising=False)


@pytest.fixture
def ssm_stub(monkeypatch, on_ec2):
    client = boto3.client(
        "ssm",
        region_name="us-east-2",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    created = {}

    def fake_client(service, region_name=None, **kwargs):
        created["service"], created["region"] = service, region_name
        return client

    monkeypatch.setattr(boto3, "client", fake_client)
    with Stubber(client) as stubber:
        yield stubber, created
        stubber.assert_no_pending_responses()


def test_load_reads_ssm_parameter_on_ec2(ssm_stub):
    stubber, created = ssm_stub
    stubber.add_response(
        "get_parameter",
        {"Parameter": {"Name": "/neon/class_fields", "Type": "String", "Value": value([["CSI", "1248"]])}},
        {"Name": "/neon/class_fields"},
    )
    assert class_fields.loadClassFields() == [("CSI", "1248")]
    assert created == {"service": "ssm", "region": "us-east-2"}


def test_load_reports_missing_ssm_parameter(ssm_stub):
    stubber, _ = ssm_stub
    stubber.add_client_error("get_parameter", service_error_code="ParameterNotFound")
    with pytest.raises(ClassFieldsError, match="/neon/class_fields does not exist in us-east-2"):
        class_fields.loadClassFields()


def test_load_reports_unreadable_ssm_parameter(ssm_stub):
    stubber, _ = ssm_stub
    stubber.add_client_error("get_parameter", service_error_code="AccessDeniedException")
    with pytest.raises(ClassFieldsError, match="could not read SSM parameter /neon/class_fields.*AccessDenied"):
        class_fields.loadClassFields()


@pytest.mark.parametrize("error, name", [
    pytest.param("NoCredentialsError", "NoCredentialsError", id="no-credentials"),
    pytest.param("EndpointConnectionError", "EndpointConnectionError", id="no-network"),
])
def test_load_reports_botocore_errors_from_the_call(ssm_stub, monkeypatch, error, name):
    import botocore.exceptions
    stubber, _ = ssm_stub
    exc = getattr(botocore.exceptions, error)
    instance = exc(endpoint_url="https://ssm.us-east-2.amazonaws.com") if error == "EndpointConnectionError" else exc()
    client = boto3.client("ssm")  # the stubbed client from the fixture

    def raise_(**kwargs):
        raise instance

    monkeypatch.setattr(client, "get_parameter", raise_)
    with pytest.raises(ClassFieldsError, match=f"could not read SSM parameter /neon/class_fields: {name}"):
        class_fields.loadClassFields()


def test_load_reports_throttling(ssm_stub):
    stubber, _ = ssm_stub
    stubber.add_client_error("get_parameter", service_error_code="ThrottlingException")
    with pytest.raises(ClassFieldsError, match="could not read SSM parameter /neon/class_fields.*ThrottlingException"):
        class_fields.loadClassFields()


def test_load_reports_error_creating_the_client(monkeypatch, on_ec2):
    import botocore.exceptions

    def fail(*args, **kwargs):
        raise botocore.exceptions.ProfileNotFound(profile="missing")

    monkeypatch.setattr(boto3, "client", fail)
    with pytest.raises(ClassFieldsError, match="could not read SSM parameter /neon/class_fields: ProfileNotFound"):
        class_fields.loadClassFields()


def test_load_reports_missing_boto3(monkeypatch, on_ec2):
    monkeypatch.setitem(sys.modules, "boto3", None)  # makes `import boto3` raise ImportError
    with pytest.raises(ClassFieldsError, match="could not read SSM parameter /neon/class_fields: (Import|ModuleNotFound)Error"):
        class_fields.loadClassFields()


def test_load_reports_malformed_json_in_ssm(ssm_stub):
    stubber, _ = ssm_stub
    stubber.add_response(
        "get_parameter",
        {"Parameter": {"Name": "/neon/class_fields", "Type": "String", "Value": '{"version": 1, "fields": [["A", "1"],]}'}},
    )
    with pytest.raises(ClassFieldsError, match="SSM parameter /neon/class_fields is invalid: value is not valid JSON"):
        class_fields.loadClassFields()


def test_load_reports_non_utf8_local_file(monkeypatch, tmp_path):
    path = tmp_path / "class_fields.json"
    path.write_bytes(b"\xff\xfe{}")
    monkeypatch.setattr(sys.modules["config"], "N_classFieldsFile", str(path))
    with pytest.raises(ClassFieldsError, match="could not read N_classFieldsFile"):
        class_fields.loadClassFields()


def test_load_reports_invalid_ssm_value(ssm_stub):
    stubber, _ = ssm_stub
    stubber.add_response(
        "get_parameter",
        {"Parameter": {"Name": "/neon/class_fields", "Type": "String", "Value": value([["A", "0"]])}},
    )
    with pytest.raises(ClassFieldsError, match="SSM parameter /neon/class_fields is invalid: entry 0"):
        class_fields.loadClassFields()


def test_load_reads_local_file_from_config():
    # conftest points config.N_classFieldsFile at the fixture
    assert class_fields.loadClassFields() == [tuple(f) for f in class_fields_seed.SEED]


def test_load_resolves_relative_path_from_repo_root(monkeypatch):
    monkeypatch.setattr(
        sys.modules["config"], "N_classFieldsFile", os.path.join("tests", "fixtures", "class_fields.json")
    )
    monkeypatch.chdir(os.path.dirname(REPO_ROOT))
    assert class_fields.loadClassFields()[0] == ("Festool Domino", "440")


NOT_SET = object()


@pytest.mark.parametrize("setting, message", [
    pytest.param(NOT_SET, "N_classFieldsFile is not set in config.py", id="not-set"),
    pytest.param("", "N_classFieldsFile is not set in config.py", id="empty"),
    pytest.param("/nonexistent/class_fields.json", "could not read N_classFieldsFile", id="missing-file"),
])
def test_load_reports_bad_local_config(monkeypatch, setting, message):
    if setting is NOT_SET:
        monkeypatch.delattr(sys.modules["config"], "N_classFieldsFile")
    else:
        monkeypatch.setattr(sys.modules["config"], "N_classFieldsFile", setting)
    with pytest.raises(ClassFieldsError, match=message):
        class_fields.loadClassFields()


def test_load_reports_invalid_local_file(monkeypatch, tmp_path):
    path = tmp_path / "class_fields.json"
    path.write_text(value([["A", "1"], ["A", "2"]]))
    monkeypatch.setattr(sys.modules["config"], "N_classFieldsFile", str(path))
    with pytest.raises(ClassFieldsError, match="N_classFieldsFile is invalid: entry 1"):
        class_fields.loadClassFields()


# ============================================================================
# attendanceToTestout.py
# ============================================================================

def test_main_exits_nonzero_and_writes_nothing_when_table_is_invalid(
    monkeypatch, tmp_path, caplog, requests_mock
):
    path = tmp_path / "class_fields.json"
    path.write_text(value([["Woodshop Safety", "084"]]))
    monkeypatch.setattr(sys.modules["config"], "N_classFieldsFile", str(path))

    import attendanceToTestout
    with pytest.raises(SystemExit) as excinfo:
        attendanceToTestout.main()

    assert excinfo.value.code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "Could not load the class-to-field table" in errors[0]
    assert "entry 0" in errors[0]
    assert "No sign-offs were written" in errors[0]
    assert not requests_mock.called, "Neon should not be called without a valid table"


def test_main_exits_nonzero_when_ssm_parameter_is_missing(ssm_stub, caplog, requests_mock):
    stubber, _ = ssm_stub
    stubber.add_client_error("get_parameter", service_error_code="ParameterNotFound")

    import attendanceToTestout
    with pytest.raises(SystemExit) as excinfo:
        attendanceToTestout.main()

    assert excinfo.value.code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "/neon/class_fields does not exist" in errors[0]
    assert "No sign-offs were written" in errors[0]
    assert not requests_mock.called


def test_main_exits_nonzero_when_ssm_value_has_extra_keys(ssm_stub, caplog, requests_mock):
    stubber, _ = ssm_stub
    raw = json.dumps({"version": 1, "fields": [["A", "1"]], "comment": "x" * 5000})
    stubber.add_response(
        "get_parameter",
        {"Parameter": {"Name": "/neon/class_fields", "Type": "String", "Value": raw}},
    )

    import attendanceToTestout
    with pytest.raises(SystemExit) as excinfo:
        attendanceToTestout.main()

    assert excinfo.value.code == 1
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert 'got extra "comment"' in errors[0]
    assert "x" * 100 not in errors[0], "the ERROR line should not dump the value"
    assert not requests_mock.called


def test_main_uses_field_ids_from_the_loaded_table(monkeypatch, tmp_path, requests_mock):
    from neonUtil import N_baseURL
    from neon_mocker import NeonEventMock, NeonUserMock

    path = tmp_path / "class_fields.json"
    path.write_text(value([["Basket Weaving", "999"]]))
    monkeypatch.setattr(sys.modules["config"], "N_classFieldsFile", str(path))

    student = NeonUserMock()
    event = NeonEventMock(event_name="Basket Weaving").add_registrant(student, marked_attended=True)
    NeonEventMock.mock_events(requests_mock, [event])
    patch_mock = requests_mock.patch(f"{N_baseURL}/accounts/{student.account_id}", status_code=200)

    import attendanceToTestout
    attendanceToTestout.main()

    assert patch_mock.last_request.json()["individualAccount"]["accountCustomFields"][0]["id"] == "999"


@pytest.mark.parametrize("class_name, expected", [
    ("Woodshop Safety", ("84", "Woodshop Safety")),
    ("Metal Shop Safety & Orientation", ("520", "Metal Shop Safety")),
    # Both phrases appear; Festool Domino is earlier in the list
    ("Woodshop Safety + Festool Domino", ("440", "Festool Domino")),
    # Small Lasers comes before Laser Engrave Round in the list
    ("Laser Engrave Round on Small Lasers", ("680", "Small Lasers")),
    ("CSI: Ceramics Safety and Information", ("1248", "CSI")),
    ("Basket Weaving", (None, None)),
    # Matching is case-sensitive, as before
    ("woodshop safety", (None, None)),
])
def test_getFieldForEvent_first_phrase_in_list_order_wins(class_name, expected):
    import attendanceToTestout
    seed = [tuple(f) for f in class_fields_seed.SEED]
    assert attendanceToTestout.getFieldForEvent(class_name, seed) == expected


def test_getFieldForEvent_follows_list_order_not_name():
    import attendanceToTestout
    name = "Metal Lathe and Wood Lathe"
    assert attendanceToTestout.getFieldForEvent(name, [("Metal Lathe", "1"), ("Wood Lathe", "2")]) == ("1", "Metal Lathe")
    assert attendanceToTestout.getFieldForEvent(name, [("Wood Lathe", "2"), ("Metal Lathe", "1")]) == ("2", "Wood Lathe")


def test_getFieldForEvent_uses_table_loaded_by_main(monkeypatch):
    import attendanceToTestout
    monkeypatch.setattr(attendanceToTestout, "CLASS_FIELDS", [("Vinyl", "686")])
    assert attendanceToTestout.getFieldForEvent("Vinyl Cutter") == ("686", "Vinyl")


def _oldGetFieldForEvent(className, eventFields):
    # getFieldForEvent as it was on main before the move, verbatim
    for name, id in eventFields.items():
        if name in className:
            return id, name
    return None, None


def _parityNames():
    import random

    phrases = [p for p, _ in class_fields_seed.SEED]
    names = [
        "", " ", "CSI", "csi", "Woodshop", "Safety", "Metal Shop", "Shop Safety",
        "Metal Shop Safety", "Woodshop Safety", "Metal Shop Safety vs Woodshop Safety",
        "Woodshop Safety vs Metal Shop Safety", "CNC Router", "Tormach CNC Router",
        "CNC Router on the Tormach", "Tormach", "CNC", "Router", "cnc router",
        "WOODSHOP SAFETY", "Laser", "Lasers", "Big Laser", "Small Lasers and Big Lasers",
        "Laser Engrave Round", "Laser Engrave Rounds on Small Lasers", "Metal Lathe",
        "Wood Lathe", "Metal Lathe/Wood Lathe", "MIG/TIG Welding", "TIG Welding & MIG Welding",
        "Milling on the Tormach", "Resin and Filament", "Vinyl Sublimation",
        "Ceramics Safety (CSI)", "PHYSICS", "Orientation - Woodshop Safety",
        "Festool Domino + Shaper Origin", "Shaper Origin + Festool Domino",
        "Woodshop SafetyCSI", "xWoodshop Safetyx", "Woodshop\u00a0Safety", "Woodshop  Safety",
    ]
    names += phrases + [p.lower() for p in phrases] + [p.upper() for p in phrases]
    rng = random.Random(139)
    pieces = phrases + [w for p in phrases for w in p.split()] + ["", " ", "-", "the", "x"]
    for _ in range(3000):
        names.append(" ".join(rng.choice(pieces) for _ in range(rng.randint(0, 4))))
        names.append("".join(rng.choice(pieces) for _ in range(rng.randint(0, 3))))
    return names


def test_getFieldForEvent_matches_old_code_for_every_name():
    """Same result as the old EVENT_FIELDS dict lookup, for the real phrases and tricky names"""
    import attendanceToTestout

    oldTable = dict(class_fields_seed.SEED)
    newTable = [tuple(f) for f in class_fields_seed.SEED]
    for name in _parityNames():
        assert attendanceToTestout.getFieldForEvent(name, newTable) == _oldGetFieldForEvent(name, oldTable), name


# ============================================================================
# Seed
# ============================================================================

def test_seed_matches_old_hard_coded_table():
    """The seed is the EVENT_FIELDS dict from before the move, in the same order"""
    import ast

    try:
        source = subprocess.run(
            ["git", "show", f"{LAST_HARD_CODED_COMMIT}:attendanceToTestout.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f"git history for {LAST_HARD_CODED_COMMIT} is not available (shallow clone)")

    tree = ast.parse(source)
    table = next(
        node.value for node in tree.body
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "EVENT_FIELDS"
    )
    old = [[k.value, v.value] for k, v in zip(table.keys, table.values)]
    assert class_fields_seed.SEED == old


def test_seed_script_prints_valid_value_and_matches_fixture():
    output = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "scripts", "class_fields_seed.py")],
        capture_output=True, text=True, check=True,
    ).stdout
    assert json.loads(output) == {"version": 1, "fields": class_fields_seed.SEED}
    assert parseClassFields(output) == [tuple(f) for f in class_fields_seed.SEED]
    with open(FIXTURE, encoding="utf-8") as f:
        assert f.read() == output, "Regenerate tests/fixtures/class_fields.json from the seed script"
    # Standard-tier parameters hold up to 4 KB
    assert len(output.encode()) < 4096
