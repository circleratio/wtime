import contextlib
import io
import subprocess
import sys
from pathlib import Path

from wtime import __version__
from wtime.cli import main as package_main

ROOT = Path(__file__).resolve().parent.parent
PORTABLE = ROOT / "portable" / "wtime.py"


def run_portable(args):
    result = subprocess.run(
        [sys.executable, str(PORTABLE), *args],
        capture_output=True,
        text=True,
    )
    return result.stdout, result.stderr, result.returncode


def run_package(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = package_main(args)
        except SystemExit as e:
            code = e.code
    return out.getvalue(), err.getvalue(), code


def test_no_args_prints_single_local_line():
    out, err, code = run_portable([])

    assert code == 0
    assert err == ""
    assert "(ローカル)" in out
    assert len(out.rstrip("\n").split("\n")) == 1


def test_version_matches_package_version():
    out, _, code = run_portable(["--version"])

    assert code == 0
    assert out.strip() == f"wtime {__version__}"


def test_matches_package_output_for_timezones_diff_time_and_set_local_tz():
    args = [
        "--set-local-tz",
        "Europe/London",
        "--time",
        "2026-08-25T14:30:00",
        "--diff",
        "Asia/Tokyo",
    ]

    portable_out, portable_err, portable_code = run_portable(args)
    package_out, package_err, package_code = run_package(args)

    assert portable_code == package_code == 0
    assert portable_err == package_err == ""
    assert portable_out == package_out


def test_matches_package_output_for_city_name_resolution():
    portable_out, _, portable_code = run_portable(["Tokyo", "Los Angeles"])
    package_out, _, package_code = run_package(["Tokyo", "Los Angeles"])

    assert portable_code == package_code == 0
    assert portable_out == package_out


def test_unknown_timezone_matches_package_error_and_exit_code():
    portable_out, portable_err, portable_code = run_portable(["Foo/Bar"])
    package_out, package_err, package_code = run_package(["Foo/Bar"])

    assert portable_code == package_code == 1
    assert portable_out == package_out == ""
    assert portable_err == package_err


def test_portable_file_matches_build_script_output():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import build_portable

        expected = build_portable.build()
    finally:
        sys.path.remove(str(ROOT / "scripts"))

    assert PORTABLE.read_text() == expected
