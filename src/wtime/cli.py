import argparse
import sys
from typing import Optional, Sequence

from wtime import __version__
from wtime.clock import (
    AmbiguousTimezoneError,
    InvalidTimeError,
    UnknownTimezoneError,
    get_local_entry,
    get_zone_entry,
    parse_local_datetime,
    resolve_timezone_name,
)
from wtime.formatter import diff_from_local, format_entry


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
