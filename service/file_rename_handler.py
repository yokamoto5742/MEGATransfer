import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from utils.config_manager import get_rename_pattern, get_wait_time, get_mega_url
from service.mega_uploader import MegaUploader


class FileRenameHandler(FileSystemEventHandler):
    """ファイルシステムイベントを処理し、アップロードとリネームを行うハンドラー"""

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
        """ファイル移動時の処理（フォルダに移動されてきたファイル）"""
        if event.is_directory:
            return
        self._process_file(event.dest_path)

    def _process_file(self, file_path: str):
        """ファイルを処理する（アップロード -> リネーム）"""
        # ファイル書き込み完了を待つ
        time.sleep(self.wait_time)

        path = Path(file_path)
        if not path.exists():
            return

        filename = path.stem  # 拡張子を除いたファイル名
        extension = path.suffix  # 拡張子

        if self.should_process(filename):
            print(f"[検知] 対象ファイルが見つかりました: {filename}")

            # 1. MEGAへアップロード
            upload_success = self.uploader.upload_file(path)

            if upload_success:
                print(f"[成功] アップロードが完了しました")
            else:
                print(f"[失敗] アップロードに失敗しました。処理を継続します。")

            # 2. リネーム処理 (元のロジック)
            self.rename_file(path, filename, extension)

    def should_process(self, filename: str) -> bool:
        """ファイル名が処理対象かどうかを判定"""
        return bool(self.pattern.search(filename))

    def rename_file(self, file_path: Path, filename: str, extension: str):
        """ファイル名を変換する"""
        # パターンに一致する部分を削除
        new_filename = self.pattern.sub('', filename)
        new_file_path = file_path.parent / f"{new_filename}{extension}"

        # 変換後のファイル名が既に存在する場合
        if new_file_path.exists():
            print(f"[スキップ] 変換後のファイルが既に存在します: {new_file_path}")
            return

        try:
            file_path.rename(new_file_path)
            print(f"[成功] リネーム完了:")
            print(f"  変換前: {file_path.name}")
            print(f"  変換後: {new_file_path.name}")
        except PermissionError:
            print(f"[エラー] ファイルにアクセスできません: {file_path}")
        except OSError as e:
            print(f"[エラー] リネーム失敗: {e}")
