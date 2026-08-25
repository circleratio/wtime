# wtime 設計書

`doc/requirement.md` の要求仕様に基づく実装設計。実装言語は Python（標準ライブラリの `zoneinfo` を使用するため Python 3.9 以降が前提）。

# 1. ディレクトリ構成

```
wtime/
├── pyproject.toml
├── src/
│   └── wtime/
│       ├── __init__.py      # __version__ の定義のみ
│       ├── __main__.py      # `python -m wtime` 用エントリポイント
│       ├── cli.py           # 引数解析・全体制御（main関数）
│       ├── clock.py         # 時刻取得・タイムゾーン解決
│       └── formatter.py     # 出力文字列の整形
├── scripts/
│   └── build_portable.py   # src/wtime/ から portable/wtime.py を生成する
├── portable/
│   └── wtime.py             # 生成物。pip install 不要で動く単一ファイル版
├── tests/
│   ├── test_cli.py
│   ├── test_clock.py
│   ├── test_formatter.py
│   └── test_portable.py
└── doc/
    ├── requirement.md
    └── spec.md
```

- `src` レイアウトを採用し、パッケージを `pip install` した状態でテストすることで import 漏れ等の事故を防ぐ。
- 外部依存ライブラリは追加しない（標準ライブラリのみで完結させる）。

# 2. モジュール設計

## 2.1 `wtime/__init__.py`
- `__version__ = "0.1.0"` を定義する。`cli.py` の `--version` から参照する唯一のソースとする。

## 2.2 `wtime/clock.py`
時刻取得とタイムゾーン名の解決を担当する。CLI・整形処理から独立させ、単体テストしやすくする。

```python
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

class UnknownTimezoneError(Exception):
    """指定されたタイムゾーン名（または都市名）が IANA tz データベースに存在しない場合に送出"""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"unknown timezone: '{name}'")

class AmbiguousTimezoneError(Exception):
    """都市名が複数のタイムゾーンにマッチした場合に送出"""
    def __init__(self, name: str, candidates: list[str]):
        self.name = name
        self.candidates = candidates
        super().__init__(f"ambiguous timezone: '{name}'")

class InvalidTimeError(Exception):
    """--time に渡された日時文字列がどのフォーマットにも一致しない場合に送出"""
    def __init__(self, value: str):
        self.value = value
        super().__init__(f"invalid time: '{value}'")

@dataclass(frozen=True)
class ClockEntry:
    dt: datetime      # tzinfo 付きの現在時刻（または --time で指定された基準時刻）
    label: str        # 表示用タイムゾーン名（例: "Asia/Tokyo"）
    is_local: bool     # ローカルタイムかどうか

def get_local_entry(now: datetime | None = None, tz_name: str | None = None) -> ClockEntry: ...
def get_zone_entry(name: str, now: datetime | None = None) -> ClockEntry: ...
def resolve_local_timezone_name() -> str: ...
def resolve_timezone_name(name: str) -> str: ...
def parse_local_datetime(value: str, tz_name: str | None = None) -> datetime: ...
```

- `now` 引数は基準時刻を外部から注入できるようにするためのもの。テスト時の固定時刻検証だけでなく、`--time` 指定時に `cli.py` から解析済みの基準時刻を渡す経路としても使う。省略時は現在時刻を使用する。
- `get_zone_entry(name)` は内部でまず `resolve_timezone_name(name)` を呼んでIANAの正式名を確定し、その名前で `ClockEntry.label` を組み立てる（都市名だけの指定でも `label` には解決後のフルのIANA名が入る。詳細は次項）。
- `resolve_local_timezone_name()` はローカルタイムゾーンの IANA 名（例: `Asia/Tokyo`）を解決する。
- `get_local_entry()` の `tz_name` 引数は `--set-local-tz` によるローカルタイムゾーンの上書き先（解決済みのフルIANA名）を渡すためのもの。`None`（デフォルト）なら従来通りマシンのシステムタイムゾーンを使う（詳細は後述）。
- `parse_local_datetime(value)` は `--time` の引数文字列を、tzinfo 付き `datetime` に変換する。`tz_name` を渡すとそのタイムゾーンの壁時計時刻として解釈し、`None`（デフォルト）ならマシンのシステムタイムゾーンとして解釈する（詳細は後述）。

