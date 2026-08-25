from typing import Optional

from wtime.clock import ClockEntry

_WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def format_entry(entry: ClockEntry, diff: Optional[str] = None) -> str:
    dt = entry.dt
    weekday = _WEEKDAY_ABBR[dt.weekday()]
    date_part = dt.strftime("%Y-%m-%d")
    time_part = dt.strftime("%H:%M:%S")
    offset = dt.strftime("%z")
    offset_part = f"{offset[:3]}:{offset[3:]}"

    line = f"{date_part}({weekday}) {time_part} {offset_part} {entry.label}"
    if entry.is_local:
        line += " (ローカル)"
    elif diff is not None:
        line += f" ({diff})"
    return line


def diff_from_local(entry: ClockEntry, local_entry: ClockEntry) -> str:
    delta_minutes = int(
        (entry.dt.utcoffset() - local_entry.dt.utcoffset()).total_seconds() // 60
    )
    sign = "+" if delta_minutes >= 0 else "-"
    hours, minutes = divmod(abs(delta_minutes), 60)
    if minutes:
        return f"{sign}{hours}h{minutes}m"
    return f"{sign}{hours}h"
