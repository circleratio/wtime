# wtime 実装計画

`doc/spec.md` の設計に基づく実装ステップ。各ステップは前のステップの成果物に依存するため、原則として上から順に進める。

# ステップ1: プロジェクト初期化

- `pyproject.toml` を作成する
  - `[build-system]`: setuptools
  - `[project]`: `name = "wtime"`, `requires-python = ">=3.9"`, `dynamic = ["version"]`
  - `[tool.setuptools.dynamic]`: `version = {attr = "wtime.__version__"}`
  - `[project.scripts]`: `wtime = "wtime.cli:main"`
  - `[tool.setuptools.package-dir]` / `packages` で `src` レイアウトを指定
- `src/wtime/__init__.py` を作成し `__version__ = "0.1.0"` を定義する
- `src/wtime/__main__.py` に `python -m wtime` 用の `if __name__ == "__main__": sys.exit(main())` を実装する
- 開発用依存として `pytest` を導入する（`pyproject.toml` の `[project.optional-dependencies]` に `test = ["pytest"]` を追加）
- **完了条件**: `pip install -e .` が成功し、`wtime --help`（未実装のため中身はエラーで構わない）が少なくともコマンドとして認識される状態、もしくは `python -m pytest` が「テストなし」で正常終了する状態

# ステップ2: `clock.py` の実装

- `UnknownTimezoneError` 例外クラスを実装する
- `ClockEntry` データクラスを実装する
- `get_local_entry(now=None)` を実装する（`datetime.now().astimezone()` を使用）
- `resolve_local_timezone_name()` を実装する
  1. `TZ` 環境変数を確認し、`ZoneInfo(TZ)` で妥当性検証
  2. `/etc/localtime` のシンボリックリンク先から `zoneinfo/` 以降を抽出
  3. いずれも不可の場合は `time.tzname` の略称にフォールバック
- `get_zone_entry(name, now=None)` を実装する（`ZoneInfo(name)` 生成、`zoneinfo.ZoneInfoNotFoundError` を `UnknownTimezoneError` に変換）
- **完了条件**: ステップ6の `test_clock.py` が全て通る

# ステップ3: `formatter.py` の実装

- `_WEEKDAY_ABBR` 定数を定義する
- `format_entry(entry: ClockEntry) -> str` を実装する
  - `YYYY-MM-DD(曜日) HH:MM:SS ±HH:MM タイムゾーン名` 形式で整形
  - `entry.is_local` が真の場合は末尾に ` (ローカル)` を付与
- **完了条件**: ステップ6の `test_formatter.py` が全て通る（UTCオフセットが分単位のタイムゾーンを含む）

# ステップ4: `cli.py` の実装

- `build_parser()` を実装する（位置引数 `timezones`（`nargs="*"`）、`--version`）
- `main(argv=None) -> int` を実装する
  1. 引数解析
  2. 指定タイムゾーンをすべて `get_zone_entry()` で解決を試みる。1つでも `UnknownTimezoneError` が発生した場合、標準出力には何も書かず、不正な名前ごとに `wtime: error: unknown timezone: '<name>'` を標準エラー出力へ書き、`1` を返す
  3. 全て解決できた場合、ローカルエントリ→指定順の各エントリの順で `format_entry()` の結果を標準出力へ1行ずつ出力し、`0` を返す
- **完了条件**: ステップ6の `test_cli.py` が全て通る

# ステップ5: エントリポイントの結線確認

- `src/wtime/__main__.py` および `pyproject.toml` の `[project.scripts]` から `cli.main` が正しく呼び出せることを確認する
- **完了条件**: `wtime`／`python -m wtime` の両方で引数なし実行がローカル時刻を1行出力する

# ステップ6: テスト実装

- `tests/test_clock.py`
- `tests/test_formatter.py`
- `tests/test_cli.py`（`capsys` を使用）

`doc/spec.md` の「5. テスト方針」に列挙された各ケースをそのままテストケースとして実装する。

- **完了条件**: `python -m pytest` が全件成功する

# ステップ7: 手動動作確認

以下を実際に実行し、`doc/requirement.md` の使用例と出力が一致することを目視確認する。

```
wtime
wtime Europe/London
wtime Europe/London Asia/Tokyo
wtime --help
wtime --version
wtime Foo/Bar   # エラーになること、終了コードを echo $? で確認
```

- **完了条件**: 全コマンドが要求仕様通りの出力・終了コードになる

# ステップ8: 最終確認

- `python -m pytest` 全件成功
- `doc/requirement.md` の要求仕様を再読し、実装漏れがないかチェックリストとして突き合わせる
- 未対応・保留にした項目（今回スコープ外とした時差計算機能など）があれば `doc/requirement.md` との整合を確認する