### ローカルタイムゾーン名の解決方法
Python 標準の `datetime.now().astimezone()` は正しい UTC オフセットを返すが、tzinfo に IANA 名は保持されない（環境によっては `JST` のような略称のみ）。そのため以下の優先順で解決する。

1. 環境変数 `TZ` が設定されていれば、その値をタイムゾーン名として採用する（`ZoneInfo(TZ)` で妥当性を検証）。
2. Linux/macOS では `/etc/localtime` がタイムゾーンデータファイルへのシンボリックリンクになっている場合が多いため、リンク先パスから `zoneinfo/` 以降の部分（例: `Asia/Tokyo`）を抽出する。
3. 上記いずれでも解決できない場合は、`time.tzname` が返すローカルの略称（例: `JST`）をそのまま表示名として使用する（IANA 名ではない点をフォールバックとして許容する）。

この関数は例外を送出しない（最終フォールバックとして必ず何らかの文字列を返す）。

### `--set-local-tz` によるローカルタイムゾーンの上書き（`get_local_entry`）

```python
def get_local_entry(now: datetime | None = None, tz_name: str | None = None) -> ClockEntry:
    if tz_name is not None:
        zone = ZoneInfo(tz_name)
        dt = (now or datetime.now()).astimezone(zone)
        return ClockEntry(dt=dt, label=tz_name, is_local=True)

    dt = (now or datetime.now()).astimezone()
    return ClockEntry(dt=dt, label=resolve_local_timezone_name(), is_local=True)
```

- `tz_name` には `cli.py` が `--set-local-tz` の値を `resolve_timezone_name()` で解決済みのフルIANA名を渡す（`get_local_entry()` 自身は都市名解決や不正値のエラー処理を行わない。呼び出し側の責務とする）。
- `tz_name` が指定された場合、`resolve_local_timezone_name()`（マシンのシステムタイムゾーン解決）は呼ばれず、`label` にはそのまま `tz_name` が入る。「ローカル」行は `is_local=True` のまま変わらないため、`formatter.py` 側の変更は不要（`(ローカル)` 表記や `--diff` の基準計算はそのまま動く）。
- `now` が指定されている場合（`--time` 併用時）、`(now or datetime.now())` は既に正しいUTC実体（aware datetime）を指しているため、`.astimezone(zone)` は単に表示用タイムゾーンへの変換として働く。`tz_name` 未指定時の `.astimezone()`（引数なし）との対称性を保っている。

### 都市名だけの指定の解決（`resolve_timezone_name`）

`doc/requirement.md` の仕様（`/` を含まない入力のみ都市名として解決を試みる、完全一致・大文字小文字無視、アンダースコアとスペースを同一視、複数一致は曖昧エラー）を満たすため、以下の手順で解決する。

```python
from functools import lru_cache
from zoneinfo import available_timezones

@lru_cache(maxsize=1)
def _city_index() -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for zone in available_timezones():
        if "/" not in zone:
            continue
        city = zone.rsplit("/", 1)[1].lower()
        index.setdefault(city, []).append(zone)
    return index

def resolve_timezone_name(name: str) -> str:
    try:
        ZoneInfo(name)
        return name  # 既存の完全なIANA名（"UTC"のようなスラッシュなしの名前も含む）
    except ZoneInfoNotFoundError:
        pass

    if "/" in name:
        raise UnknownTimezoneError(name)  # スラッシュを含む入力は都市名解決の対象外

    key = name.replace(" ", "_").lower()
    candidates = _city_index().get(key)
    if not candidates:
        raise UnknownTimezoneError(name)
    if len(candidates) > 1:
        raise AmbiguousTimezoneError(name, sorted(candidates))
    return candidates[0]
```

- まず入力をそのまま `ZoneInfo()` に渡し、既存の完全一致（`Europe/London` や `UTC` のようなスラッシュなしの正式名も含む）を優先する。これにより既存の挙動（フルのIANA名指定）に一切影響しない。
- 完全一致しない場合、入力に `/` が含まれていれば都市名解決の対象外として即座に `UnknownTimezoneError` を送出する（要求仕様通り）。
- `/` を含まない場合のみ、`available_timezones()` から作った「都市名（小文字）→ 一致するIANA名のリスト」のインデックスを参照する。入力のスペースはアンダースコアに正規化してから小文字化して照合する。
- `available_timezones()` はファイルシステムを走査するため呼び出しコストがあり、複数のタイムゾーン引数を都市名で指定した場合に毎回スキャンし直すのは無駄になる。そのため `_city_index()` を `functools.lru_cache` でプロセス内キャッシュし、初回呼び出し時にのみ構築する。
- 一致が0件なら `UnknownTimezoneError`、2件以上なら `AmbiguousTimezoneError(name, 候補のソート済みリスト)` を送出する。候補の順序を安定させるため、返す前にソートする（`available_timezones()` は `set` を返すため順序が不定なため）。
- 一致が1件ならその正式なIANA名を返す。

