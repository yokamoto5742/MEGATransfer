# MEGATransfer

Windows システムトレイアプリケーション。指定ディレクトリを監視し、ファイル名のパターンごとに指定したOneDrive共有フォルダへファイルを自動アップロードします。アップロード完了後、ファイルは保管先に移動され、一定時間経過後に自動削除されます。

## 主な特徴

- ファイルシステム監視による自動検出と処理
- Microsoft Edgeを使用したブラウザ自動化によるアップロード
- 複数ファイルのバッチ処理に対応
- システムトレイインテグレーション
- ファイル名パターンごとのアップロード先振り分け
- アップロード完了後ファイルの自動移動・保管と時間経過による自動削除
- 多重起動防止（ユーザーセッション単位）

## 前提条件

- **OS**: Windows 11
- **Python**: 3.13以上
- **ブラウザ**: Microsoft Edge（PC既存）

## インストール

1. リポジトリをクローンします
```bash
git clone https://github.com/yokamoto5742/MEGATransfer
cd MEGATransfer
```

2. 依存関係をインストールします（`uv` 使用）
```bash
uv sync
```

3. プロジェクトルートに `.env` を作成し、OneDrive共有フォルダのURLを記載します（Git管理外）
```ini
Taskdiary=<onedrive-shared-folder-url>
Receive_file=<onedrive-shared-folder-url>
```

4. 設定ファイルを編集します（`utils/config.ini`）
```ini
[Paths]
src_dir = <directory-to-monitor>
uploaded_dir = <directory-for-uploaded-files>

[filename]
Taskdiary_pattern = <filename-pattern>
Receive_file_pattern = <filename-pattern>
```

## 使用方法

### アプリケーション実行

```bash
python main.py
```

アプリケーションはシステムトレイに常駐します。トレイアイコンからフォルダを開く、または終了できます。

### 設定ファイル（`utils/config.ini`）

アップロード先のURLは `config.ini` ではなく `.env` の同名キー（`Taskdiary`、`Receive_file`）で指定します。

```ini
[Paths]
src_dir = C:\Users\yokam\Desktop\target
# アップロード済みファイルの保管先（未設定時は src_dir/_uploaded）
uploaded_dir = C:\Users\yokam\Desktop\uploaded

[filename]
# ファイル名パターン（拡張子を除いたファイル名の末尾にマッチ）。.env の同名キーのURLへ転送
Taskdiary_pattern = _taskdiary
Receive_file_pattern = _magnate
# アップロード時にファイル名末尾のパターンを削除するか（例: test_magnate.md → test.md）
# True の場合、ステム末尾のパターン部分を削除した名前でアップロードする
# ローカルおよび保管先のファイル名は元のまま変わらない
Taskdiary_strip_pattern = False
Receive_file_strip_pattern = True

[App]
# ファイル書き込み完了を待つ時間（秒）
wait_time = 0.5
# バッチ処理開始までの待機時間（秒）
batch_delay = 3.0
# アップロード済みファイルを保管先に残す時間（時間）
uploaded_retention_hours = 4

[Uploader]
# 同名ファイルがある場合に表示される上書きボタンのテキスト
replace_button_text = 置き換える
# アップロード応答の最大待機時間（秒）
max_wait_time = 120
# ブラウザをヘッドレスモードで実行するか
headless = True
# アップロード完了後の待機時間（秒）
post_upload_wait = 1.0

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
│   └── onedrive_uploader.py      # PlaywrightによるOneDriveアップロード実装
├── utils/                        # ユーティリティ
│   ├── __init__.py
│   ├── config.ini                # 設定ファイル
│   ├── config_manager.py         # 設定ローディング
│   ├── env_loader.py             # .env読み込み
│   ├── log_rotation.py           # ログ管理
│   └── single_instance.py        # 多重起動防止
├── tests/                        # テストスイート
│   ├── __init__.py
│   ├── test_tray_app.py
│   ├── test_config_manager.py
│   ├── test_file_upload_handler.py
│   ├── test_onedrive_uploader.py
│   └── test_single_instance.py
├── main.py                       # エントリーポイント
├── build.py                      # 実行ファイルビルドスクリプト
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
  - 多重起動防止（ユーザーセッション単位のミューテックス）

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
  - ファイル名パターンによるアップロード先の判定
  - バッチキューイング
  - アップロード完了後、ファイルを保管先に移動

**バッチ処理動作**:
1. ファイル検出時にキューに追加
2. 新しいファイルが来るとタイマーをリセット
3. `batch_delay` 秒間新規ファイルなし→キューのファイルをアップロード先ごとにまとめ、順番にアップロード
4. アップロード成功後、ファイルを `uploaded_dir` に移動

**アップロード済みファイルの自動削除**:
  `uploaded_dir` 内のファイルは、`uploaded_retention_hours` で指定した時間（デフォルト4時間）を過ぎると自動削除されます。削除判定は最終更新日時（mtime）を基準とし、アプリ起動時とアップロード完了後に実行されます。

### OneDriveUploader（`service/onedrive_uploader.py`）

Microsoft Edgeブラウザの自動化によるOneDrive共有フォルダへのアップロード処理。

- **機能**:
  - 「作成またはアップロード」→「ファイルのアップロード」の自動操作
  - アップロード完了待機（送信APIの応答で判定）
  - 同名ファイルがある場合は「置き換える」で上書き
  - 設定により、ファイル名末尾のパターン部分を削除した名前でアップロード（ローカル・保管先は元の名前のまま）

**アップロード完了判定**:
  画面表示ではなく、OneDriveがファイルを送信するAPI（`Files/AddUsingPath`）の応答で判定します。成功応答で完了、エラー応答の場合は「置き換える」を押して再送信し、その応答で判定します。

**ファイル名変換**:
  config.iniの `<名前>_strip_pattern = True` の場合、ステム末尾のパターン部分を削除した名前でアップロードします（例: `test_magnate.md` → `test.md`）。ローカルのファイル名および保管先への移動後のファイル名は元の名前のままです。

**使用例**:
```python
from pathlib import Path
from service.onedrive_uploader import OneDriveUploader

