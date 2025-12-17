import sys

from app.tray_app import TrayApp


def main():

    try:
        app = TrayApp()
        app.run()
    except FileNotFoundError as e:
        print(f"[エラー] 設定ファイルエラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[エラー] 予期せぬエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
