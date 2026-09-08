"""Rules for validating cron expressions, line by line.

Every function here is pure: given the same text it always returns the
same findings, and nothing touches the filesystem or stdout. That's what
makes the rules easy to unit test and safe to reuse from a CLI, a
pre-commit hook, or a web form.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional


class FieldSpec(NamedTuple):
    name: str
    min: int
    max: int
    names: Optional[dict]


class Finding(NamedTuple):
    line: int
    severity: str  # "error" or "warning"
    message: str


MONTH_NAMES = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Both 0 and 7 mean Sunday in the standard vixie-cron dialect.
DOW_NAMES = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}

FIELD_SPECS = (
    FieldSpec("minute", 0, 59, None),
    FieldSpec("hour", 0, 23, None),
    FieldSpec("day of month", 1, 31, None),
    FieldSpec("month", 1, 12, MONTH_NAMES),
    FieldSpec("day of week", 0, 7, DOW_NAMES),
)

KNOWN_SPECIALS = {
    "@yearly", "@annually", "@monthly", "@weekly",
    "@daily", "@midnight", "@hourly", "@reboot",
}

_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=")


def _resolve_value(token: str, spec: FieldSpec) -> Optional[int]:
    if token.isdigit():
        return int(token)
    if spec.names is not None:
        return spec.names.get(token.upper())
    return None


def _validate_item(item: str, spec: FieldSpec) -> list:
    if item == "":
        return ["empty item in list"]

    if "/" in item:
        base, _, step = item.partition("/")
        if step == "" or not step.isdigit():
            return [f"invalid step '{item}'"]
        if int(step) <= 0:
            return [f"step must be a positive integer in '{item}'"]
    else:
        base = item

    if base == "*":
        return []

    if "-" in base:
        lo_raw, _, hi_raw = base.partition("-")
        lo = _resolve_value(lo_raw, spec)
        hi = _resolve_value(hi_raw, spec)
        if lo is None or hi is None:
            return [f"invalid range '{base}'"]
        errors = []
        if not (spec.min <= lo <= spec.max):
            errors.append(f"range start {lo} out of bounds [{spec.min}-{spec.max}]")
        if not (spec.min <= hi <= spec.max):
            errors.append(f"range end {hi} out of bounds [{spec.min}-{spec.max}]")
        if not errors and lo > hi:
            errors.append(f"range start {lo} is greater than end {hi} in '{base}'")
        return errors

    val = _resolve_value(base, spec)
    if val is None:
        return [f"invalid value '{base}'"]
    if not (spec.min <= val <= spec.max):
        return [f"value {val} out of bounds [{spec.min}-{spec.max}]"]
    return []


def validate_field(value: str, spec: FieldSpec) -> list:
    """Return a list of human-readable error strings for one field value.

    Does not know about line numbers or which of the five fields it is;
    that context is added by the caller so this stays trivial to test in
    isolation.
    """
    if value == "":
        return ["field is empty"]
    errors = []
    for item in value.split(","):
        errors.extend(_validate_item(item, spec))
    return errors


def _lint_special(stripped: str, line_no: int) -> list:
    parts = stripped.split(None, 1)
    name = parts[0]
    findings = []
    if name not in KNOWN_SPECIALS:
        findings.append(Finding(line_no, "error", f"unknown special schedule '{name}'"))
    if len(parts) < 2:
        findings.append(Finding(line_no, "error", f"'{name}' is missing a command"))
    return findings


def lint_line(line: str, line_no: int) -> list:
    """Lint a single crontab line, returning zero or more findings."""
    stripped = line.strip()

    if not stripped or stripped.startswith("#"):
        return []

    if _ENV_ASSIGNMENT.match(stripped):
        return []

    if stripped.startswith("@"):
        return _lint_special(stripped, line_no)

    parts = stripped.split(None, 5)
    if len(parts) < 6:
        return [Finding(
            line_no, "error",
            f"expected 5 time fields followed by a command, found {len(parts)} field(s)",
        )]

    findings = []
    for spec, value in zip(FIELD_SPECS, parts[:5]):
        for message in validate_field(value, spec):
            findings.append(Finding(line_no, "error", f"{spec.name}: {message}"))
    return findings


def lint_text(text: str) -> list:
    """Lint a full crontab file's contents, line by line."""
    findings = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        findings.extend(lint_line(line, line_no))
    return findings
