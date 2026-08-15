import logging
import os
import shutil
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from service.mega_uploader import MegaUploader
from utils.config_manager import (
    get_batch_delay,
    get_mega_url,
    get_rename_pattern,
    get_uploaded_dir,
    get_uploaded_retention_hours,
    get_wait_time,
)

logger = logging.getLogger(__name__)


class FileUploadHandler(FileSystemEventHandler):
    """ファイルをMEGAにアップロードするハンドラー"""

    def __init__(self):
        super().__init__()
        self.pattern = get_rename_pattern()
        self.wait_time = get_wait_time()
        self.batch_delay = get_batch_delay()
        self.uploaded_dir = Path(get_uploaded_dir())
        self.retention_hours = get_uploaded_retention_hours()

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
        self._add_to_queue(str(event.src_path))

    def on_moved(self, event):
        """フォルダに移動されてきたファイルの処理"""
        if event.is_directory:
            return
        self._add_to_queue(str(event.dest_path))

    def _add_to_queue(self, file_path: str):
        """ファイルをキューに追加しバッチ処理タイマーをリセット"""
        # ファイル書き込み完了を待つ
        time.sleep(self.wait_time)

        path = Path(file_path)
        if not path.exists():
            return
        # 拡張子を除いたファイル名
        filename = path.stem

        if self.should_process(filename):
            logger.info(f"対象ファイルが見つかりました: {filename}")

            with self._lock:
                # 既にキューにある場合は追加しない
                if path not in self._pending_files:
                    self._pending_files.append(path)
                    logger.info(f"現在{len(self._pending_files)}件のファイルが待機中")

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

        logger.info(f"バッチ処理開始: {len(files_to_process)}件のファイルを処理します")

        # 複数ファイルを一括アップロード
        uploaded_files = self.uploader.upload_files(files_to_process)

        # アップロードに成功したファイルを保管先へ移動
        if uploaded_files:
            self._move_uploaded_files(uploaded_files)
            self.cleanup_uploaded_dir()

        # 処理結果のサマリーを表示
        failed_count = len(files_to_process) - len(uploaded_files)
        if failed_count > 0:
            logger.warning(f"{failed_count}件のファイルがアップロードに失敗しました")

    def _move_uploaded_files(self, files: list[Path]):
        """アップロード完了したファイルを保管先へ移動"""
        logger.info(f"{len(files)}件のファイルを移動します")

        try:
            self.uploaded_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"保管先ディレクトリを作成できませんでした: {self.uploaded_dir}: {e}")
            return

        for file_path in files:
            try:
                if file_path.exists():
                    destination = self._resolve_destination(file_path.name)
                    shutil.move(str(file_path), str(destination))
                    # 保管時刻を基準に削除するため更新日時を現在時刻にする
                    os.utime(destination, None)
                    logger.info(f"移動完了: {file_path.name} -> {destination}")
            except Exception as e:
                logger.error(f"移動失敗: {file_path.name}: {e}")

        logger.info("すべてのファイルの移動処理が完了しました")

    def _resolve_destination(self, filename: str) -> Path:
        """保管先に同名ファイルがある場合は連番を付けて衝突を避ける"""
        destination = self.uploaded_dir / filename
        if not destination.exists():
            return destination

        name = Path(filename)
        counter = 1
        while destination.exists():
            destination = self.uploaded_dir / f"{name.stem}_{counter}{name.suffix}"
            counter += 1
        return destination

    def cleanup_uploaded_dir(self):
        """保管先の保持時間を過ぎたファイルを削除"""
        if not self.uploaded_dir.exists():
            return

        threshold = time.time() - self.retention_hours * 3600
        deleted_count = 0

        for file_path in self.uploaded_dir.iterdir():
            if not file_path.is_file():
                continue
            try:
                if file_path.stat().st_mtime < threshold:
                    file_path.unlink()
                    deleted_count += 1
            except OSError as e:
                logger.error(f"保管ファイルの削除に失敗しました: {file_path.name}: {e}")

        if deleted_count > 0:
            logger.info(f"{deleted_count}件の保管ファイルを削除しました")

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

        found_count = 0
        for file_path in dir_path.iterdir():
            if file_path.is_file() and self.should_process(file_path.stem):
                logger.info(f"既存の対象ファイルが見つかりました: {file_path.name}")
                with self._lock:
                    if file_path not in self._pending_files:
                        self._pending_files.append(file_path)
                        found_count += 1

        if found_count > 0:
            logger.info(f"{found_count}件の既存ファイルをキューに追加しました")
            self._reset_timer()
        else:
            logger.info("処理対象の既存ファイルはありませんでした")