# 依存関係の補足

- ステップ2・3は互いに独立して並行実装可能（`clock.py` と `formatter.py` は `ClockEntry` の型定義のみで結合するため）
- ステップ4はステップ2・3の完了後に着手する
- ステップ6のテストはステップ2〜4それぞれの実装と同時並行で書き進めてよい（先にテストを書いてから実装するTDDスタイルでも可）

---

# 追加機能: `--diff` オプション

ステップ1〜8はすでに実装済み。ここからは `doc/requirement.md`・`doc/spec.md` に追加した `--diff` オプション分の差分実装計画。既存の実装（`src/`, `tests/`）に対する変更のみを行い、プロジェクト初期化（ステップ1）等はやり直さない。

# ステップ9: `formatter.py` の拡張

- `diff_from_local(entry: ClockEntry, local_entry: ClockEntry) -> str` を実装する
  - `entry.dt.utcoffset() - local_entry.dt.utcoffset()` を分単位に変換し、`+Hh` / `-Hh` / `+HhMm` / `-HhMm` 形式に整形する
- `format_entry(entry: ClockEntry, diff: str | None = None) -> str` を拡張する
  - `entry.is_local` が真なら従来通り ` (ローカル)` を付与し、`diff` は無視する
  - `entry.is_local` が偽かつ `diff` が指定されていれば ` ({diff})` を付与する
  - それ以外（`diff=None` かつ非ローカル）は従来通り何も付与しない
- **完了条件**: ステップ11で追加する `test_formatter.py` の新規ケースが全て通る

# ステップ10: `cli.py` の拡張

- `build_parser()` に `--diff`（`action="store_true"`）を追加する
- `main()` の出力生成部分を変更する
  1. ローカルエントリを取得する（変更なし）
  2. `args.diff` が真の場合、各タイムゾーンエントリについて `diff_from_local(entry, local_entry)` を計算し `format_entry(entry, diff=...)` を呼ぶ
  3. `args.diff` が偽の場合は従来通り `format_entry(entry)` を呼ぶ
  4. ローカル行は常に `format_entry(local_entry)`（`diff` を渡さない）
  5. タイムゾーン未指定時の挙動（ローカル1行のみ出力）は `--diff` の有無に関わらず変化しない
- **完了条件**: ステップ11で追加する `test_cli.py` の新規ケースが全て通る

# ステップ11: テスト追加

- `tests/test_formatter.py` に以下を追加する
  - `diff_from_local()` の境界値テスト（時間のみの差、分を含む差、負の差）
  - `format_entry()` に `diff` を渡した場合／`is_local=True` に `diff` を渡しても無視される場合
- `tests/test_cli.py` に以下を追加する
  - `--diff` とタイムゾーンを併用した場合の出力（対象行に時間差が付き、ローカル行には付かない）
  - `--diff` をタイムゾーン引数なしで指定した場合、通常通りローカル1行のみが出力されること
- **完了条件**: `python -m pytest` が全件成功する

# ステップ12: 手動動作確認

`doc/requirement.md` の「時間差を表示（--diff）」の使用例を実際に実行し、出力を目視確認する。

```
wtime --diff Europe/London Asia/Kolkata
wtime --diff
```

- **完了条件**: 出力フォーマット（符号・時:分表記）が要求仕様通りであること、`wtime --diff`（タイムゾーンなし）がエラーにならずローカル1行のみ出力すること

# ステップ13: 最終確認

- `python -m pytest` 全件成功
- 既存の正常系・異常系（`--diff` なしの動作）に回帰がないことを確認する
- `doc/requirement.md` の要求仕様（`--diff` 関連）との突き合わせ
- `README.md` に `--diff` の使いかたが未記載であれば追記する（ドキュメント作成段階のタスクだが、実装完了時点で漏れがないか確認する）

---

# 追加機能: `--time` オプション

ステップ1〜13はすでに実装済み。ここからは `doc/requirement.md`・`doc/spec.md` に追加した `--time <日時>` オプション分の差分実装計画。既存の実装（`src/`, `tests/`）に対する変更のみを行う。

# ステップ14: `clock.py` の拡張

- `InvalidTimeError` 例外クラスを追加する（`value` 属性を持つ）
- `parse_local_datetime(value: str) -> datetime` を実装する
  1. 入力文字列中の最初の半角スペース1個を `T` に置換して正規化する
  2. `%Y-%m-%dT%H:%M:%S` → `%Y-%m-%dT%H:%M` の順に `datetime.strptime()` を試す
  3. いずれかが成功したら、結果の naive な `datetime` に対して `.astimezone()`（引数なし）を呼び、ローカルタイムゾーン付きの `datetime` を返す
  4. どちらの書式にも一致しなければ `InvalidTimeError(value)` を送出する