### `--time` の日時文字列パース（`parse_local_datetime`）

`doc/requirement.md` の仕様（T区切り／スペース区切りの両方を許容、秒省略可、日付のみは不可）を満たすため、以下の手順で解析する。

```python
_TIME_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")

def parse_local_datetime(value: str, tz_name: str | None = None) -> datetime:
    normalized = value.replace(" ", "T", 1)  # スペース区切りをT区切りに正規化
    for fmt in _TIME_FORMATS:
        try:
            naive = datetime.strptime(normalized, fmt)
        except ValueError:
            continue
        if tz_name is not None:
            return naive.replace(tzinfo=ZoneInfo(tz_name))  # 指定タイムゾーンの壁時計時刻として解釈
        return naive.astimezone()  # naiveな datetime を「システムのローカルタイム」とみなしtzinfoを付与
    raise InvalidTimeError(value)
```

- 入力文字列に含まれる最初の1個の半角スペースだけを `T` に置き換えることで、`"2026-08-25 14:30:00"` と `"2026-08-25T14:30:00"` を同じパース処理に統一する。
- `tz_name` が指定された場合（`--set-local-tz` 併用時）は、`naive.replace(tzinfo=ZoneInfo(tz_name))` によって「その日時をそのタイムゾーンの壁時計時刻として解釈する」。`zoneinfo.ZoneInfo` は（`pytz` と異なり）`replace(tzinfo=...)` で正しくDSTを含むオフセットを解決できるため、この方法で問題ない。
- `tz_name` が指定されていない場合は従来通り `datetime.astimezone()` を使う。「self が naive の場合、システムのローカルタイムを表しているとみなして aware に変換する」という標準ライブラリの挙動を利用しており、これは `get_local_entry()` が現在時刻を取得する際に使っている変換方法と同じ。
- いずれの経路でも、得られる `datetime` は正しいUTC実体を指す aware な値になるため、`--time` を指定してもしなくても（`--set-local-tz` を指定してもしなくても）以降の処理（`get_local_entry`/`get_zone_entry` への `now` の受け渡し）を統一的に扱える。
- どちらの書式にもマッチしない場合（日付のみ、書式崩れ、存在しない日付など）は `InvalidTimeError` を送出する。`tz_name` の妥当性検証はこの関数の責務ではない（呼び出し側が `resolve_timezone_name()` で事前に解決済みの値を渡す）。

## 2.3 `wtime/formatter.py`
`ClockEntry` を要求仕様のフォーマット文字列に変換する。

```python
from wtime.clock import ClockEntry

_WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

def format_entry(entry: ClockEntry, diff: str | None = None) -> str: ...
def diff_from_local(entry: ClockEntry, local_entry: ClockEntry) -> str: ...
```

- 出力形式: `YYYY-MM-DD(曜日) HH:MM:SS ±HH:MM タイムゾーン名`
  - 例: `2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo`
- ローカルタイムの行のみ末尾に ` (ローカル)` を付与する。
  - 例: `2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)`
- `diff` を渡した場合（`--diff` 指定時の非ローカル行）は末尾に ` ({diff})` を付与する。`entry.is_local` が真の場合は `diff` の値に関わらず付与しない（ローカル行は常に `(ローカル)` 表記を優先する）。ローカル表記と差分表記は同じ末尾の1スロットを共有し、両方が同時に出ることはない。
  - 例: `2026-08-25(Tue) 06:30:00 +01:00 Europe/London (-8h)`
- 曜日表記はロケール非依存にするため `datetime.strftime("%a")` は使わず、`_WEEKDAY_ABBR[dt.weekday()]` による固定の英語表記を用いる（実行環境のロケール設定に出力が左右されないようにするため）。
- UTC オフセットは `dt.strftime("%z")`（`+0900` 形式）を取得し、`+09:00` の形にコロンを挿入して整形する。

