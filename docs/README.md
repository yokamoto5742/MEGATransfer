# MEGATransfer

Windows システムトレイアプリケーション。指定ディレクトリを監視してファイルを自動的にMEGAファイルリクエストにアップロードします。アップロード完了後、ファイルは自動削除されます。

## 主な特徴

- ファイルシステム監視による自動検出と処理
- Playwrightを使用したブラウザ自動化によるアップロード
- 複数ファイルのバッチ処理に対応
- システムトレイインテグレーション
- ファイル名パターンマッチング
- 詳細なログ記録と自動ローテーション

## 前提条件

- **OS**: Windows11
- **Python**: 3.13以上
- **ブラウザ**: Chromium（Playwrightが自動インストール）

## インストール

1. リポジトリをクローンします
```bash
git clone <repository-url>
cd MEGATransfer
```

1. 仮想環境を作成し、有効化します
```bash
python -m venv .venv
.venv\Scripts\activate
```

1. 依存パッケージをインストールします
```bash
pip install -r requirements.txt
```

1. Playwrightブラウザをインストールします
```bash
playwright install chromium
```

1. 設定ファイルを編集します（`utils/config.ini`）
```ini
[URL]
MEGAfilerequest = <your-mega-file-request-url>

[Paths]
src_dir = <directory-to-monitor>

[filename]
pattern = <filename-pattern>
```

## 使用方法

### アプリケーション実行

```bash
python main.py
```

アプリケーションはシステムトレイに常駐します。トレイアイコンからフォルダを開く、または終了できます。

### 設定ファイル（`utils/config.ini`）

```ini
[URL]
MEGAfilerequest = https://mega.nz/filerequest/xxxxx

[Paths]
src_dir = C:\Users\yokam\Desktop\Magnate\ファイル転送

[filename]
# ファイル名パターン（拡張子を除いたファイル名の末尾にマッチ）
pattern = _magnate

[App]
# ファイル書き込み完了を待つ時間（秒）
wait_time = 0.5
# バッチ処理開始までの待機時間（秒）
batch_delay = 3.0

[Uploader]
# MEGAのアップロード完了を示すテキスト
upload_complete_text = アップロード済み
# 完了チェックの最大待機時間（秒）
max_wait_time = 30
# 完了チェックの間隔（秒）
check_interval = 0.5
# ブラウザをヘッドレスモードで実行するか
headless = True
# アップロード完了後の待機時間（秒）
post_upload_wait = 5.0

[LOGGING]
log_retention_days = 7
log_directory = logs
log_level = INFO
project_name = MEGATransfer
debug_mode = True
```

## プロジェクト構造

```
MEGATransfer/
├── app/                          # トレイアプリケーション
│   ├── __init__.py
│   └── tray_app.py               # システムトレイUI管理
├── service/                      # ファイル処理・アップロード処理
│   ├── __init__.py
│   ├── file_upload_handler.py    # ファイル監視とキュー管理
│   └── mega_uploader.py          # Playwr基底のアップロード実装
├── utils/                        # ユーティリティ
│   ├── __init__.py
│   ├── config.ini                # 設定ファイル
│   ├── config_manager.py         # 設定ローディング
│   └── log_rotation.py           # ログ管理
├── tests/                        # テストスイート
│   ├── __init__.py
│   ├── test_tray_app.py
│   ├── test_file_upload_handler.py
│   └── test_mega_uploader.py
├── scripts/                      # ビルド・管理スクリプト
│   ├── __init__.py
│   ├── project_structure.py
│   └── version_manager.py
├── docs/                         # ドキュメント
│   ├── README.md
│   ├── LICENSE
│   └── CHANGELOG.md
├── main.py                       # エントリーポイント
├── build.py                      # 実行ファイルビルドスクリプト
├── requirements.txt              # 依存パッケージ
├── pyrightconfig.json            # 型チェック設定
└── CLAUDE.md                     # Claude Code用開発ガイドライン
```

## 主要コンポーネント

