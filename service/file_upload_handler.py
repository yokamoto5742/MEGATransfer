import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from utils.config_manager import get_batch_delay, get_mega_url, get_rename_pattern, get_wait_time
from service.mega_uploader import MegaUploader


class FileUploadHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理するハンドラー"""

    def __init__(self):
        super().__init__()
        self.pattern = get_rename_pattern()
        self.wait_time = get_wait_time()
        self.batch_delay = get_batch_delay()

        # MEGAアップローダーの初期化
        mega_url = get_mega_url()
        self.uploader = MegaUploader(mega_url)

        # 複数ファイル処理用のキュー
        self._pending_files: list[Path] = []
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def on_created(self, event):
        """新規ファイル作成時の処理"""
        if event.is_directory:
            return
        self._add_to_queue(event.src_path)

    def on_moved(self, event):
        """フォルダに移動されてきたファイルの処理"""
        if event.is_directory:
            return
        self._add_to_queue(event.dest_path)

    def _add_to_queue(self, file_path: str):
        """ファイルをキューに追加し、バッチ処理タイマーをリセット"""
        # ファイル書き込み完了を待つ
        time.sleep(self.wait_time)

        path = Path(file_path)
        if not path.exists():
            return
        # 拡張子を除いたファイル名
        filename = path.stem

        if self.should_process(filename):
            print(f"[検知] 対象ファイルが見つかりました: {filename}")

            with self._lock:
                # 既にキューにある場合は追加しない
                if path not in self._pending_files:
                    self._pending_files.append(path)
                    print(f"[キュー追加] 現在{len(self._pending_files)}件のファイルが待機中")

                # タイマーをリセット（新しいファイルが来たら処理開始を遅延）
                self._reset_timer()

    def _reset_timer(self):
        """バッチ処理タイマーをリセット"""
        if self._timer:
            self._timer.cancel()

        self._timer = threading.Timer(self.batch_delay, self._process_pending_files)
        self._timer.start()

    def _process_pending_files(self):
        """キュー内のすべてのファイルを一括処理"""
        with self._lock:
            if not self._pending_files:
                return

            files_to_process = self._pending_files.copy()
            self._pending_files.clear()

        print(f"[バッチ処理開始] {len(files_to_process)}件のファイルを処理します")

        # 複数ファイルを一括アップロード
        uploaded_files = self.uploader.upload_files(files_to_process)

        # アップロードに成功したファイルを削除
        if uploaded_files:
            self._delete_uploaded_files(uploaded_files)

        # 処理結果のサマリーを表示
        failed_count = len(files_to_process) - len(uploaded_files)
        if failed_count > 0:
            print(f"[警告] {failed_count}件のファイルがアップロードに失敗しました")

    def _delete_uploaded_files(self, files: list[Path]):
        """アップロード完了したファイルを削除"""
        print(f"[削除開始] {len(files)}件のファイルを削除します")

        for file_path in files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    print(f"[削除完了] {file_path.name}")
            except Exception as e:
                print(f"[削除失敗] {file_path.name}: {e}")

        print(f"[削除完了] すべてのファイルの削除処理が完了しました")

    def should_process(self, filename: str) -> bool:
        """ファイル名が処理対象かどうかを判定"""
        return bool(self.pattern.search(filename))

    def get_pending_count(self) -> int:
        """待機中のファイル数を取得"""
        with self._lock:
            return len(self._pending_files)

    def process_now(self):
        """タイマーを待たずに即座に処理を開始"""
        if self._timer:
            self._timer.cancel()
        self._process_pending_files()

    def scan_existing_files(self, directory: str):
        """指定ディレクトリ内の既存ファイルをスキャンしてキューに追加"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        print(f"[スキャン] 既存ファイルを確認しています: {directory}")

        found_count = 0
        for file_path in dir_path.iterdir():
            if file_path.is_file() and self.should_process(file_path.stem):
                print(f"[検知] 既存の対象ファイルが見つかりました: {file_path.name}")
                with self._lock:
                    if file_path not in self._pending_files:
                        self._pending_files.append(file_path)
                        found_count += 1

        if found_count > 0:
            print(f"[スキャン完了] {found_count}件の既存ファイルをキューに追加しました")
            self._reset_timer()
        else:
            print("[スキャン完了] 処理対象の既存ファイルはありませんでした")