### 時間差（`diff_from_local`）の仕様
- `entry.dt.utcoffset() - local_entry.dt.utcoffset()` を分単位の整数に変換し、符号付きの `+Hh` / `-Hh` / `+HhMm` / `-HhMm` 形式に整形する（`H` は時間、`M` は分の絶対値。分が0のときは分部分を省略する）。
  - 例: 差が -480分 → `-8h`、差が -210分 → `-3h30m`
- 符号は「`entry` が `local_entry` よりどれだけ進んでいるか」を表す（対象の方が時刻が進んでいれば `+`、遅れていれば `-`）。
- `utcoffset()` は両エントリとも `datetime.now()` 由来の tzinfo 付き `datetime` から取得するため、DST（サマータイム）を含めた実際の時差がそのまま反映される。
- この関数はローカル行自身には使用しない（呼び出し側の `cli.py` がローカル行を除外して呼び出す）。

## 2.4 `wtime/cli.py`
引数解析と全体の制御フロー、標準出力・標準エラー出力への書き込みを担当する。

```python
import argparse
import sys
from wtime import __version__
from wtime.clock import (
    get_local_entry,
    get_zone_entry,
    parse_local_datetime,
    resolve_timezone_name,
    AmbiguousTimezoneError,
    InvalidTimeError,
    UnknownTimezoneError,
)
from wtime.formatter import format_entry, diff_from_local

def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> int: ...
```

- `build_parser()`
  - `prog="wtime"`
  - 位置引数 `timezones`: `nargs="*"`, `metavar="TIMEZONE"`、複数指定可、ヘルプに `Asia/Tokyo` 等の例を記載
  - `--version`: `action="version"`, `version=f"wtime {__version__}"`
  - `--diff`: `action="store_true"`、指定した各タイムゾーンの行にローカルとの時間差を追記する
  - `--time`: `metavar="DATETIME"`、デフォルト `None`。基準時刻を文字列のまま受け取り、`main()` 内で `parse_local_datetime()` により解析する（`argparse` の `type=` では例外メッセージが argparse 標準の形式になってしまうため使わず、`main()` 側で捕捉して `wtime: error: ...` 形式に統一する）
  - `--set-local-tz`: `metavar="TIMEZONE"`、デフォルト `None`。値は文字列のまま受け取り、`main()` 内で `resolve_timezone_name()` により解決する
  - `--help` は `argparse` の標準機能により自動的に提供される
- `_timezone_error_message(exc: UnknownTimezoneError | AmbiguousTimezoneError) -> str` というヘルパー関数を用意し、`UnknownTimezoneError`/`AmbiguousTimezoneError` からエラーメッセージ文字列を組み立てる処理を共通化する（後述のエラーメッセージフォーマットを1箇所で管理し、タイムゾーン引数のループと `--set-local-tz` の検証の両方から呼び出す）。
- `main(argv)` の処理フロー:
  1. `build_parser().parse_args(argv)` で引数解析（不正なオプション指定時は argparse が終了コード `2` で終了）
  2. `args.set_local_tz` が指定されていれば `resolve_timezone_name(args.set_local_tz)` を試みる。`UnknownTimezoneError`/`AmbiguousTimezoneError` が送出された場合は、通常出力は一切行わず `_timezone_error_message()` の結果を標準エラー出力に書き、`main()` は `1` を返す（`--time` の検証やタイムゾーン引数の検証には進まない）。解決できた場合はその値を `local_tz_name` とする（未指定時は `None`）
  3. `args.time` が指定されていれば `parse_local_datetime(args.time, tz_name=local_tz_name)` を試みる。`InvalidTimeError` が送出された場合は、通常出力は一切行わず `wtime: error: invalid time: '<value>'` を標準エラー出力に書き、`main()` は `1` を返す（タイムゾーン引数の検証には進まない）
  4. 解析できた場合（または `--time` 未指定の場合）、その値を `base_time`（未指定時は `None`）として、指定されたタイムゾーン名すべてを `get_zone_entry(name, now=base_time)` で解決を試みる
     - **1つでも解決に失敗すれば、通常出力は一切行わず**、失敗した項目ごとに `_timezone_error_message()` でエラーメッセージを組み立てて標準エラー出力に書き出し、`main()` は `1` を返す（下記フォーマット参照）。`UnknownTimezoneError` と `AmbiguousTimezoneError` の両方をこのループで捕捉する
  5. 全て解決できた場合、`get_local_entry(now=base_time, tz_name=local_tz_name)` でローカル時刻のエントリを取得する
  6. `args.diff` が真の場合、各タイムゾーンのエントリごとに `diff_from_local(entry, local_entry)` で差分文字列を計算し、`format_entry(entry, diff=...)` に渡す。偽の場合は従来通り `format_entry(entry)` を呼ぶ（`--diff` はタイムゾーン未指定でも単に効果を持たないだけでエラーにはしない）
  7. ローカル時刻のエントリ（`format_entry(local_entry)`、diffは常に渡さない）を先頭に、指定順の各タイムゾーンのエントリを続けて標準出力に1行ずつ出力し、`main()` は `0` を返す
