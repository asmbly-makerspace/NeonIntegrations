"""Class-to-field table for attendanceToTestout.py.

The table says which Neon account custom field gets a sign-off date when
someone attends a class. It lives in one SSM parameter, /neon/class_fields,
which the AsmblyMCPs account checkup tool also reads, so a new class type is
a parameter update rather than a code change. See the README for the format
and how to change it.

On EC2/Lambda the value is read from SSM. Locally and in tests it is read
from the JSON file named by `N_classFieldsFile` in config.py.
"""

import json
import os
import re

PARAMETER_NAME = "/neon/class_fields"
PARAMETER_REGION = "us-east-2"

SUPPORTED_VERSION = 1
MAX_ENTRIES = 200
MAX_PHRASE_LENGTH = 64

_WORD = r"[A-Za-z0-9&()+,./:'-]+"
PHRASE_PATTERN = re.compile(rf"{_WORD}( {_WORD})*")
FIELD_ID_PATTERN = re.compile(r"[1-9][0-9]{0,8}")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOP_LEVEL_KEYS = {"version", "fields"}

# Error messages quote a bad value, cut to this many characters so a broken
# parameter never ends up whole in the log
_MAX_QUOTE = 80


def _quote(value) -> str:
    text = json.dumps(value)
    return text if len(text) <= _MAX_QUOTE else text[: _MAX_QUOTE - 3] + "..."


class ClassFieldsError(Exception):
    """The class-to-field table could not be loaded or is invalid."""


def parseClassFields(raw: str) -> list[tuple[str, str]]:
    """Parse and validate the parameter value.

    Returns the ordered list of (class phrase, field id) pairs. Raises
    ClassFieldsError naming the first problem found; nothing is returned
    unless the whole value is valid.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, RecursionError) as e:
        raise ClassFieldsError(f"value is not valid JSON: {e}") from None

    if not isinstance(data, dict):
        raise ClassFieldsError("value must be a JSON object with 'version' and 'fields'")
    extra = sorted(set(data) - TOP_LEVEL_KEYS)
    if extra:
        raise ClassFieldsError(
            "value may only have the keys 'version' and 'fields', got extra "
            + ", ".join(_quote(key) for key in extra[:5])
            + (f" and {len(extra) - 5} more" if len(extra) > 5 else "")
        )

    version = data.get("version")
    # bool is a subclass of int in Python, so rule out `true` explicitly
    if type(version) is not int or version != SUPPORTED_VERSION:
        raise ClassFieldsError(
            f"'version' must be {SUPPORTED_VERSION}, got {_quote(version)}"
        )

    fields = data.get("fields")
    if not isinstance(fields, list):
        raise ClassFieldsError("'fields' must be a list of [phrase, field id] pairs")
    if not 1 <= len(fields) <= MAX_ENTRIES:
        raise ClassFieldsError(
            f"'fields' must have 1 to {MAX_ENTRIES} entries, got {len(fields)}"
        )

    result = []
    seen = set()
    for i, entry in enumerate(fields):
        where = f"entry {i} ({_quote(entry)})"
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or not all(isinstance(item, str) for item in entry)
        ):
            raise ClassFieldsError(f"{where} must be a list of two strings")
        phrase, fieldId = entry

        if not 1 <= len(phrase) <= MAX_PHRASE_LENGTH or not phrase.isascii():
            raise ClassFieldsError(
                f"{where}: phrase must be 1 to {MAX_PHRASE_LENGTH} ASCII characters"
            )
        if not PHRASE_PATTERN.fullmatch(phrase):
            raise ClassFieldsError(
                f"{where}: phrase may only use letters, digits, single spaces "
                "between words and & ( ) + , . / : ' -"
            )
        if not FIELD_ID_PATTERN.fullmatch(fieldId):
            raise ClassFieldsError(
                f"{where}: field id must be 1 to 9 digits with no leading zero"
            )
        if phrase in seen:
            raise ClassFieldsError(f"{where}: phrase {json.dumps(phrase)} appears more than once")
        seen.add(phrase)
        result.append((phrase, fieldId))

    return result


def _readFromSsm() -> str:
    # Everything from importing boto3 to reading the value is inside the try,
    # so a missing package, bad AWS config, missing credentials or throttling
    # all end as one ClassFieldsError rather than a traceback
    try:
        import boto3

        client = boto3.client("ssm", region_name=PARAMETER_REGION)
        try:
            response = client.get_parameter(Name=PARAMETER_NAME)
        except client.exceptions.ParameterNotFound:
            raise ClassFieldsError(
                f"SSM parameter {PARAMETER_NAME} does not exist in {PARAMETER_REGION}"
            ) from None
        value = response["Parameter"]["Value"]
    except ClassFieldsError:
        raise
    except Exception as e:
        raise ClassFieldsError(
            f"could not read SSM parameter {PARAMETER_NAME}: {type(e).__name__}: {e}"
        ) from None
    return value


def _readFromLocalFile() -> str:
    try:
        import config
    except ImportError:
        raise ClassFieldsError("config.py not found, so N_classFieldsFile is not set") from None

    path = getattr(config, "N_classFieldsFile", None)
    if not isinstance(path, str) or not path:
        raise ClassFieldsError(
            "N_classFieldsFile is not set in config.py. Point it at a JSON file, "
            "e.g. one made with `python scripts/class_fields_seed.py > private/class_fields.json`"
        )
    if not os.path.isabs(path):
        path = os.path.join(_REPO_ROOT, path)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise ClassFieldsError(f"could not read N_classFieldsFile {path}: {e}") from None


def _runningInAws() -> bool:
    # Same check the scripts use to pick aws_ssm over config.py
    return os.environ.get("USER") == "ec2-user" or bool(os.environ.get("LAMBDA_TASK_ROOT"))


def loadClassFields() -> list[tuple[str, str]]:
    """Read and validate the table from SSM (EC2/Lambda) or the local file."""
    if _runningInAws():
        source = f"SSM parameter {PARAMETER_NAME}"
        raw = _readFromSsm()
    else:
        source = "N_classFieldsFile"
        raw = _readFromLocalFile()
    try:
        return parseClassFields(raw)
    except ClassFieldsError as e:
        raise ClassFieldsError(f"{source} is invalid: {e}") from None
