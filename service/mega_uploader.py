import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from utils.config_manager import (
    get_check_interval,
    get_headless,
    get_max_wait_time,
    get_post_upload_wait,
    get_upload_complete_text,
)

logger = logging.getLogger(__name__)


class MegaUploader:
    """MEGAファイルリクエストへのアップロードを実施"""

    def __init__(self, url: str):
        self.url = url
        self.upload_complete_text = get_upload_complete_text()
        self.max_wait_time = get_max_wait_time()
        self.check_interval = get_check_interval()
        self.headless = get_headless()
        self.post_upload_wait = get_post_upload_wait()
        logger.debug(f"MegaUploader初期化: post_upload_wait={self.post_upload_wait}秒")

    @contextmanager
    def _open_mega_page(self) -> Generator[Page, None, None]:
        """Chromeブラウザを起動しMEGAページを開く"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            page.goto(self.url)
            page.wait_for_load_state("networkidle")
            try:
                yield page
            finally:
                browser.close()
                logger.debug("ブラウザを閉じました")

    def _wait_for_upload_complete(self, page: Page) -> bool:
        """指定したアップロード済み表示がなされるまで待機"""
        elapsed = 0.0
        while elapsed < self.max_wait_time:
            if page.locator(f"text={self.upload_complete_text}").count() > 0:
                logger.debug(f"「{self.upload_complete_text}」を検出しました（経過時間: {elapsed}秒）")
                return True
            time.sleep(self.check_interval)
            elapsed += self.check_interval
        logger.debug(f"「{self.upload_complete_text}」の検出がタイムアウトしました（経過時間: {elapsed}秒）")
        return False

    def _upload_single_file(self, page: Page, file_path: Path) -> bool:
        """1つのファイルをアップロードする"""
        logger.info(f"アップロード開始: {file_path.name}")

        try:
            # input[type="file"] を探してファイルをセットする
            file_input = page.locator('input[type="file"]')

            if file_input.count() > 0:
                file_input.set_input_files(str(file_path))
                logger.debug("ファイルを選択しました")

                if self._wait_for_upload_complete(page):
                    logger.info(f"アップロード完了: {file_path.name}")
                    logger.debug(f"アップロード完了後の待機開始: {self.post_upload_wait}秒")
                    time.sleep(self.post_upload_wait)
                    logger.debug("アップロード完了後の待機終了")
                    return True
                else:
                    logger.warning(f"完了確認がタイムアウトしました: {file_path.name}")
                    return False
            else:
                logger.error("アップロード用のinputタグが見つかりませんでした")
                return False

        except Exception as e:
            logger.error(f"アップロード失敗: {file_path.name} - {e}")
            return False

    def upload_file(self, file_path: Path) -> bool:
        """指定された単一ファイルをMEGAにアップロードする"""
        logger.info(f"MEGAへの接続: {file_path.name}")
        try:
            with self._open_mega_page() as page:
                return self._upload_single_file(page, file_path)
        except Exception as e:
            logger.error(f"Playwrightによるアップロード失敗: {e}")
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
            logger.info("アップロードするファイルがありません")
            return []

        logger.info(f"{len(file_paths)}件のファイルをアップロードします")
        uploaded_files: list[Path] = []

        try:
            with self._open_mega_page() as page:
                for i, file_path in enumerate(file_paths, 1):
                    logger.info(f"進捗: {i}/{len(file_paths)} - {file_path.name}")
                    if self._upload_single_file(page, file_path):
                        uploaded_files.append(file_path)
        except Exception as e:
            logger.error(f"Playwrightによるアップロード失敗: {e}")

        logger.info(f"{len(uploaded_files)}/{len(file_paths)}件のファイルをアップロードしました")
        return uploaded_files