- `get_local_entry()` / `get_zone_entry()` は変更しない（既存の `now` 引数をそのまま利用する）
- **完了条件**: ステップ16で追加する `test_clock.py` の新規ケースが全て通る

# ステップ15: `cli.py` の拡張

- `build_parser()` に `--time`（`metavar="DATETIME"`、デフォルト `None`。`type=` は使わず文字列のまま受け取る）を追加する
- `main()` の処理順序を変更する
  1. 引数解析
  2. `args.time` が指定されていれば `parse_local_datetime(args.time)` を試みる。`InvalidTimeError` を捕捉した場合は `wtime: error: invalid time: '<value>'` を標準エラー出力に書き、`1` を返して終了する（タイムゾーンの検証には進まない）
  3. 解析できた場合の値、または `--time` 未指定なら `None` を `base_time` とする
  4. タイムゾーン名の解決を `get_zone_entry(name, now=base_time)` に変更する（不正なタイムゾーン名のエラー処理は変更なし）
  5. ローカルエントリの取得を `get_local_entry(now=base_time)` に変更する
  6. 以降（`--diff` の処理、出力）は変更なし
- **完了条件**: ステップ16で追加する `test_cli.py` の新規ケースが全て通る

# ステップ16: テスト追加

- `tests/test_clock.py` に以下を追加する
  - `parse_local_datetime()` が `T`区切り・スペース区切りの両方を解析できること
  - `parse_local_datetime()` が秒省略入力を00秒として解析できること
  - `parse_local_datetime()` が日付のみ・書式崩れの入力に対して `InvalidTimeError` を送出すること
- `tests/test_cli.py` に以下を追加する
  - `--time` に有効な日時を指定すると、その日時を基準にローカル行・タイムゾーン行が出力されること
  - `--time` と `--diff` を併用すると、指定日時時点のオフセットに基づいた時間差が計算されること（DSTの有無で結果が変わる日付を選ぶ）
  - `--time` に不正な形式（日付のみ）を指定すると、標準出力が空・標準エラー出力にエラーメッセージ・戻り値が `1` であること
- **完了条件**: `python -m pytest` が全件成功する

# ステップ17: 手動動作確認

`doc/requirement.md` の「基準日時を指定（--time）」の使用例を実際に実行し、出力を目視確認する。

```
wtime --time 2026-01-01T00:30:00 Europe/London
wtime --time "2026-08-25 14:30" --diff Europe/London
wtime --time 2026-08-25 Europe/London   # エラーになること、終了コードを echo $? で確認
```

- **完了条件**: 年またぎでUTCオフセットが変わる例（1月のロンドンは+00:00）も含めて要求仕様通りの出力になること、日付のみの指定がエラーになること

# ステップ18: 最終確認

- `python -m pytest` 全件成功
- 既存の正常系・異常系（`--time` なしの動作、`--diff` 単体の動作）に回帰がないことを確認する
- `doc/requirement.md` の要求仕様（`--time` 関連）との突き合わせ
- `README.md` に `--time` の使いかたが未記載であれば追記する

---

# 追加機能: 都市名だけの指定

ステップ1〜18はすでに実装済み。ここからは `doc/requirement.md`・`doc/spec.md` に追加した「タイムゾーン引数として都市名だけの指定を受け付ける」機能分の差分実装計画。既存の実装（`src/`, `tests/`）に対する変更のみを行う。

# ステップ19: `clock.py` の拡張

- `AmbiguousTimezoneError` 例外クラスを追加する（`name`・`candidates` 属性を持つ）
- `_city_index()` を実装する（`functools.lru_cache(maxsize=1)` でキャッシュ）
  - `zoneinfo.available_timezones()` を走査し、`/` を含む名前だけを対象に、最後のセグメント（都市部分）を小文字化したものをキーとして `{都市名(小文字): [IANA名, ...]}` の辞書を構築する
- `resolve_timezone_name(name: str) -> str` を実装する
  1. まず `ZoneInfo(name)` をそのまま試し、成功すれば `name` をそのまま返す（既存の完全一致の挙動を変えない。`UTC` のようなスラッシュなしの正式名も含む）
  2. 失敗し、かつ `name` に `/` が含まれる場合は都市名解決を試みず `UnknownTimezoneError(name)` を送出する
  3. `/` を含まない場合、`name` のスペースをアンダースコアに置換し小文字化したキーで `_city_index()` を検索する
  4. 該当なしなら `UnknownTimezoneError(name)`、複数該当なら `AmbiguousTimezoneError(name, sorted(candidates))` を送出する
  5. 1件のみ該当すればそのIANA名を返す
