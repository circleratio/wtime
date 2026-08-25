import os
import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


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
