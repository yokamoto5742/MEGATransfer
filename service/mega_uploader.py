import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page


class MegaUploader:
    """MEGAファイルリクエストへのアップロードを実施"""

    # アップロード完了を示すテキスト
    UPLOAD_COMPLETE_TEXT = "アップロード済み"
    # 完了チェックの最大待機時間（秒）
    MAX_WAIT_TIME = 300
    # 完了チェックの間隔（秒）
    CHECK_INTERVAL = 0.5

    def __init__(self, url: str):
        self.url = url

    def _wait_for_upload_complete(self, page: Page) -> bool:
        """「アップロード済み」テキストが表示されるまで待機"""
        elapsed = 0
        while elapsed < self.MAX_WAIT_TIME:
            # ページ内に「アップロード済み」テキストが存在するか確認
            if page.locator(f"text={self.UPLOAD_COMPLETE_TEXT}").count() > 0:
                return True
            time.sleep(self.CHECK_INTERVAL)
            elapsed += self.CHECK_INTERVAL
        return False

    def _upload_single_file(self, page: Page, file_path: Path) -> bool:
        """1つのファイルをアップロードする（ブラウザは開いたまま）"""
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
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()

                # MEGAのURLへ移動
                page.goto(self.url)

                # ページのロード完了を待機
                page.wait_for_load_state("networkidle")

                result = self._upload_single_file(page, file_path)

                browser.close()
                return result

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
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()

                # MEGAのURLへ移動
                page.goto(self.url)

                # ページのロード完了を待機
                page.wait_for_load_state("networkidle")

                for i, file_path in enumerate(file_paths, 1):
                    print(f"[進捗] {i}/{len(file_paths)} - {file_path.name}")

                    if self._upload_single_file(page, file_path):
                        uploaded_files.append(file_path)

                    # 次のファイルアップロードのために少し待機
                    if i < len(file_paths):
                        time.sleep(1)

                browser.close()

        except Exception as e:
            print(f"[エラー] Playwrightによるアップロード失敗: {e}")

        print(f"[完了] {len(uploaded_files)}/{len(file_paths)}件のファイルをアップロードしました")
        return uploaded_files