uploader = OneDriveUploader("https://1drv.ms/f/c/xxxxx")
files = [Path("file1.txt"), Path("file2.txt")]
uploaded = uploader.upload_files(files)
# uploaded: アップロード成功したファイルのパスリスト
```

### ConfigManager（`utils/config_manager.py`）

設定ファイル（`config.ini`）からの値を型安全に取得します。

## 開発

### 開発環境セットアップ

```bash
# 依存関係のインストール
uv sync

# 型チェック
pyright
```

### テスト実行

```bash
# 全テストを実行
python -m pytest tests/ -v --tb=short

# 特定のテストファイルを実行
python -m pytest tests/test_tray_app.py -v

# カバレッジレポート付きで実行
python -m pytest tests/ --cov=app --cov=service --cov=utils --cov-report=html
```

### 実行ファイルのビルド

```bash
python build.py
```

PyInstallerを使用して、以下をバンドルした実行ファイルを生成します:
- `utils/config.ini` 設定ファイル
- `.env`（アップロード先URL。ビルド前にプロジェクトルートに配置が必要）
- すべての依存パッケージ

ビルド結果は `dist/MEGATransfer.exe` に出力されます。

**注意**: 実行ファイルはMicrosoft Edgeを使用するため、配布先PCに Microsoft Edge がインストールされている必要があります。

## トラブルシューティング

### ファイルが検出されない

1. `config.ini`の監視フォルダパスが正確か確認
2. ファイル名パターンの確認
   ```ini
   # 末尾が "_magnate" で終わるファイル（拡張子前）にマッチ
   Receive_file_pattern = _magnate
   # 例："document_magnate.pdf" は検出されます
   ```
3. アプリケーションのログを確認（`logs/MEGATransfer.log`）

### アップロードが完了しない

1. `.env` のOneDrive共有フォルダのURLが有効か（編集可能リンクか）確認
2. ネットワーク接続を確認
3. `config.ini`の `max_wait_time` を増やす
   ```ini
   max_wait_time = 180  # デフォルト120秒から180秒に変更
   ```
4. ブラウザの `headless` 設定を試す（`headless = False` で実際の動作を確認）

### アップロード済みファイルが削除されない

1. `uploaded_dir` パスが正確か確認
2. `uploaded_retention_hours` の値を確認（デフォルト4時間）
3. ファイルの最終更新日時が古いか確認
4. ログで削除処理が実行されているか確認

### ブラウザが起動しない

1. Microsoft Edge がインストールされているか確認（PC既存のEdgeを使用）
2. Edge のバージョンが最新か確認
3. Windowsの実行ポリシーを確認
4. 管理者権限でアプリケーションを実行してみる

## ライセンス

このプロジェクトのライセンス情報については、 [LICENSE](docs/LICENSE) を参照してください。

## 更新履歴

更新履歴は [CHANGELOG.md](docs/CHANGELOG.md) を参照してください。
