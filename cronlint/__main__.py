"""Thin CLI wrapper around the pure linting functions in linter.py."""

import sys

from .linter import lint_text


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: python -m cronlint <crontab-file>", file=sys.stderr)
        return 2

    path = argv[1]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    findings = lint_text(text)
    for finding in findings:
        print(f"{path}:{finding.line}: {finding.severity}: {finding.message}")

    # Warnings alone don't fail the run.
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
