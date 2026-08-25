# wtime

CLIの時刻表示ツール（世界時計）。ローカルタイムと、指定したタイムゾーンの現在時刻を表示する。

## 必要環境

- Python 3.9 以降（`zoneinfo` モジュールを使用するため）
- 追加の外部ライブラリ依存なし

## インストール

プロジェクトルートで以下を実行する。

```
pip install -e .
```

`wtime` コマンドとして実行できるようになる。

```
wtime
```

`pip` が使えない環境では、インストールせずに `src` を `PYTHONPATH` に通して直接実行することもできる。引数はそのまま後ろに続ければよい。

```
PYTHONPATH=src python3 -m wtime
PYTHONPATH=src python3 -m wtime Asia/Tokyo Europe/London
```

さらに手軽に使いたい場合は、`portable/wtime.py` を直接実行する方法もある。`pip install` はもちろん `PYTHONPATH` の設定も不要で、`python3` さえあれば動く単一ファイル版（`--diff`・`--time`・`--set-local-tz`・都市名解決を含むフル機能）。

```
python3 portable/wtime.py
python3 portable/wtime.py Asia/Tokyo Europe/London
```

このファイルをコピーするだけで他のマシンに持ち出せる。

## 使いかた

### 引数なし

```
$ wtime
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)
```

現在のローカルタイムの時刻を1行で表示する。

### タイムゾーンを引数に指定

```
$ wtime Europe/London
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)
2026-08-25(Tue) 06:30:00 +01:00 Europe/London
```

現在のローカルタイムの時刻と、指定されたタイムゾーンの時刻を一行ずつ出力する。タイムゾーンは [IANA tz データベース](https://www.iana.org/time-zones)の名前（例: `Asia/Tokyo`）で指定する。

### 都市名だけで指定

```
$ wtime Tokyo
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo
```

`/` を含まない入力は、IANA名の都市部分（最後のセグメント）との完全一致（大文字小文字は区別しない）でタイムゾーンを解決する。`Los_Angeles` のようなアンダースコア入りの都市名は `"Los Angeles"` のようにスペースで指定してもよい（シェル上ではクォートが必要）。

同じ都市名が複数のタイムゾーンに一致する場合はエラーになり、候補が表示される。

```
$ wtime Istanbul
wtime: error: ambiguous timezone: 'Istanbul' (candidates: Asia/Istanbul, Europe/Istanbul)
```

### 複数のタイムゾーンを指定

```
$ wtime Europe/London Asia/Tokyo
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)
2026-08-25(Tue) 06:30:00 +01:00 Europe/London
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo
```

複数のタイムゾーンをスペース区切りで指定すると、指定した順に出力する。

### 時間差を表示（--diff）

```
$ wtime --diff Europe/London Asia/Kolkata
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo (ローカル)
2026-08-25(Tue) 06:30:00 +01:00 Europe/London (-8h)
2026-08-25(Tue) 11:00:00 +05:30 Asia/Kolkata (-3h30m)
```

`--diff` を指定すると、各タイムゾーンの行末にローカル時刻との時間差を追記する（ローカルの行自体には付与されない）。符号は指定タイムゾーンがローカルよりどれだけ進んでいるかを表し、分単位の差があれば分も表示する。タイムゾーンを指定せず `wtime --diff` とした場合は通常通りローカル時刻の1行のみを表示する。

### 基準日時を指定（--time）

```
$ wtime --time 2026-01-01T00:30:00 Europe/London
2026-01-01(Thu) 00:30:00 +09:00 Asia/Tokyo (ローカル)
2025-12-31(Wed) 15:30:00 +00:00 Europe/London
```

`--time <日時>` を指定すると、現在時刻の代わりに指定したローカル日時を基準に表示・`--diff`の時間差計算を行う。`<日時>` は `2026-08-25T14:30:00` のようなT区切り、または `"2026-08-25 14:30:00"` のようなスペース区切り（シェル上ではクォートが必要）のどちらでも指定できる。秒は省略可能（省略時は00秒）だが、日付のみの指定はできない。不正な形式を指定するとエラーになる。

```
$ wtime --time 2026-08-25 Europe/London
wtime: error: invalid time: '2026-08-25'
```

### ローカルタイムゾーンを変更（--set-local-tz）

```
$ wtime --set-local-tz Europe/London Asia/Tokyo
2026-08-25(Tue) 06:30:00 +01:00 Europe/London (ローカル)
2026-08-25(Tue) 14:30:00 +09:00 Asia/Tokyo
```

`--set-local-tz <タイムゾーン>` を指定すると、マシンのシステムタイムゾーンの代わりに指定したタイムゾーンを「ローカル」として扱う（フルのIANA名・都市名のどちらでも指定できる）。`--time` と併用すると、その日時は `--set-local-tz` で指定したタイムゾーンの壁時計時刻として解釈される。`--diff` の基準もそのタイムゾーンになる。

```
$ wtime --set-local-tz Europe/London --time 2026-08-25T14:30:00 --diff Asia/Tokyo
2026-08-25(Tue) 14:30:00 +01:00 Europe/London (ローカル)
2026-08-25(Tue) 22:30:00 +09:00 Asia/Tokyo (+8h)
```

### ヘルプ・バージョン表示

```
wtime --help
wtime --version
```

### 不正なタイムゾーンを指定した場合

```
$ wtime Foo/Bar
wtime: error: unknown timezone: 'Foo/Bar'
$ echo $?
1
```

存在しないタイムゾーン名を指定するとエラーメッセージを標準エラー出力に出し、終了コード `1` で終了する（標準出力には何も出力しない）。

## 開発

### テストの実行

`pytest` がインストールされていれば、`wtime` 本体をインストールせずにプロジェクトルートで以下を実行するだけでよい（`pyproject.toml` の `[tool.pytest.ini_options]` で `src` がテスト実行時の import パスに解決されるため）。

```
python3 -m pytest
```

`pytest` 自体も未インストールの場合は、`pip install -e ".[test]"` でインストールできる（`pip` が使える環境のみ）。

### ポータブル版（`portable/wtime.py`）の再生成

`portable/wtime.py` は `src/wtime/` の実装から自動生成した成果物であり、直接編集しない。`src/wtime/` に変更を加えたら、以下を実行して再生成し、生成結果もコミットする。

```
python3 scripts/build_portable.py
```

`tests/test_portable.py` に、再生成し忘れ（`src/wtime/` と `portable/wtime.py` の乖離）を検出するテストが含まれる。

### ディレクトリ構成

```
src/wtime/
├── __init__.py    # バージョン定義
├── __main__.py    # `python -m wtime` 用エントリポイント
├── cli.py         # 引数解析・全体制御
├── clock.py       # 時刻取得・タイムゾーン解決
└── formatter.py   # 出力文字列の整形
scripts/
└── build_portable.py  # portable/wtime.py の生成スクリプト
portable/
└── wtime.py            # 生成された単一ファイル版（pip install不要）
tests/             # pytest によるテスト
```

## ドキュメント

- [doc/requirement.md](doc/requirement.md) — 要求仕様
- [doc/spec.md](doc/spec.md) — 設計書
- [doc/plan.md](doc/plan.md) — 実装計画
