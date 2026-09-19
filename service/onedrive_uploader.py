import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Page, Response, sync_playwright

from utils.config_manager import (
    get_headless,
    get_max_wait_time,
    get_post_upload_wait,
    get_replace_button_text,
)

logger = logging.getLogger(__name__)

# OneDriveのWeb画面がファイル本体を送信するAPI
UPLOAD_API_PATH = "/Files/AddUsingPath("
NEW_COMMAND_SELECTOR = '[data-automationid="newCommand"]'
UPLOAD_FILE_SELECTOR = '[data-automationid="uploadFile"]'
REPLACE_BUTTON_TIMEOUT_MS = 5000


class OneDriveUploader:
    """OneDrive共有フォルダへのアップロードを実施"""

    def __init__(self, url: str):
        self.url = url
        self.replace_button_text = get_replace_button_text()
        self.max_wait_time = get_max_wait_time()
        self.headless = get_headless()
        self.post_upload_wait = get_post_upload_wait()
        logger.debug(f"OneDriveUploader初期化: post_upload_wait={self.post_upload_wait}秒")

    @contextmanager
    def _open_folder_page(self) -> Generator[Page, None, None]:
        """Edgeを起動し共有フォルダのページを開く"""
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=self.headless)
            # ボタンを表示テキストで探すため表示言語を固定する
            page = browser.new_page(locale="ja-JP")
            page.goto(self.url)
            page.wait_for_load_state("networkidle")
            try:
                yield page
            finally:
                browser.close()
                logger.debug("ブラウザを閉じました")

    @staticmethod
    def _is_upload_response(response: Response) -> bool:
        return response.request.method == "POST" and UPLOAD_API_PATH in response.url

    def _send_file(self, page: Page, file_path: Path) -> Response:
        """アップロードメニューからファイルを選択し、送信APIの応答を返す"""
        with page.expect_response(self._is_upload_response, timeout=self.max_wait_time * 1000) as response_info:
            page.locator(NEW_COMMAND_SELECTOR).click()
            with page.expect_file_chooser() as chooser_info:
                page.locator(UPLOAD_FILE_SELECTOR).click()
            chooser_info.value.set_files(str(file_path))
        return response_info.value

    def _replace_existing_file(self, page: Page) -> Response:
        """同名ファイルの通知で「置き換える」を押し、再送信の応答を返す"""
        with page.expect_response(self._is_upload_response, timeout=self.max_wait_time * 1000) as response_info:
            replace_button = page.get_by_role("button", name=self.replace_button_text)
            replace_button.click(timeout=REPLACE_BUTTON_TIMEOUT_MS)
        return response_info.value

    def _upload_single_file(self, page: Page, file_path: Path) -> bool:
        """1つのファイルをアップロードする

        画面表示ではなく送信APIの応答で完了を判定する。
        同名ファイルがあると応答がエラーになり「置き換える」の通知が出る。
        """
        logger.info(f"アップロード開始: {file_path.name}")

        try:
            response = self._send_file(page, file_path)
            if not response.ok:
                logger.info(f"送信が拒否されたため上書きを試みます（HTTP {response.status}）: {file_path.name}")
                response = self._replace_existing_file(page)

            if not response.ok:
                logger.warning(f"アップロードが拒否されました（HTTP {response.status}）: {file_path.name}")
                return False

            logger.info(f"アップロード完了: {file_path.name}")
            time.sleep(self.post_upload_wait)
            return True

        except Exception as e:
            logger.error(f"アップロード失敗: {file_path.name} - {e}")
            return False

    def upload_files(self, file_paths: list[Path]) -> list[Path]:
        """
        複数ファイルをOneDrive共有フォルダにアップロードする

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
            with self._open_folder_page() as page:
                for i, file_path in enumerate(file_paths, 1):
                    logger.info(f"進捗: {i}/{len(file_paths)} - {file_path.name}")
                    if self._upload_single_file(page, file_path):
                        uploaded_files.append(file_path)
        except Exception as e:
            logger.error(f"Playwrightによるアップロード失敗: {e}")

        logger.info(f"{len(uploaded_files)}/{len(file_paths)}件のファイルをアップロードしました")
        return uploaded_files
