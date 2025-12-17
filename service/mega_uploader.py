import time
from pathlib import Path
from playwright.sync_api import sync_playwright


class MegaUploader:
    """MEGAファイルリクエストへのアップロードを担当するクラス"""

    def __init__(self, url: str):
        self.url = url

    def upload_file(self, file_path: Path) -> bool:
        """指定されたファイルをMEGAにアップロードする"""
        print(f"[アップロード開始] MEGAへの接続: {file_path.name}")

        try:
            with sync_playwright() as p:
                # トレイアプリとして動作するため headless=True (画面を表示しない)
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # MEGAのURLへ移動
                page.goto(self.url)

                # ページのロード完了を待機
                page.wait_for_load_state("networkidle")

                # input[type="file"] を探してファイルをセットする
                # MEGAのFile Requestページは標準的なファイル入力を持っていることが多い
                file_input = page.locator('input[type="file"]')

                if file_input.count() > 0:
                    file_input.set_input_files(str(file_path))
                    print(f"[アップロード中...] ファイルを選択しました")

                    # アップロード完了を待機するためのロジック
                    # 完了メッセージが出るか、あるいは一定時間待機する
                    # 注: MEGAの仕様に合わせて調整が必要な場合があります
                    try:
                        # 例: "完了" や "Thank you" などの要素が表示されるのを待つ
                        # ここでは汎用的に少し長めに待機しつつ、進捗表示などを確認する想定
                        time.sleep(15)
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
