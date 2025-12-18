import time
from pathlib import Path
from playwright.sync_api import sync_playwright


class MegaUploader:
    """MEGAファイルリクエストへのアップロードを実施"""

    def __init__(self, url: str):
        self.url = url

    def upload_file(self, file_path: Path) -> bool:
        """指定されたファイルをMEGAにアップロードする"""
        print(f"[アップロード開始] MEGAへの接続: {file_path.name}")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()

                # MEGAのURLへ移動
                page.goto(self.url)

                # ページのロード完了を待機
                page.wait_for_load_state("networkidle")

                # input[type="file"] を探してファイルをセットする
                file_input = page.locator('input[type="file"]')

                if file_input.count() > 0:
                    file_input.set_input_files(str(file_path))
                    print(f"[アップロード中...] ファイルを選択しました")

                    try:
                        # 例: "完了" や "Thank you" などの要素が表示されるのを待つ
                        time.sleep(5)
                        print(f"[アップロード完了] (推定): {file_path.name}")
                    except Exception as e:
                        print(f"[警告] 完了確認中にタイムアウトしました: {e}")
                else:
                    print("[エラー] アップロード用のinputタグが見つかりませんでした")
                    browser.close()
                    return False

                browser.close()
                return True

        except Exception as e:
            print(f"[エラー] Playwrightによるアップロード失敗: {e}")
            return False
