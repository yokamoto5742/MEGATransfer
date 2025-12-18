import configparser
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv


def get_config_path():
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合
        base_path = sys._MEIPASS
    else:
        # 通常のPythonスクリプトとして実行される場合
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, 'config.ini')


CONFIG_PATH = get_config_path()


def load_environment_variables():
    current_dir = Path(__file__).parent.parent
    env_path = current_dir / '.env'

    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False


load_environment_variables()


def load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            config.read_file(f)
    except FileNotFoundError:
        print(f"設定ファイルが見つかりません: {CONFIG_PATH}")
        raise
    except configparser.Error as e:
        print(f"設定ファイルの解析中にエラーが発生しました: {e}")
        raise
    return config


def save_config(config: configparser.ConfigParser):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except IOError as e:
        print(f"設定ファイルの保存中にエラーが発生しました: {e}")
        raise


def get_src_dir() -> str:
    """監視対象のディレクトリパスを取得"""
    config = load_config()
    return config.get('Paths', 'src_dir')


def get_mega_url() -> str:
    """MEGAファイルリクエストのURLを取得"""
    config = load_config()
    return config.get('URL', 'MEGAfilerequest')


def get_rename_pattern() -> re.Pattern:
    """ファイル名変換用の正規表現パターンを取得

    パターンはファイル名（stem）の末尾にマッチする
    $がない場合は自動的に末尾マッチとして扱う
    """
    config = load_config()
    # config.iniの [filename] セクションを優先的に読み込む
    pattern_str = config.get('filename', 'pattern', fallback=None)

    if not pattern_str:
        # 後方互換性のため Rename セクションも確認
        pattern_str = config.get('Rename', 'pattern', fallback=r'_[A-Za-z0-9]{6}$')

    # パターンが$で終わっていない場合は末尾マッチとして$を追加
    if not pattern_str.endswith('$'):
        pattern_str = pattern_str + '$'

    try:
        return re.compile(pattern_str)
    except re.error as e:
        print(f"正規表現パターンが無効です: {pattern_str}")
        print(f"エラー: {e}")
        raise


def get_wait_time() -> float:
    """ファイル書き込み完了を待つ時間を取得（秒）"""
    config = load_config()
    return config.getfloat('App', 'wait_time', fallback=0.5)