- エントリポイント `__main__.py` および `pyproject.toml` の `[project.scripts]` はいずれも `sys.exit(main())` 相当の呼び出しを行う。
- 検証の順序は `--set-local-tz` → `--time` → タイムゾーン引数、の順に固定する。`--time` の解釈が `--set-local-tz` の結果に依存するため、この順序でなければならない。複数の段階でエラーが起きても最初に検出された段階のエラーのみが報告される（すべてのエラーをまとめて報告する複雑さを避けるための設計判断。既存の「`--time` と不正なタイムゾーン名の同時指定」の扱いと同じ考え方を踏襲する）。

### エラーメッセージフォーマット
```
wtime: error: unknown timezone: 'Foo/Bar'
```
複数不正な場合は行ごとに列挙する:
```
wtime: error: unknown timezone: 'Foo/Bar'
wtime: error: unknown timezone: 'Baz/Qux'
```
都市名が複数のタイムゾーンにマッチした場合（候補はカンマ区切りでソート済みのIANA名を列挙する）:
```
wtime: error: ambiguous timezone: 'Istanbul' (candidates: Asia/Istanbul, Europe/Istanbul)
```
`--time` が不正な場合:
```
wtime: error: invalid time: '2026-08-25'
```

# 3. CLI仕様まとめ

| 項目 | 内容 |
|---|---|
| コマンド名 | `wtime` |
| 引数なし | ローカル時刻のみ1行出力 |
| `wtime TZ [TZ...]` | ローカル時刻 + 指定タイムゾーンの時刻を指定順に出力（複数可） |
| `TZ` に都市名のみ指定（`/`を含まない） | IANA名の都市部分と完全一致・大文字小文字無視で解決する。一致0件は不正なタイムゾーン名と同じ扱い、一致2件以上は曖昧エラー |
| `--help` | 使いかたを表示して終了コード `0` |
| `--version` | `wtime <バージョン>` を表示して終了コード `0` |
| `--diff` | 指定した各タイムゾーンの行末に `(+9h)` 等のローカルとの時間差を追記する。タイムゾーン未指定時は無効果（エラーにしない） |
| `--time DATETIME` | 現在時刻の代わりに指定したローカル日時を基準に表示・`--diff`計算を行う。`T`区切り／スペース区切り、秒省略可 |
| `--set-local-tz TIMEZONE` | マシンのシステムタイムゾーンの代わりに指定したタイムゾーンを「ローカル」として扱う。フルIANA名・都市名の両方を受け付ける |
| 不正なタイムゾーン名 | 標準エラー出力にエラーメッセージ、終了コード `1` |
| 都市名が複数タイムゾーンに一致（曖昧） | 標準エラー出力に候補付きエラーメッセージ、終了コード `1` |
| 不正な `--time` の形式 | 標準エラー出力にエラーメッセージ、終了コード `1`（`--set-local-tz` の検証より後、タイムゾーン引数の検証より先に判定） |
| 不正な `--set-local-tz` の値 | 標準エラー出力にエラーメッセージ、終了コード `1`（他のどの検証よりも先に判定） |
| 引数解析エラー（不明なオプション等） | argparse標準の使い方メッセージ、終了コード `2` |

# 4. パッケージング

