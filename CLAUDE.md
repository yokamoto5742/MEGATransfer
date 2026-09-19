# CLAUDE.md

このファイルは、このリポジトリでコードを扱う際のClaude Code (claude.ai/code) 向けガイダンスです。

## プロジェクト概要

MEGATransferは、指定パターンに一致するファイルを監視ディレクトリで検知し、Playwrightによる
ブラウザ自動操作で、パターンごとに指定したOneDrive共有フォルダへアップロードするWindows
システムトレイアプリです。アップロードに成功したファイルは、監視ディレクトリから保管先へ移動されます。

処理フロー: `main.py` → `app/tray_app.py`（`TrayApp`、トレイアイコン＋監視スレッド）→
`service/file_upload_handler.py`（`FileUploadHandler`、`watchdog.FileSystemEventHandler`）→
`service/onedrive_uploader.py`（`OneDriveUploader`、Playwright同期API）。設定は
`utils/config_manager.py` が `utils/config.ini` から、アップロード先URLは `main.py` で
`utils/env_loader.py` が読み込んだ `.env` の環境変数から取得します。

## 開発コマンド

依存関係は `uv`（`pyproject.toml` + `uv.lock`）で管理しています。

```bash
uv sync                    # 依存関係のインストール
python main.py             # アプリの実行
pyright                    # 型チェック（設定は pyproject.toml の [tool.pyright]）
python build.py            # PyInstallerによるWindows実行ファイルのビルド
```

テストコマンドは `.claude/rules/testing.md` を参照してください。

## 注意点

- **config.iniのパス解決は2種類ある**: `utils/config_manager.py` の `get_config_path()` は、
  PyInstallerでフリーズされた状態では `sys._MEIPASS` から、それ以外はソースディレクトリから
  読み込みます。config.iniの配置に関する変更は両方のモードで動作する必要があります。
  `.env`（`utils/env_loader.py` の `get_env_path()`）も同じ規則で、フリーズ時は `build.py` が
  同梱した `sys._MEIPASS` の `.env`、それ以外はプロジェクトルートの `.env` を読み込みます。
- **アップロードのタイミングはconfig.iniの値の連鎖で決まる**（個別の定数ではない）:
  `wait_time`（ファイル書き込み後の安定待ち）→ `batch_delay`（バッチアップロード前のデバウンス、
  新しいファイルが来るたびにリセット）→ `max_wait_time`（送信APIの応答待ち）→
  `post_upload_wait`（成功後の待機）。一部だけ変更すると検知タイミングがずれる可能性があります。
- **ファイル名マッチングはサフィックスベース**: `get_upload_destinations()` は
  `UPLOAD_DESTINATION_NAMES` の各名前について `.env` の `<名前>`（URL）と config.iniの
  `[filename] <名前>_pattern` を組にして読み込みます。URLが未設定・空の場合は `ValueError` で
  起動を止めます。パターンは末尾に `$` がなければ自動付与し、ファイル名全体ではなく
  拡張子を除いたステム部分に対してマッチングします。アップロード先を増やす場合は
  `UPLOAD_DESTINATION_NAMES`・config.ini・`.env` に追加します。
- **アップロード時にファイル名を変換できる**: config.iniの `[filename] <名前>_strip_pattern = True`
  の場合、ステム末尾のパターン部分を削除した名前でアップロードします（`test_magnate.md` →
  `test.md`、未設定時はFalse）。ローカルのファイル名は変えず、Playwrightの `FilePayload`
  （内容＋新しい名前）をファイル選択ダイアログに渡します。保管先には元の名前で移動されます。
- **1回のバッチに複数のアップロード先が混ざる**: `_process_pending_files` はファイルを
  アップロード先ごとにまとめ、アップロード先ごとにブラウザを起動して順番に処理します。
- **アップロード成功後のファイルは削除ではなく移動される**（`_move_uploaded_files`）: 移動先は
  config.iniの `[Paths] uploaded_dir`。未設定の場合は `src_dir` 配下の `_uploaded` になります。
  共用端末では他ユーザーから見えない場所を指定してください。移動先に同名ファイルがある場合は
  連番を付けて衝突を避けます。
- **保管先のファイルは自動削除される**（`cleanup_uploaded_dir`）: config.iniの
  `[App] uploaded_retention_hours`（デフォルト4時間）を過ぎたファイルを、アプリ起動時と
  アップロード完了後に削除します。判定は更新日時（mtime）で、`_move_uploaded_files` が移動直後に
  `os.utime` でmtimeを現在時刻へ更新するため「保管してからの経過時間」が基準になります。
  サブディレクトリは対象外です。
- **アップロード完了は送信APIの応答で判定する**（`OneDriveUploader._upload_single_file`）:
  OneDriveのWeb画面はファイルを `POST .../Files/AddUsingPath(...)` で送信します（15MBでも
  分割されず1リクエスト）。ファイル一覧の行はアップロード中から表示され、表示が一時的に
  増減するため、画面表示では判定しません。同名ファイルがあると応答は400になり、
  「置き換える」ボタン付きの通知が出ます。これを押すと `overwrite` 付きで再送信されるため、
  その応答で判定します。
- **共有リンクは匿名の編集可能リンク**: サインインなしでアップロードと上書きはできますが、
  削除にはMicrosoftアカウントのサインインが必要です。ボタンは表示テキストで探すため、
  ブラウザは `locale="ja-JP"` で開きます。
- **ブラウザはPC既存のMicrosoft Edgeを使う**（`p.chromium.launch(channel="msedge", ...)`）:
  Chromium本体は同梱せず、配布先PCにプリインストールされているEdgeを起動します。院内共用PCは
  管理者権限が使えずインターネット経由でのブラウザダウンロードも不可のため採用した方式です。
  Edgeが存在しない/バージョンが古いPCでは起動に失敗します。
- **多重起動防止はユーザーセッション単位**（`utils/single_instance.py`）: `Local\` 名前空間の
  名前付きミューテックスで排他するため、同一端末に別ユーザーが同時ログオンしている場合は
  それぞれ1つずつ起動できます。共用端末で監視フォルダを共有していると重複アップロードの
  余地が残ります。ミューテックスの解放はプロセス終了時にOSが行うため、強制終了後もロックは
  残りません。ミューテックスの作成自体に失敗した場合は、起動を妨げずログのみ出力します。
- config.iniの `headless` はアップロード時の実ブラウザ表示を制御します。OneDriveへのアップロードは
  ヘッドレスモードで動作することを確認済みです。

## 関連ドキュメント

- `.claude/rules/` — コーディング規約、レスポンススタイル、テスト規約（自動読み込み）
- `docs/CHANGELOG.md` — Keep a Changelog形式、日本語で記録
