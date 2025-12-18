# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## House Rules:
- 文章ではなくパッチの差分を返す。
- コードの変更範囲は最小限に抑える。
- コードの修正は直接適用する。
- Pythonのコーディング規約はPEP8に従います。
- KISSの原則に従い、できるだけシンプルなコードにします。
- 可読性を優先します。一度読んだだけで理解できるコードが最高のコードです。
- Pythonのコードのimport文は以下の適切な順序に並べ替えてください。
標準ライブラリ
サードパーティライブラリ
カスタムモジュール 
それぞれアルファベット順に並べます。importが先でfromは後です。

## CHANGELOG
このプロジェクトにおけるすべての重要な変更は日本語でdcos/CHANGELOG.mdに記録します。
フォーマットは[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)に基づきます。

## Automatic Notifications (Hooks)
自動通知は`.claude/settings.local.json` で設定済：
- **Stop Hook**: ユーザーがClaude Codeを停止した時に「作業が完了しました」と通知
- **SessionEnd Hook**: セッション終了時に「Claude Code セッションが終了しました」と通知

## クリーンコードガイドライン
- 関数のサイズ：関数は50行以下に抑えることを目標にしてください。関数の処理が多すぎる場合は、より小さなヘルパー関数に分割してください。
- 単一責任：各関数とモジュールには明確な目的が1つあるようにします。無関係なロジックをまとめないでください。
- 命名：説明的な名前を使用してください。`tmp` 、`data`、`handleStuff`のような一般的な名前は避けてください。例えば、`doCalc`よりも`calculateInvoiceTotal` の方が適しています。
- DRY原則：コードを重複させないでください。類似のロジックが2箇所に存在する場合は、共有関数にリファクタリングしてください。それぞれに独自の実装が必要な場合はその理由を明確にしてください。
- コメント:分かりにくいロジックについては説明を加えます。説明不要のコードには過剰なコメントはつけないでください。
- コメントとdocstringは必要最小限に日本語で記述します。文末に"。"や"."をつけないでください。
- 
## Project Overview

MEGATransfer is a Windows system tray application that monitors a directory for files matching a specific pattern and automatically uploads them to MEGA file requests using Playwright browser automation. After successful upload, the files are automatically deleted from the monitored directory.

## Architecture

### Core Components

**Tray Application** (`app/tray_app.py`)
- System tray interface using `pystray` with custom icon
- Manages the file watching lifecycle (start/stop)
- Runs file monitoring in a daemon thread
- On startup, scans for existing files in the monitored directory

**File Upload Handler** (`service/file_upload_handler.py`)
- Watchdog `FileSystemEventHandler` that responds to file creation and move events
- Implements batching: files are queued and processed together after a 3-second delay
- Supports immediate processing via `process_now()`
- Deletes files after successful upload
- Uses threading locks for concurrent safety

**MEGA Uploader** (`service/mega_uploader.py`)
- Playwright-based browser automation for MEGA file requests
- Runs in non-headless mode (`headless=False`)
- Supports both single file and batch file uploads
- Waits for "アップロード済み" text to confirm upload completion
- Maximum upload timeout: 300 seconds

**Config Manager** (`utils/config_manager.py`)
- Loads configuration from `utils/config.ini` (bundled with PyInstaller builds)
- Supports `.env` file for environment variables
- Provides typed access to configuration values

### Key Behavioral Patterns

**Batching Logic**: When files are detected, they are added to a queue. A 3-second timer starts/resets with each new file. When the timer expires, all queued files are uploaded together in a single browser session.

**Browser Session Reuse**: For multiple files, `upload_files()` opens the browser once and uploads all files sequentially, then closes the browser.

**File Deletion**: Only successfully uploaded files are deleted. If an upload fails, the file remains in the monitored directory.

## Development Commands

### Running the Application
```bash
python main.py
```

### Running Tests
```bash
python -m pytest tests/ -v --tb=short --disable-warnings
```

### Type Checking
```bash
pyright
```
Configuration in `pyrightconfig.json` (Python 3.13, standard mode)

### Building Executable
```bash
python build.py
```
Creates a windowed executable using PyInstaller with `utils/config.ini` bundled.

## Configuration

Configuration is in `utils/config.ini`:

- `[URL] MEGAfilerequest`: The MEGA file request URL
- `[Paths] src_dir`: Directory to monitor for files
- `[filename] pattern`: Regex pattern for matching file names (matches stem, not extension)
- `[App] wait_time`: Seconds to wait after file creation before processing

## Dependencies

Key dependencies (see `requirements.txt`):
- `watchdog`: File system monitoring
- `playwright`: Browser automation for MEGA uploads
- `pystray`: System tray application
- `pytest`: Testing framework
- `pyright`: Type checking
- `pyinstaller`: Executable building

## Testing Notes

Tests are located in `tests/`. Only `tests/test_main.py` currently exists. When writing new tests, use `pytest-cov` for coverage reporting.
