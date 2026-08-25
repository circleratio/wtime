from datetime import datetime, timezone

import pytest

from wtime.clock import (
    AmbiguousTimezoneError,
    ClockEntry,
    InvalidTimeError,
    UnknownTimezoneError,
    get_local_entry,
    get_zone_entry,
    parse_local_datetime,
    resolve_local_timezone_name,
    resolve_timezone_name,
)


def test_valid_timezone_returns_entry():
    now = datetime(2026, 8, 25, 5, 30, tzinfo=timezone.utc)
    entry = get_zone_entry("Asia/Tokyo", now=now)

    assert isinstance(entry, ClockEntry)
    assert entry.label == "Asia/Tokyo"
    assert entry.is_local is False
    assert entry.dt.hour == 14  # UTC+9


def test_unknown_timezone_raises():
    with pytest.raises(UnknownTimezoneError) as exc_info:
        get_zone_entry("Foo/Bar")
    assert exc_info.value.name == "Foo/Bar"


def test_get_local_entry_returns_local_entry():
    entry = get_local_entry()

    assert isinstance(entry, ClockEntry)
    assert entry.is_local is True
    assert isinstance(entry.label, str)
    assert entry.label


def test_resolve_local_timezone_name_never_raises_and_returns_nonempty_string():
    name = resolve_local_timezone_name()

    assert isinstance(name, str)
    assert name


def test_parse_local_datetime_accepts_t_and_space_separated_equally():
    from_t = parse_local_datetime("2026-08-25T14:30:00")
    from_space = parse_local_datetime("2026-08-25 14:30:00")

    assert from_t == from_space
    assert (from_t.year, from_t.month, from_t.day) == (2026, 8, 25)
    assert (from_t.hour, from_t.minute, from_t.second) == (14, 30, 0)
    assert from_t.tzinfo is not None


def test_parse_local_datetime_defaults_seconds_to_zero_when_omitted():
    dt = parse_local_datetime("2026-08-25T14:30")

    assert dt.second == 0
    assert (dt.hour, dt.minute) == (14, 30)


def test_parse_local_datetime_raises_on_date_only():
    with pytest.raises(InvalidTimeError) as exc_info:
        parse_local_datetime("2026-08-25")
    assert exc_info.value.value == "2026-08-25"


def test_parse_local_datetime_raises_on_malformed_input():
    with pytest.raises(InvalidTimeError):
        parse_local_datetime("not-a-datetime")


def test_resolve_timezone_name_returns_full_iana_name_unchanged():
    assert resolve_timezone_name("Europe/London") == "Europe/London"
    assert resolve_timezone_name("UTC") == "UTC"


def test_resolve_timezone_name_resolves_city_name_case_insensitively():
    assert resolve_timezone_name("Tokyo") == "Asia/Tokyo"
    assert resolve_timezone_name("tokyo") == "Asia/Tokyo"
    assert resolve_timezone_name("TOKYO") == "Asia/Tokyo"


def test_resolve_timezone_name_resolves_space_separated_city_name():
    assert resolve_timezone_name("Los Angeles") == "America/Los_Angeles"


def test_resolve_timezone_name_raises_on_unknown_city():
    with pytest.raises(UnknownTimezoneError) as exc_info:
        resolve_timezone_name("Nowhereville")
    assert exc_info.value.name == "Nowhereville"


def test_resolve_timezone_name_does_not_fall_back_to_city_lookup_for_slashed_input():
    with pytest.raises(UnknownTimezoneError) as exc_info:
        resolve_timezone_name("Foo/Bar")
    assert exc_info.value.name == "Foo/Bar"


def test_resolve_timezone_name_raises_ambiguous_error_with_sorted_candidates():
    with pytest.raises(AmbiguousTimezoneError) as exc_info:
        resolve_timezone_name("Istanbul")
    assert exc_info.value.name == "Istanbul"
    assert exc_info.value.candidates == ["Asia/Istanbul", "Europe/Istanbul"]


def test_get_local_entry_with_tz_name_overrides_system_timezone():
    now = datetime(2026, 8, 25, 5, 30, tzinfo=timezone.utc)
    entry = get_local_entry(now=now, tz_name="Europe/London")

    assert entry.is_local is True
    assert entry.label == "Europe/London"
    assert (entry.dt.hour, entry.dt.minute) == (6, 30)  # BST: UTC+1


def test_parse_local_datetime_with_tz_name_interprets_as_that_zones_wall_clock():
    summer = parse_local_datetime("2026-08-25T14:30:00", tz_name="Europe/London")
    winter = parse_local_datetime("2026-01-01T00:30:00", tz_name="Europe/London")

    assert summer.utcoffset().total_seconds() == 3600  # BST
    assert winter.utcoffset().total_seconds() == 0  # GMT
    assert (summer.hour, summer.minute) == (14, 30)
    assert (winter.hour, winter.minute) == (0, 30)
