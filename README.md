# cronlint

Cron expressions fail silently. `60 * * * *` never runs because there is
no minute 60. `* * * 13 *` never runs because there is no month 13. Most
implementations don't warn you; they just quietly skip a schedule that
looks plausible at a glance. cronlint scans a crontab file and points out
the line where each mistake lives.

## What it checks right now

- wrong number of fields (a valid line needs 5 time fields plus a command)
- values out of range for their field (minute 0-59, hour 0-23, day of
  month 1-31, month 1-12, day of week 0-7)
- invalid ranges, like `18-5` or `10-3`
- step values that are missing, non-numeric, or zero/negative (`*/0`)
- unknown `@` shortcuts and `@daily`/`@reboot` lines missing a command
- month and day-of-week names (`MON-FRI`, `JAN-DEC`)

It skips comments, blank lines, and `NAME=value` environment assignments,
the same way real crontabs do.

## Usage

```
$ cat crontab.example
# back up the database every night
0 2 * * * /usr/local/bin/backup.sh
60 * * * * /usr/local/bin/broken.sh
30 8 * * MON-FRI /usr/local/bin/weekday-report.sh
*/0 * * * * /usr/local/bin/also-broken.sh
0 9 13 * * /usr/local/bin/fine.sh

$ python -m cronlint crontab.example
crontab.example:3: error: minute: value 60 out of bounds [0-59]
crontab.example:5: error: minute: step must be a positive integer in '*/0'
```

Or call the linter directly from Python:

```python
from cronlint import lint_text

findings = lint_text(open("crontab.example").read())
for f in findings:
    print(f.line, f.severity, f.message)
```

## Design

The rules live in `cronlint/linter.py` as plain functions with no side
effects: `validate_field` checks one field's string value against its
allowed range, `lint_line` checks one line, `lint_text` checks a whole
file. None of them touch the filesystem, so testing a rule is just
`assert validate_field("60", MINUTE_SPEC) == [...]` with no fixtures or
mocking required. The CLI in `cronlint/__main__.py` is the only part that
reads a file or prints anything.

## Status

Early skeleton. Field validation works; it does not yet catch semantic
oddities like a day-of-month and day-of-week both being restricted
(which most cron implementations OR together in a way people don't
expect), or flag schedules that will simply never fire (Feb 30th).
