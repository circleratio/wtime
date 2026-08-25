from datetime import datetime
from zoneinfo import ZoneInfo

from wtime.clock import ClockEntry
from wtime.formatter import diff_from_local, format_entry


def test_formats_local_entry_with_marker():
    dt = datetime(2026, 8, 25, 14, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    entry = ClockEntry(dt=dt, label="Asia/Tokyo", is_local=True)

    assert format_entry(entry) == "2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)"


def test_formats_non_local_entry_without_marker():
    dt = datetime(2026, 8, 25, 6, 30, 0, tzinfo=ZoneInfo("Europe/London"))
    entry = ClockEntry(dt=dt, label="Europe/London", is_local=False)

    assert format_entry(entry) == "2026-08-25(Tue) 06:30:00 +01:00 Europe/London"


def test_formats_half_hour_offset_timezone():
    dt = datetime(2026, 8, 25, 20, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    entry = ClockEntry(dt=dt, label="Asia/Kolkata", is_local=False)

    assert format_entry(entry) == "2026-08-25(Tue) 20:00:00 +05:30 Asia/Kolkata"


def test_format_entry_appends_diff_for_non_local_entry():
    dt = datetime(2026, 8, 25, 6, 30, 0, tzinfo=ZoneInfo("Europe/London"))
    entry = ClockEntry(dt=dt, label="Europe/London", is_local=False)

    assert (
        format_entry(entry, diff="-8h")
        == "2026-08-25(Tue) 06:30:00 +01:00 Europe/London (-8h)"
    )


def test_format_entry_ignores_diff_for_local_entry():
    dt = datetime(2026, 8, 25, 14, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    entry = ClockEntry(dt=dt, label="Asia/Tokyo", is_local=True)

    assert (
        format_entry(entry, diff="+0h")
        == "2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)"
    )


def test_diff_from_local_hours_only():
    local_dt = datetime(2026, 8, 25, 14, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    entry_dt = datetime(2026, 8, 25, 6, 30, 0, tzinfo=ZoneInfo("Europe/London"))
    local_entry = ClockEntry(dt=local_dt, label="Asia/Tokyo", is_local=True)
    entry = ClockEntry(dt=entry_dt, label="Europe/London", is_local=False)

    assert diff_from_local(entry, local_entry) == "-8h"


def test_diff_from_local_with_minutes():
    local_dt = datetime(2026, 8, 25, 14, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    entry_dt = datetime(2026, 8, 25, 11, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    local_entry = ClockEntry(dt=local_dt, label="Asia/Tokyo", is_local=True)
    entry = ClockEntry(dt=entry_dt, label="Asia/Kolkata", is_local=False)

    assert diff_from_local(entry, local_entry) == "-3h30m"


def test_diff_from_local_positive():
    local_dt = datetime(2026, 8, 25, 6, 30, 0, tzinfo=ZoneInfo("Europe/London"))
    entry_dt = datetime(2026, 8, 25, 14, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    local_entry = ClockEntry(dt=local_dt, label="Europe/London", is_local=True)
    entry = ClockEntry(dt=entry_dt, label="Asia/Tokyo", is_local=False)

    assert diff_from_local(entry, local_entry) == "+8h"
