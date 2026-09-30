import unittest

from cronlint.linter import FIELD_SPECS, lint_line, validate_field

MINUTE = FIELD_SPECS[0]
HOUR = FIELD_SPECS[1]
DOM = FIELD_SPECS[2]
MONTH = FIELD_SPECS[3]
DOW = FIELD_SPECS[4]


class ValidateFieldTests(unittest.TestCase):
    def test_star_is_always_valid(self):
        self.assertEqual(validate_field("*", MINUTE), [])

    def test_empty_field_is_an_error(self):
        self.assertEqual(validate_field("", MINUTE), ["field is empty"])

    def test_empty_list_item_is_an_error(self):
        errors = validate_field("1,,3", MINUTE)
        self.assertEqual(errors, ["empty item in list"])

    def test_single_value_in_range(self):
        self.assertEqual(validate_field("30", MINUTE), [])
        self.assertEqual(validate_field("0", MINUTE), [])
        self.assertEqual(validate_field("59", MINUTE), [])

    def test_single_value_out_of_range(self):
        self.assertEqual(
            validate_field("60", MINUTE),
            ["value 60 out of bounds [0-59]"],
        )

    def test_non_numeric_value_without_names_is_invalid(self):
        self.assertEqual(validate_field("foo", MINUTE), ["invalid value 'foo'"])

    def test_comma_list_collects_errors_from_each_item(self):
        errors = validate_field("5,60,10", MINUTE)
        self.assertEqual(errors, ["value 60 out of bounds [0-59]"])

    def test_range_within_bounds(self):
        self.assertEqual(validate_field("1-5", HOUR), [])

    def test_range_start_greater_than_end(self):
        self.assertEqual(
            validate_field("18-5", HOUR),
            ["range start 18 is greater than end 5 in '18-5'"],
        )

    def test_range_with_out_of_bounds_ends(self):
        errors = validate_field("30-70", MINUTE)
        self.assertIn("range end 70 out of bounds [0-59]", errors)

    def test_range_with_invalid_endpoint(self):
        self.assertEqual(validate_field("1-foo", HOUR), ["invalid range '1-foo'"])

    def test_step_on_star(self):
        self.assertEqual(validate_field("*/15", MINUTE), [])

    def test_step_on_range(self):
        self.assertEqual(validate_field("1-10/2", MINUTE), [])

    def test_step_missing_value(self):
        self.assertEqual(validate_field("*/", MINUTE), ["invalid step '*/'"])

    def test_step_non_numeric(self):
        self.assertEqual(validate_field("*/x", MINUTE), ["invalid step '*/x'"])

    def test_step_zero_is_rejected(self):
        self.assertEqual(
            validate_field("*/0", MINUTE),
            ["step must be a positive integer in '*/0'"],
        )

    def test_step_negative_is_rejected(self):
        self.assertEqual(
            validate_field("*/-1", MINUTE),
            ["invalid step '*/-1'"],
        )

    def test_month_names_are_case_insensitive(self):
        self.assertEqual(validate_field("jan", MONTH), [])
        self.assertEqual(validate_field("DEC", MONTH), [])

    def test_month_name_range(self):
        self.assertEqual(validate_field("JAN-MAR", MONTH), [])

    def test_dow_names_and_sunday_alias(self):
        self.assertEqual(validate_field("SUN", DOW), [])
        self.assertEqual(validate_field("MON-FRI", DOW), [])
        self.assertEqual(validate_field("7", DOW), [])

    def test_dom_min_and_max(self):
        self.assertEqual(validate_field("1", DOM), [])
        self.assertEqual(validate_field("31", DOM), [])
        self.assertEqual(validate_field("0", DOM), ["value 0 out of bounds [1-31]"])

    def test_all_field_specs_reject_their_names_dict_leaking_into_others(self):
        self.assertEqual(validate_field("MON", MINUTE), ["invalid value 'MON'"])


class LintLineTests(unittest.TestCase):
    def test_blank_line_is_ignored(self):
        self.assertEqual(lint_line("", 1), [])
        self.assertEqual(lint_line("   ", 1), [])

    def test_comment_line_is_ignored(self):
        self.assertEqual(lint_line("# nightly backup", 1), [])

    def test_env_assignment_is_ignored(self):
        self.assertEqual(lint_line("MAILTO=root", 1), [])
        self.assertEqual(lint_line("PATH=/usr/bin:/bin", 1), [])

    def test_valid_line_has_no_findings(self):
        self.assertEqual(lint_line("0 2 * * * /usr/local/bin/backup.sh", 1), [])

    def test_wrong_field_count(self):
        findings = lint_line("* * * *", 3)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 3)
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("found 4 field(s)", findings[0].message)

    def test_out_of_range_value_is_reported_with_field_name(self):
        findings = lint_line("60 * * * * /bin/true", 5)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 5)
        self.assertEqual(findings[0].severity, "error")
        self.assertEqual(
            findings[0].message,
            "minute: value 60 out of bounds [0-59]",
        )

    def test_multiple_bad_fields_each_produce_a_finding(self):
        findings = lint_line("60 24 * 13 * /bin/true", 1)
        messages = [f.message for f in findings]
        self.assertEqual(len(findings), 3)
        self.assertTrue(any("minute" in m for m in messages))
        self.assertTrue(any("hour" in m for m in messages))
        self.assertTrue(any("month" in m for m in messages))

    def test_known_special_schedule_with_command_is_valid(self):
        self.assertEqual(lint_line("@daily /usr/local/bin/backup.sh", 1), [])

    def test_unknown_special_schedule_is_an_error(self):
        findings = lint_line("@fortnightly /usr/local/bin/backup.sh", 1)
        self.assertEqual(len(findings), 1)
        self.assertIn("unknown special schedule '@fortnightly'", findings[0].message)

    def test_special_schedule_missing_command_is_an_error(self):
        findings = lint_line("@daily", 1)
        self.assertEqual(len(findings), 1)
        self.assertIn("missing a command", findings[0].message)

    def test_day_of_week_names_in_a_full_line(self):
        self.assertEqual(
            lint_line("30 8 * * MON-FRI /usr/local/bin/weekday-report.sh", 1), []
        )

    def test_dom_and_dow_both_restricted_warns(self):
        findings = lint_line("0 9 1 * MON /bin/true", 4)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 4)
        self.assertEqual(findings[0].severity, "warning")
        self.assertIn("either matches", findings[0].message)

    def test_only_one_of_dom_or_dow_restricted_does_not_warn(self):
        self.assertEqual(lint_line("0 9 1 * * /bin/true", 1), [])
        self.assertEqual(lint_line("0 9 * * MON /bin/true", 1), [])

    def test_star_step_counts_as_unrestricted(self):
        self.assertEqual(lint_line("0 9 */2 * MON /bin/true", 1), [])

    def test_dom_dow_warning_skipped_when_fields_have_errors(self):
        findings = lint_line("0 9 32 * MON /bin/true", 1)
        self.assertEqual([f.severity for f in findings], ["error"])


if __name__ == "__main__":
    unittest.main()