### TrayApp（`app/tray_app.py`）

システムトレイインテグレーションと監視ライフサイクルを管理します。

- **機能**:
  - カスタムアイコン表示
  - 監視フォルダの存在確認
  - ファイル監視の開始・停止
  - 起動時に既存ファイルをスキャン

**主要メソッド**:
```python
# ファイル監視を開始
app.start_watching()

# ファイル監視を停止
app.stop_watching()

# アプリケーションを実行（トレイに常駐）
app.run()
```

### FileUploadHandler（`service/file_upload_handler.py`）

ファイルシステム監視とバッチ処理キューを管理します。

- **機能**:
  - ファイル作成/移動イベント検出
  - ファイル名パターンマッチング
  - バッチキューイング（5秒遅延）
  - ファイル削除

**バッチ処理動作**:
1. ファイル検出時にキューに追加
2. 新しいファイルが来るとタイマーをリセット
3. 5秒間新規ファイルなし→全キューファイルを一括アップロード

### MegaUploader（`service/mega_uploader.py`）

Playwrightを使用したブラウザ自動化によるアップロード処理。

- **機能**:
  - ファイル選択インタフェースの自動操作
  - アップロード完了待機（最大30秒）
  - 単一ファイルと複数ファイルのアップロード

**使用例**:
```python
from pathlib import Path
from service.mega_uploader import MegaUploader

uploader = MegaUploader("https://mega.nz/filerequest/xxxxx")
files = [Path("file1.txt"), Path("file2.txt")]
uploaded = uploader.upload_files(files)
# uploaded: アップロード成功したファイルのパスリスト
```

### ConfigManager（`utils/config_manager.py`）

設定ファイル（`config.ini`）からの値を型安全に取得します。

## 開発

### 開発環境のセットアップ

```bash
# 仮想環境の有効化
.venv\Scripts\activate

# 開発依存パッケージのインストール
pip install -r requirements.txt

# Playwrightブラウザのインストール
playwright install chromium
```

### テスト実行

```bash
# 全テストを実行
python -m pytest tests/ -v --tb=short --disable-warnings

# 特定のテストファイルを実行
python -m pytest tests/test_tray_app.py -v

# カバレッジレポート付きで実行
python -m pytest tests/ --cov=app --cov=service --cov=utils
```

### 型チェック

```bash
pyright
```

設定は`pyrightconfig.json`（Python 3.13、標準モード）。

### 実行ファイルのビルド

```bash
python build.py
```

PyInstallerを使用して、以下をバンドルした実行ファイルを生成します:
- `utils/config.ini`設定ファイル
- Playwrightブラウザ（Chromium）
- すべての依存パッケージ

ビルド結果は`dist/MEGATransfer.exe`に出力されます。

## トラブルシューティング

### ファイルが検出されない

1. `config.ini`の監視フォルダパスが正確か確認
2. ファイル名パターンが正規表現として正しいか確認
   ```ini
   # 末尾が "_magnate" で終わるファイルにマッチ
   pattern = _magnate
   # この場合、"document_magnate.pdf" は検出されます
   ```
3. アプリケーションのログを確認（`logs/MEGATransfer.log`）

### アップロードが完了しない

1. MEGAファイルリクエストURLが有効か確認
2. ネットワーク接続を確認
3. `config.ini`の`max_wait_time`を増やす
   ```ini
   max_wait_time = 60  # デフォルト30秒から60秒に変更
   ```

### ブラウザが起動しない

1. Playwrightが正しくインストールされているか確認
   ```bash
   playwright install chromium
   ```
2. Windowsの実行ポリシーを確認
3. 管理者権限でアプリケーションを実行してみる

## バージョン情報

- **現在のバージョン**: 1.0.0
- **最終更新日**: 2025年12月24日

## ライセンス

このプロジェクトのライセンス情報については、 [LICENSE](./LICENSE) を参照してください。

## 更新履歴

更新履歴は [CHANGELOG.md](./CHANGELOG.md) を参照してください。
