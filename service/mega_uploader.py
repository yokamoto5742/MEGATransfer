import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from utils.config_manager import (
    get_check_interval,
    get_headless,
    get_max_wait_time,
    get_upload_complete_text,
)


class MegaUploader:
    """MEGAファイルリクエストへのアップロードを実施"""

    def __init__(self, url: str):
        self.url = url
        self.upload_complete_text = get_upload_complete_text()
        self.max_wait_time = get_max_wait_time()
        self.check_interval = get_check_interval()
        self.headless = get_headless()

    @contextmanager
    def _open_mega_page(self) -> Generator[Page, None, None]:
        """ブラウザを起動しMEGAページを開く"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(self.url)
            page.wait_for_load_state("networkidle")
            try:
                yield page
            finally:
                browser.close()

    def _wait_for_upload_complete(self, page: Page) -> bool:
        """「アップロード済み」が表示されるまで待機"""
        elapsed = 0.0
        while elapsed < self.max_wait_time:
            # ページ内に「アップロード済み」が存在するか確認
            if page.locator(f"text={self.upload_complete_text}").count() > 0:
                return True
            time.sleep(self.check_interval)
            elapsed += self.check_interval
        return False

    def _upload_single_file(self, page: Page, file_path: Path) -> bool:
        """1つのファイルをアップロードする）"""
        print(f"[アップロード開始] {file_path.name}")

        try:
            # input[type="file"] を探してファイルをセットする
            file_input = page.locator('input[type="file"]')

            if file_input.count() > 0:
                file_input.set_input_files(str(file_path))
                print(f"[アップロード中...] ファイルを選択しました")

                # 「アップロード済み」表示を待機
                if self._wait_for_upload_complete(page):
                    print(f"[アップロード完了] {file_path.name}")
                    return True
                else:
                    print(f"[警告] 完了確認がタイムアウトしました: {file_path.name}")
                    return False
            else:
                print("[エラー] アップロード用のinputタグが見つかりませんでした")
                return False

        except Exception as e:
            print(f"[エラー] アップロード失敗: {file_path.name} - {e}")
            return False

    def upload_file(self, file_path: Path) -> bool:
        """指定されたファイルをMEGAにアップロードする（単一ファイル用）"""
        print(f"[アップロード開始] MEGAへの接続: {file_path.name}")
        try:
            with self._open_mega_page() as page:
                return self._upload_single_file(page, file_path)
        except Exception as e:
            print(f"[エラー] Playwrightによるアップロード失敗: {e}")
            return False

    def upload_files(self, file_paths: list[Path]) -> list[Path]:
        """
        複数ファイルをMEGAにアップロードする

        Args:
            file_paths: アップロードするファイルのパスリスト

        Returns:
            アップロードに成功したファイルのパスリスト
        """
        if not file_paths:
            print("[情報] アップロードするファイルがありません")
            return []

        print(f"[開始] {len(file_paths)}件のファイルをアップロードします")
        uploaded_files: list[Path] = []

        try:
            with self._open_mega_page() as page:
                for i, file_path in enumerate(file_paths, 1):
                    print(f"[進捗] {i}/{len(file_paths)} - {file_path.name}")
                    if self._upload_single_file(page, file_path):
                        uploaded_files.append(file_path)
        except Exception as e:
            print(f"[エラー] Playwrightによるアップロード失敗: {e}")

        print(f"[完了] {len(uploaded_files)}/{len(file_paths)}件のファイルをアップロードしました")
        return uploaded_files
