# This file is auto-generated from src/wtime/ by scripts/build_portable.py.
# Do not edit directly.

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

__version__ = "0.1.0"

class UnknownTimezoneError(Exception):
    """指定されたタイムゾーン名（または都市名）が IANA tz データベースに存在しない場合に送出"""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"unknown timezone: '{name}'")

class AmbiguousTimezoneError(Exception):
    """都市名が複数のタイムゾーンにマッチした場合に送出"""

    def __init__(self, name: str, candidates: List[str]):
        self.name = name
        self.candidates = candidates
        super().__init__(f"ambiguous timezone: '{name}'")

class InvalidTimeError(Exception):
    """--time に渡された日時文字列がどのフォーマットにも一致しない場合に送出"""

    def __init__(self, value: str):
        self.value = value
        super().__init__(f"invalid time: '{value}'")

_TIME_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")

def parse_local_datetime(value: str, tz_name: str | None = None) -> datetime:
    normalized = value.replace(" ", "T", 1)
    for fmt in _TIME_FORMATS:
        try:
            naive = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if tz_name is not None:
            return naive.replace(tzinfo=ZoneInfo(tz_name))
        return naive.astimezone()
    raise InvalidTimeError(value)

@dataclass(frozen=True)
class ClockEntry:
    dt: datetime
    label: str
    is_local: bool

def resolve_local_timezone_name() -> str:
    tz_env = os.environ.get("TZ")
    if tz_env:
        try:
            ZoneInfo(tz_env)
            return tz_env
        except (ZoneInfoNotFoundError, ValueError):
            pass

    localtime_path = "/etc/localtime"
    if os.path.islink(localtime_path):
        target = os.path.realpath(localtime_path)
        marker = "zoneinfo/"
        idx = target.rfind(marker)
        if idx != -1:
            name = target[idx + len(marker):]
            try:
                ZoneInfo(name)
                return name
            except (ZoneInfoNotFoundError, ValueError):
                pass

    local_now = time.localtime()
    return time.tzname[1] if local_now.tm_isdst > 0 and len(time.tzname) > 1 else time.tzname[0]

@lru_cache(maxsize=1)
def _city_index() -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for zone in available_timezones():
        if "/" not in zone:
            continue
        city = zone.rsplit("/", 1)[1].lower()
        index.setdefault(city, []).append(zone)
    return index

def resolve_timezone_name(name: str) -> str:
    try:
        ZoneInfo(name)
        return name
    except ZoneInfoNotFoundError:
        pass

    if "/" in name:
        raise UnknownTimezoneError(name)

    key = name.replace(" ", "_").lower()
    candidates = _city_index().get(key)
    if not candidates:
        raise UnknownTimezoneError(name)
    if len(candidates) > 1:
        raise AmbiguousTimezoneError(name, sorted(candidates))
    return candidates[0]

def get_local_entry(now: datetime | None = None, tz_name: str | None = None) -> ClockEntry:
    if tz_name is not None:
        zone = ZoneInfo(tz_name)
        dt = (now or datetime.now()).astimezone(zone)
        return ClockEntry(dt=dt, label=tz_name, is_local=True)

    dt = (now or datetime.now()).astimezone()
    return ClockEntry(dt=dt, label=resolve_local_timezone_name(), is_local=True)

def get_zone_entry(name: str, now: datetime | None = None) -> ClockEntry:
    resolved_name = resolve_timezone_name(name)
    zone = ZoneInfo(resolved_name)

    dt = (now or datetime.now()).astimezone(zone)
    return ClockEntry(dt=dt, label=resolved_name, is_local=False)


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


def _timezone_error_message(exc) -> str:
    if isinstance(exc, AmbiguousTimezoneError):
        candidates = ", ".join(exc.candidates)
        return f"wtime: error: ambiguous timezone: '{exc.name}' (candidates: {candidates})"
    return f"wtime: error: unknown timezone: '{exc.name}'"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wtime",
        description="CLIの時刻表示ツール（世界時計）",
    )
    parser.add_argument(
        "timezones",
        nargs="*",
        metavar="TIMEZONE",
        help="IANAタイムゾーン名（例: Asia/Tokyo）。複数指定可",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"wtime {__version__}",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="指定した各タイムゾーンの行にローカルとの時間差を追記する",
    )
    parser.add_argument(
        "--time",
        metavar="DATETIME",
        default=None,
        help="現在時刻の代わりに基準とするローカル日時（例: 2026-08-25T14:30:00）",
    )
    parser.add_argument(
        "--set-local-tz",
        metavar="TIMEZONE",
        default=None,
        help="マシンのシステムタイムゾーンの代わりに「ローカル」として扱うタイムゾーン",
    )
    return parser

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    local_tz_name = None
    if args.set_local_tz is not None:
        try:
            local_tz_name = resolve_timezone_name(args.set_local_tz)
        except (UnknownTimezoneError, AmbiguousTimezoneError) as e:
            print(_timezone_error_message(e), file=sys.stderr)
            return 1

    base_time = None
    if args.time is not None:
        try:
            base_time = parse_local_datetime(args.time, tz_name=local_tz_name)
        except InvalidTimeError as e:
            print(f"wtime: error: invalid time: '{e.value}'", file=sys.stderr)
            return 1

    entries = []
    error_lines = []
    for name in args.timezones:
        try:
            entries.append(get_zone_entry(name, now=base_time))
        except (UnknownTimezoneError, AmbiguousTimezoneError) as e:
            error_lines.append(_timezone_error_message(e))

    if error_lines:
        for line in error_lines:
            print(line, file=sys.stderr)
        return 1

    local_entry = get_local_entry(now=base_time, tz_name=local_tz_name)
    lines = [format_entry(local_entry)]
    if args.diff:
        lines.extend(
            format_entry(entry, diff=diff_from_local(entry, local_entry))
            for entry in entries
        )
    else:
        lines.extend(format_entry(entry) for entry in entries)
    print("\n".join(lines))
    return 0

if __name__ == "__main__":
    sys.exit(main())
