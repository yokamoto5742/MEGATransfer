import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from utils.config_manager import get_rename_pattern, get_wait_time, get_mega_url
from service.mega_uploader import MegaUploader


class FileUploadHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理するハンドラー"""

    def __init__(self):
        super().__init__()
        self.pattern = get_rename_pattern()
        self.wait_time = get_wait_time()

        # MEGAアップローダーの初期化
        mega_url = get_mega_url()
        self.uploader = MegaUploader(mega_url)

    def on_created(self, event):
        """新規ファイル作成時の処理"""
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_moved(self, event):
        """フォルダに移動されてきたファイルの処理"""
        if event.is_directory:
            return
        self._process_file(event.dest_path)

    def _process_file(self, file_path: str):
        """ファイルを処理する（アップロード -> 削除）"""
        # ファイル書き込み完了を待つ
        time.sleep(self.wait_time)

        path = Path(file_path)
        if not path.exists():
            return

        filename = path.stem  # 拡張子を除いたファイル名

        if self.should_process(filename):
            print(f"[検知] 対象ファイルが見つかりました: {filename}")

            # 1. MEGAへアップロード
            upload_success = self.uploader.upload_file(path)

            if upload_success:
                print(f"[成功] アップロードが完了しました")
            else:
                print(f"[失敗] アップロードに失敗しました。")

    def should_process(self, filename: str) -> bool:
        """ファイル名が処理対象かどうかを判定"""
        return bool(self.pattern.search(filename))