- `pyproject.toml`（setuptools バックエンド、`src` レイアウト）
- `[project.scripts]` に `wtime = "wtime.cli:main"` を登録し、`pip install .` 後に `wtime` コマンドとして実行可能にする
- `requires-python = ">=3.9"`（`zoneinfo` モジュールの下限）
- バージョン番号は `wtime/__init__.py` の `__version__` を単一のソースとし、`pyproject.toml` 側は動的取得（`dynamic = ["version"]` + `[tool.setuptools.dynamic]`）とする

# 4.1 ポータブル版（単一ファイル）のビルド

`pip install` できない環境向けに、`src/wtime/` の実装から単一ファイル `portable/wtime.py` を自動生成する。

- 生成スクリプト: `scripts/build_portable.py`（標準ライブラリのみで実装。import文の位置特定には `ast.parse` を使い、それ以外のコード本体の抽出・結合はソーステキストのスライスをそのまま連結するテキスト処理で行う）
  - 結合順序: `clock.py` → `formatter.py` → `cli.py` → `__main__.py` 相当の起動処理
  - 各モジュール内の `from wtime.xxx import ...` / `from wtime import __version__` という自モジュール間 import 文を除去する（結合後は同一ファイル内にすべてのシンボルが存在するため不要になる）
  - 標準ライブラリの import文（`argparse`, `sys`, `os`, `time`, `dataclasses`, `datetime`, `functools`, `typing`, `zoneinfo` 等）は各モジュールから集約する。同一モジュールからの `from X import a, b` は名前をマージして1行にまとめ、生成ファイル先頭で重複なくソート済みで記述する
  - `wtime/__init__.py` の `__version__ = "0.1.0"` をそのまま生成ファイル先頭のモジュール定数として埋め込む（バージョンのソースは変わらず `src/wtime/__init__.py` のまま。生成スクリプトがそこから読み取って埋め込む）
  - ファイル末尾に `if __name__ == "__main__": sys.exit(main())` を付与する
  - 生成ファイル先頭に `# This file is auto-generated from src/wtime/ by scripts/build_portable.py. Do not edit directly.` というコメント（英語、CLAUDE.mdの規約に従う）を付け、直接編集されることを防ぐ
- 実行方法: `python3 scripts/build_portable.py`（引数なし、`portable/wtime.py` を上書き生成する）
- `portable/wtime.py` はリポジトリにコミットする生成物とする（利用者が `git clone` 直後に `pip install` なしですぐ使えるようにするため）。`src/wtime/` を変更した場合は必ずビルドスクリプトを再実行し、生成物を最新化してからコミットする
- ポータブル版は外部依存を追加しないため、生成後の単一ファイルも標準ライブラリのみで完結する

# 5. テスト方針（pytest）

- `test_clock.py`
  - `get_local_entry()` / `get_zone_entry()` が固定の `now` を渡した場合に期待通りの `ClockEntry` を返すこと
  - 存在しないタイムゾーン名を渡すと `UnknownTimezoneError` が送出されること
  - `resolve_local_timezone_name()` が例外を送出せず何らかの文字列を返すこと
  - `parse_local_datetime()` が `T`区切り・スペース区切りの両方を解析できること
  - `parse_local_datetime()` が秒を省略した入力（00秒として扱われる）を解析できること
  - `parse_local_datetime()` が日付のみの入力・書式崩れの入力に対して `InvalidTimeError` を送出すること
  - `resolve_timezone_name()` が完全なIANA名（`Europe/London`、`UTC`）をそのまま返すこと
  - `resolve_timezone_name()` が都市名（大文字小文字混在）を正しいIANA名に解決すること
  - `resolve_timezone_name()` がスペース入りの都市名（例: `"Los Angeles"`）をアンダースコア入りのIANA名に解決すること
  - `resolve_timezone_name()` が一致しない都市名に対して `UnknownTimezoneError` を送出すること
  - `resolve_timezone_name()` が `/` を含むが存在しない入力に対して都市名解決を試みず `UnknownTimezoneError` を送出すること
  - `resolve_timezone_name()` が複数一致する都市名（`Istanbul`）に対して `AmbiguousTimezoneError` を送出し、`candidates` にソート済みの一致IANA名一覧が入ること
  - `get_local_entry(tz_name="Europe/London")` が、マシンのシステムタイムゾーンに関わらず `Europe/London` の時刻・ラベルで `ClockEntry` を返すこと
  - `parse_local_datetime(value, tz_name="Europe/London")` が、値をシステムタイムゾーンではなく指定したタイムゾーンの壁時計時刻として解釈すること（DSTを跨ぐ日付で夏時間・冬時間それぞれ検証する）