- `get_zone_entry(name, now=None)` を変更し、内部で直接 `ZoneInfo(name)` を呼ぶのではなく、まず `resolve_timezone_name(name)` で解決済みのIANA名を得てから `ZoneInfo()` と `ClockEntry.label` の組み立てに使う
- **完了条件**: ステップ21で追加する `test_clock.py` の新規ケースが全て通る

# ステップ20: `cli.py` の拡張

- `AmbiguousTimezoneError` をインポートする
- タイムゾーン解決のループを変更し、`UnknownTimezoneError` に加えて `AmbiguousTimezoneError` も捕捉する
  - `UnknownTimezoneError`: 既存の `wtime: error: unknown timezone: '<name>'` のまま
  - `AmbiguousTimezoneError`: `wtime: error: ambiguous timezone: '<name>' (candidates: <カンマ区切りの候補>)` を組み立てる
- 両方の例外に対応するため、これまでの「不正な名前のリスト」ではなく「組み立て済みのエラーメッセージ行のリスト」を蓄積する形に変更する（1つでも失敗があれば通常出力は行わず、全エラー行を標準エラー出力に書き `1` を返す、という既存の制御フローは変えない）
- **完了条件**: ステップ21で追加する `test_cli.py` の新規ケースが全て通る

# ステップ21: テスト追加

- `tests/test_clock.py` に以下を追加する
  - `resolve_timezone_name()` が完全なIANA名（`Europe/London`、`UTC`）をそのまま返すこと
  - `resolve_timezone_name()` が都市名（大文字小文字混在、例: `tokyo`/`TOKYO`）を正しいIANA名に解決すること
  - `resolve_timezone_name()` がスペース入り都市名（例: `"Los Angeles"`）を `America/Los_Angeles` に解決すること
  - `resolve_timezone_name()` が一致しない都市名・`/`を含む不正な入力に対して `UnknownTimezoneError` を送出すること
  - `resolve_timezone_name()` が `Istanbul` のような複数一致に対して `AmbiguousTimezoneError` を送出し、`candidates` にソート済みの一致IANA名一覧が入ること
- `tests/test_cli.py` に以下を追加する
  - 都市名のみ（`Tokyo`）を指定すると `Asia/Tokyo` として解決された行が出力されること
  - 大文字小文字違い・スペース入り都市名でも解決されること
  - `Istanbul` を指定すると、標準出力が空・標準エラー出力に候補付きエラーメッセージ・戻り値が `1` であること
- **完了条件**: `python -m pytest` が全件成功する

# ステップ22: 手動動作確認

`doc/requirement.md` の「都市名だけの指定」の使用例を実際に実行し、出力を目視確認する。

```
wtime Tokyo
wtime tokyo
wtime "Los Angeles"
wtime Istanbul   # 曖昧エラーになること、終了コードとエラーメッセージの候補を確認
```

- **完了条件**: 都市名がフルのIANA名に解決されて表示されること、曖昧な都市名がエラーになり候補（Asia/Istanbul, Europe/Istanbul）を含むこと

# ステップ23: 最終確認

- `python -m pytest` 全件成功
- 既存の正常系・異常系（フルのIANA名指定、不正なタイムゾーン名指定）に回帰がないことを確認する
- `doc/requirement.md` の要求仕様（都市名解決関連）との突き合わせ
- `README.md` に都市名だけの指定についての使いかたが未記載であれば追記する

---

# 追加機能: `--set-local-tz` オプション

ステップ1〜23はすでに実装済み。ここからは `doc/requirement.md`・`doc/spec.md` に追加した `--set-local-tz <タイムゾーン>` オプション分の差分実装計画。既存の実装（`src/`, `tests/`）に対する変更のみを行う。

# ステップ24: `clock.py` の拡張

- `get_local_entry(now=None, tz_name=None)` を拡張する
  - `tz_name` が指定された場合、`ZoneInfo(tz_name)` を組み立て、`(now or datetime.now()).astimezone(zone)` で時刻を求め、`label` に `tz_name` をそのまま入れる（`resolve_local_timezone_name()` は呼ばない）
  - `tz_name` が `None`（デフォルト）の場合は既存の挙動（システムタイムゾーン解決）のまま
