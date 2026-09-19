# 変更履歴

このプロジェクトのすべての重要な変更はこのファイルに記録されています。

フォーマットは[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)に基づき、バージョンは[セマンティックバージョニング](https://semver.org/lang/ja/)に従います。

## [Unreleased]

### 追加
- config.iniの `[filename]` に `<名前>_strip_pattern` を追加。Trueの場合、ファイル名末尾のパターン部分を削除した名前でアップロードする（例: `test_magnate.md` → `test.md`）
- `Receive_file` は変換あり、`Taskdiary` は変換なしで設定。ローカルおよび保管先のファイル名は変更しない

## [1.3.1] - 2026-09-19

### 変更
- セキュリティ向上のため、OneDrive共有URLの管理をconfig.iniから `.env` に移行。キー名は `Taskdiary`、`Receive_file`
- 起動時に `.env` を読み込むように変更。実行ファイルでは同梱した `.env` を読み込む
- URLが `.env` に未設定の場合は、キー名を示すエラーで起動を中止

### 削除
- config.iniの `[URL]` セクション

## [1.3.0] - 2026-09-19

### 追加
- ファイル名パターンごとにOneDrive共有フォルダへアップロードする機能（`OneDriveUploader`）。`_taskdiary` は `Taskdiary`、`_magnate` は `Receive_file` のURLへ送信
- 1回のバッチに複数のアップロード先のファイルが混ざった場合、アップロード先ごとに順番に処理
- OneDriveに同名ファイルがある場合は「置き換える」で上書き
- config.iniに `replace_button_text` を追加

### 変更
- アップロード完了判定を、OneDriveの送信API（`Files/AddUsingPath`）の応答で行う方式に変更
- `post_upload_wait` を5.0秒から1.0秒に変更

### 削除
- MEGAファイルリクエストへのアップロード機能（`MegaUploader`）
- config.iniの `MEGAfilerequest`、`pattern`、`upload_complete_text`、`check_interval`

## [1.2.0] - 2026-08-17

### 変更
- ブラウザをPC既存のMicrosoft Edgeを使用する方式に変更。Chromium同梱は削除
- ビルド時のブラウザ設定に関するドキュメントを更新

## [1.1.1] - 2026-08-17

### 追加
- 名前付きミューテックス（`Local\MEGATransfer_SingleInstance`）による多重起動防止。既に起動中の場合はログを出して静かに終了する

## [1.1.0] - 2026-08-15

### 追加
- 保管先（`uploaded_dir`）の古いファイルを自動削除する機能。アプリ起動時とアップロード完了後に実行
- config.iniに `uploaded_retention_hours` を追加（保管時間、デフォルト4時間）
- アップロード完了ファイルを保管先へ移動する機能

### 変更
- ファイルパスを明示的に文字列に変換して型安全性を向上
- 保管先へ移動したファイルの更新日時を現在時刻に更新（保管時刻を基準に削除するため）
- アップロード完了判定を「テキストの有無」から「件数増加」に変更

## [1.0.0] - 2025-12-24

### 追加
- テスト機能: tray_app、file_upload_handler、mega_uploaderのテストを追加
- 既存ファイルスキャン機能をFileUploadHandlerに追加
- 起動時に監視ディレクトリの既存ファイルをスキャンする機能

### 変更
- ログレベルをINFOに更新
- ソースディレクトリパスを更新（ファイル転送に変更）
- docstringをシンプルに簡潔化
- バージョンをv1.0.0に更新

### 削除
- README.mdを削除

## [0.0.1] - 2025-12-18

### 追加
- MEGATransferアプリケーションの初期実装
- システムトレイインターフェースとファイル監視機能
- Playwright を使用したMEGAへのファイルアップロード機能
- ファイルアップロード後の自動削除機能
- 設定管理システム（config.ini対応）
- ログ設定とローテーション機能
- ビルドスクリプト（PyInstaller統合）
- Playwrightブラウザをビルドに含める機能
- アップロード後の待機時間設定
- 複数ファイルのバッチアップロード対応
- FileUploadHandlerの既存ファイルスキャン機能

### 変更
- ファイルアップロード機能を改善
- Playwrightのブラウザ起動・終了処理を共通化
- アップロード処理をヘッドレスモードで実行

### 修正
- ファイルアップロード後のリネーム処理を削除
- ファイルアップロード後のファイル削除処理を追加

[1.2.0]: https://github.com/yokamoto5742-h/MEGATransfer/compare/1.1.1...1.2.0
[1.1.1]: https://github.com/yokamoto5742-h/MEGATransfer/compare/1.1.0...1.1.1
[1.1.0]: https://github.com/yokamoto5742-h/MEGATransfer/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/yokamoto5742-h/MEGATransfer/compare/0.0.1...1.0.0
[0.0.1]: https://github.com/yokamoto5742-h/MEGATransfer/releases/tag/0.0.1