- `test_formatter.py`
  - 固定の `ClockEntry` から期待通りのフォーマット文字列（曜日・UTCオフセット・ローカル表記）が得られること
  - オフセットが負値・分単位のタイムゾーン（例: `Asia/Kolkata` の `+05:30`）でも正しく整形されること
  - `format_entry(entry, diff="-8h")` のように `diff` を渡すと末尾に `(-8h)` が付与されること
  - `is_local=True` のエントリに `diff` を渡しても `(ローカル)` が優先され、diffは無視されること
  - `diff_from_local()` が時間のみの差（例: `+9h`）・分を含む差（例: `-3h30m`）・負の差の両方を正しく計算すること
- `test_cli.py`（`capsys` で標準出力/標準エラー出力を検証）
  - 引数なし実行でローカル時刻の1行のみ出力され、終了コードが `0` であること
  - 単一タイムゾーン指定で2行出力されること
  - 複数タイムゾーン指定で `N+1` 行、指定順に出力されること
  - 不正なタイムゾーン指定時、標準出力が空であり、標準エラー出力にエラーメッセージが出力され、戻り値が `1` であること
  - `--version` 実行時に `wtime <バージョン>` が出力され、戻り値が `0` であること
  - `--help` 実行時に使用方法が出力され、戻り値が `0` であること
  - `--diff` とタイムゾーンを併用すると、対象行の末尾に時間差が付与され、ローカル行には付与されないこと
  - `--diff` をタイムゾーン引数なしで指定すると、通常通りローカル時刻の1行のみが出力され、終了コードが `0` であること
  - `--time` に有効な日時を指定すると、その日時を基準にローカル行・タイムゾーン行が出力されること
  - `--time` と `--diff` を併用すると、指定日時時点のオフセットに基づいた時間差が計算されること
  - `--time` に不正な形式（日付のみ等）を指定すると、標準出力が空であり、標準エラー出力にエラーメッセージが出力され、戻り値が `1` であること
  - 都市名のみ（例: `Tokyo`）を指定すると、フルのIANA名（`Asia/Tokyo`）で解決された行が出力されること
  - 大文字小文字違い・スペース入り都市名でも同様に解決されること
  - 複数タイムゾーンに一致する都市名（`Istanbul`）を指定すると、標準出力が空であり、標準エラー出力に候補付きエラーメッセージが出力され、戻り値が `1` であること
  - `--set-local-tz` に有効なタイムゾーンを指定すると、ローカル行がそのタイムゾーンの時刻で出力されること（`(ローカル)` 表記は維持される）
  - `--set-local-tz` に都市名を指定しても解決されること
  - `--set-local-tz` と `--time` を併用すると、`--time` の日時が `--set-local-tz` のタイムゾーンの壁時計時刻として解釈されること
  - `--set-local-tz` と `--diff` を併用すると、`--set-local-tz` のタイムゾーンを基準に時間差が計算されること
  - `--set-local-tz` に不正・曖昧な値を指定すると、標準出力が空であり、標準エラー出力にエラーメッセージが出力され、戻り値が `1` であること（他のタイムゾーン引数の検証よりも先に判定されること）
- `test_portable.py`（`portable/wtime.py` を `subprocess` でサブプロセス実行して検証する。パッケージのimportではなくファイルパス実行によって「単一ファイルとして単独動作する」ことそのものを確認する）
  - 引数なし実行でローカル時刻の1行が出力され、終了コードが `0` であること
  - `--version` 実行時に `wtime <バージョン>` が出力され、`src/wtime/__init__.py` の `__version__` と一致すること
  - タイムゾーン引数・`--diff`・`--time`・`--set-local-tz`・都市名解決・不正な引数（エラー終了）の代表的な組み合わせを1〜2ケースずつ実行し、`src/wtime` 版（`wtime.cli.main`）と出力が一致すること（フル機能を網羅的に再テストするのではなく、生成結果が壊れていないことのスモークテストと位置付ける）
  - `portable/wtime.py` が生成スクリプト実行直後の内容と一致していること（`scripts/build_portable.py` の出力をコミット済みファイルと比較し、生成し忘れ・手動編集による乖離を検出する）