- `parse_local_datetime(value, tz_name=None)` を拡張する
  1. 既存のフォーマット解析（T区切り／スペース区切り、秒省略可）はそのまま
  2. `naive` が得られたあと、`tz_name` が指定されていれば `naive.replace(tzinfo=ZoneInfo(tz_name))` を返す（`ZoneInfo` は `replace(tzinfo=...)` でもDSTを正しく解決できることを踏まえた実装）
  3. `tz_name` が `None` の場合は既存通り `naive.astimezone()` を返す
- `resolve_timezone_name()`・`get_zone_entry()`・`formatter.py` は変更しない
- **完了条件**: ステップ26で追加する `test_clock.py` の新規ケースが全て通る

# ステップ25: `cli.py` の拡張

- `_timezone_error_message(exc) -> str` ヘルパー関数を新設する
  - `AmbiguousTimezoneError` なら `wtime: error: ambiguous timezone: '<name>' (candidates: <カンマ区切り>)`
  - `UnknownTimezoneError` なら `wtime: error: unknown timezone: '<name>'`
  - 既存のタイムゾーン解決ループのエラーメッセージ組み立て箇所をこのヘルパー呼び出しに置き換える（挙動は変えない、重複コードの解消）
- `build_parser()` に `--set-local-tz`（`metavar="TIMEZONE"`、デフォルト `None`）を追加する
- `main()` の処理順序を変更する
  1. 引数解析
  2. `args.set_local_tz` が指定されていれば `resolve_timezone_name(args.set_local_tz)` を試みる。`UnknownTimezoneError`/`AmbiguousTimezoneError` を捕捉した場合は `_timezone_error_message()` の結果を標準エラー出力に書き、`1` を返して終了する（`--time`・タイムゾーン引数の検証には進まない）。解決できれば `local_tz_name` に設定し、未指定なら `None` のままとする
  3. `args.time` が指定されていれば `parse_local_datetime(args.time, tz_name=local_tz_name)` を試みる（`InvalidTimeError`の扱いは変更なし）
  4. タイムゾーン引数の解決（`get_zone_entry(name, now=base_time)`）は変更なし
  5. ローカルエントリの取得を `get_local_entry(now=base_time, tz_name=local_tz_name)` に変更する
  6. 以降（`--diff` の処理、出力）は変更なし
- **完了条件**: ステップ26で追加する `test_cli.py` の新規ケースが全て通る

# ステップ26: テスト追加

- `tests/test_clock.py` に以下を追加する
  - `get_local_entry(tz_name="Europe/London")` がマシンのシステムタイムゾーンに関わらず `Europe/London` の時刻・ラベルを返すこと
  - `parse_local_datetime(value, tz_name="Europe/London")` が指定タイムゾーンの壁時計時刻として解釈されること（夏時間・冬時間それぞれの日付で検証する）
- `tests/test_cli.py` に以下を追加する
  - `--set-local-tz` に有効なタイムゾーンを指定すると、ローカル行がそのタイムゾーンの時刻で出力されること（`(ローカル)` 表記は維持）
  - `--set-local-tz` に都市名を指定しても解決されること
  - `--set-local-tz` と `--time` を併用すると、`--time` の日時が `--set-local-tz` のタイムゾーンの壁時計時刻として解釈されること
  - `--set-local-tz` と `--diff` を併用すると、そのタイムゾーンを基準に時間差が計算されること
  - `--set-local-tz` に不正・曖昧な値を指定すると、標準出力が空・標準エラー出力にエラーメッセージ・戻り値が `1` であること
- **完了条件**: `python -m pytest` が全件成功する

# ステップ27: 手動動作確認

`doc/requirement.md` の「ローカルタイムゾーンを変更（--set-local-tz）」の使用例を実際に実行し、出力を目視確認する。

```
wtime --set-local-tz Europe/London Asia/Tokyo
wtime --set-local-tz London
wtime --set-local-tz Europe/London --time 2026-08-25T14:30:00 --diff Asia/Tokyo
wtime --set-local-tz Foo/Bar   # エラーになること、終了コードを echo $? で確認
```

- **完了条件**: ローカル行が `--set-local-tz` で指定したタイムゾーンの時刻・IANA名で出力されること、`--time`/`--diff` との併用が要求仕様通りの計算結果になること、不正な値がエラーになること

# ステップ28: 最終確認

- `python -m pytest` 全件成功
- 既存の正常系・異常系（`--set-local-tz` なしの動作）に回帰がないことを確認する
- `doc/requirement.md` の要求仕様（`--set-local-tz` 関連）との突き合わせ
- `README.md` に `--set-local-tz` の使いかたが未記載であれば追記する
