import os
import subprocess
import sys

from pathlib import Path
from scripts.version_manager import update_version


def get_playwright_browsers_path():
    default_path = Path.home() / 'AppData' / 'Local' / 'ms-playwright'
    if default_path.exists():
        return str(default_path)

    print("[ERROR] Playwrightブラウザが見つかりません")
    return None


def build_executable():
    new_version = update_version()

    playwright_browsers_path = get_playwright_browsers_path()

    command = [
        "pyinstaller",
        "--name=MEGATransfer",
        "--windowed",
        "--add-data", "utils/config.ini;.",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--collect-all", "playwright",
    ]

    if playwright_browsers_path and os.path.exists(playwright_browsers_path):
        print(f"[OK] Playwrightブラウザを含めます: {playwright_browsers_path}")

        browser_dirs = [d for d in os.listdir(playwright_browsers_path)
                       if d.startswith('chromium-') or d.startswith('chromium_headless_shell-')]

        if browser_dirs:
            for browser_dir_name in browser_dirs:
                browser_dir = os.path.join(playwright_browsers_path, browser_dir_name)
                command.extend([
                    "--add-data",
                    f"{browser_dir};playwright/driver/package/.local-browsers/{browser_dir_name}"
                ])
                print(f"[OK] {browser_dir_name} を含めました")
        else:
            print("[ERROR] Chromiumブラウザディレクトリが見つかりません")
            return None

    command.append("main.py")

    print("\nPyInstallerを実行中...")
    subprocess.run(command, check=True)

    print(f"\n[OK] 実行ファイルのビルドが完了しました。バージョン: {new_version}")

    return new_version


if __name__ == "__main__":

    try:
        subprocess.run(
            [sys.executable, "-c", "from playwright.sync_api import sync_playwright"],
            check=True,
            capture_output=True
        )
        print("[OK] Playwrightがインストールされています")
    except subprocess.CalledProcessError:
        print("[ERROR] エラー: Playwrightがインストールされていません。")
        sys.exit(1)

    result = build_executable()
    if result is None:
        sys.exit(1)
