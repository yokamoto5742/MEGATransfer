# CLAUDE.md

このファイルは、このリポジトリでコードを扱う際のClaude Code (claude.ai/code) 向けガイダンスです。

## プロジェクト概要

MEGATransferは、指定パターンに一致するファイルを監視ディレクトリで検知し、Playwrightによる
ブラウザ自動操作でMEGAのファイルリクエストページにアップロードするWindowsシステムトレイアプリ
です。アップロードに成功したファイルは、監視ディレクトリから即座に削除されます。

処理フロー: `main.py` → `app/tray_app.py`（`TrayApp`、トレイアイコン＋監視スレッド）→
`service/file_upload_handler.py`（`FileUploadHandler`、`watchdog.FileSystemEventHandler`）→
`service/mega_uploader.py`（`MegaUploader`、Playwright同期API）。設定は
`utils/config_manager.py` が `utils/config.ini` から読み込みます。

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
- **アップロードのタイミングはconfig.iniの値の連鎖で決まる**（個別の定数ではない）:
  `wait_time`（ファイル書き込み後の安定待ち）→ `batch_delay`（バッチアップロード前のデバウンス、
  新しいファイルが来るたびにリセット）→ `check_interval`/`max_wait_time`（アップロード完了の
  ポーリング）→ `post_upload_wait`（成功後の待機）。一部だけ変更すると検知タイミングがずれる
  可能性があります。
- **ファイル名マッチングはサフィックスベース**: `get_rename_pattern()` はconfig.iniの
  `[filename] pattern` を読み込み、末尾に `$` がなければ自動付与し、ファイル名全体ではなく
  拡張子を除いたステム部分に対してマッチングします。
- **アップロード後のファイル削除は即座かつ復元不可**（`_delete_uploaded_files`）— バックアップや
  ごみ箱への退避はありません。
- **`python build.py` の実行には事前にPlaywrightのChromiumがインストールされている必要が
  あります**（`playwright install chromium`）。`~/AppData/Local/ms-playwright` 配下から
  ブラウザを探し、PyInstallerの出力にバンドルします。ブラウザディレクトリが見つからない場合は
  ビルドが失敗します。
- config.iniの `headless` はアップロード時の実ブラウザ表示を制御します。MEGAのアップロードUIは
  ヘッドレスモードで不安定になることがあります。

## 関連ドキュメント

- `.claude/rules/` — コーディング規約、レスポンススタイル、テスト規約（自動読み込み）
- `docs/CHANGELOG.md` — Keep a Changelog形式、日本語で記録
