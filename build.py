import subprocess
import sys


def build_executable():
    command = [
        "pyinstaller",
        "--name=MEGATransfer",
        "--windowed",
        "--add-data", "utils/config.ini;.",
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--collect-all", "playwright",
        "main.py",
    ]

    print("\nPyInstallerを実行中...")
    subprocess.run(command, check=True)

    print(f"\n[OK] 実行ファイルのビルドが完了しました")
    return None


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
