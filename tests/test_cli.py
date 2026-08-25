import re

import pytest

from wtime.cli import main
from wtime.clock import get_local_entry, get_zone_entry, parse_local_datetime
from wtime.formatter import diff_from_local, format_entry

_DIFF_SUFFIX = re.compile(r" \([+-]\d+h(\d+m)?\)$")


def test_no_args_prints_single_local_line(capsys):
    code = main([])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 1
    assert "(ローカル)" in lines[0]


def test_single_timezone_prints_two_lines(capsys):
    code = main(["Europe/London"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 2
    assert "(ローカル)" in lines[0]
    assert "Europe/London" in lines[1]


def test_multiple_timezones_preserve_order(capsys):
    code = main(["Europe/London", "Asia/Tokyo"])
    out, _ = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert len(lines) == 3
    assert "Europe/London" in lines[1]
    assert "Asia/Tokyo" in lines[2]


def test_unknown_timezone_prints_error_and_no_stdout(capsys):
    code = main(["Foo/Bar"])
    out, err = capsys.readouterr()

    assert code == 1
    assert out == ""
    assert "unknown timezone" in err
    assert "Foo/Bar" in err


def test_diff_option_appends_diff_to_timezone_lines_only(capsys):
    code = main(["--diff", "Europe/London", "Asia/Tokyo"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 3
    assert lines[0].endswith("(ローカル)")
    assert _DIFF_SUFFIX.search(lines[1])
    assert _DIFF_SUFFIX.search(lines[2])


def test_diff_option_without_timezones_prints_single_local_line(capsys):
    code = main(["--diff"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 1
    assert "(ローカル)" in lines[0]


def test_time_option_uses_specified_datetime_as_base(capsys):
    code = main(["--time", "2026-01-01T00:30:00", "Europe/London"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    base_time = parse_local_datetime("2026-01-01T00:30:00")
    expected_local = format_entry(get_local_entry(now=base_time))
    expected_zone = format_entry(get_zone_entry("Europe/London", now=base_time))

    assert code == 0
    assert err == ""
    assert lines == [expected_local, expected_zone]


def test_time_and_diff_combined_uses_offset_at_specified_moment(capsys):
    code = main(["--time", "2026-08-25T14:30:00", "--diff", "Europe/London"])
    out, _ = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    base_time = parse_local_datetime("2026-08-25T14:30:00")
    local_entry = get_local_entry(now=base_time)
    zone_entry = get_zone_entry("Europe/London", now=base_time)
    expected_diff = diff_from_local(zone_entry, local_entry)

    assert code == 0
    assert lines[1] == format_entry(zone_entry, diff=expected_diff)


def test_time_option_with_seconds_omitted_defaults_to_zero(capsys):
    code = main(["--time", "2026-08-25T14:30"])
    out, _ = capsys.readouterr()

    assert code == 0
    assert out.startswith("2026-08-25(Tue) 14:30:00")


def test_invalid_time_prints_error_and_no_stdout(capsys):
    code = main(["--time", "2026-08-25", "Europe/London"])
    out, err = capsys.readouterr()

    assert code == 1
    assert out == ""
    assert "invalid time" in err
    assert "2026-08-25" in err


def test_invalid_time_takes_precedence_over_unknown_timezone(capsys):
    code = main(["--time", "2026-08-25", "Foo/Bar"])
    out, err = capsys.readouterr()

    assert code == 1
    assert out == ""
    assert "invalid time" in err
    assert "unknown timezone" not in err


def test_city_name_resolves_to_full_iana_name(capsys):
    code = main(["Tokyo"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 2
    assert "Asia/Tokyo" in lines[1]


def test_city_name_case_and_space_insensitive(capsys):
    code = main(["tokyo", "Los Angeles"])
    out, _ = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert "Asia/Tokyo" in lines[1]
    assert "America/Los_Angeles" in lines[2]


def test_ambiguous_city_name_prints_candidates_and_no_stdout(capsys):
    code = main(["Istanbul"])
    out, err = capsys.readouterr()

    assert code == 1
    assert out == ""
    assert "ambiguous timezone" in err
    assert "Istanbul" in err
    assert "Asia/Istanbul" in err
    assert "Europe/Istanbul" in err


def test_set_local_tz_uses_specified_zone_for_local_line(capsys):
    code = main(["--set-local-tz", "Europe/London", "Asia/Tokyo"])
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert len(lines) == 2
    assert "Europe/London" in lines[0]
    assert lines[0].endswith("(ローカル)")
    assert "Asia/Tokyo" in lines[1]


def test_set_local_tz_accepts_city_name(capsys):
    code = main(["--set-local-tz", "London"])
    out, _ = capsys.readouterr()

    assert code == 0
    assert "Europe/London" in out


def test_set_local_tz_with_time_interprets_datetime_in_that_zone(capsys):
    code = main(
        ["--set-local-tz", "Europe/London", "--time", "2026-08-25T14:30:00", "--diff", "Asia/Tokyo"]
    )
    out, err = capsys.readouterr()
    lines = out.rstrip("\n").split("\n")

    assert code == 0
    assert err == ""
    assert lines[0].startswith("2026-08-25(Tue) 14:30:00 +01:00 Europe/London")
    assert lines[1].startswith("2026-08-25(Tue) 22:30:00 +09:00 Asia/Tokyo")
    assert lines[1].endswith("(+8h)")


def test_set_local_tz_invalid_value_prints_error_and_no_stdout(capsys):
    code = main(["--set-local-tz", "Foo/Bar"])
    out, err = capsys.readouterr()

    assert code == 1
    assert out == ""
    assert "unknown timezone" in err
    assert "Foo/Bar" in err


def test_version_option(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    out, _ = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "wtime" in out


def test_help_option(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    out, _ = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "usage" in out
