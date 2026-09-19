import configparser
import os
import re
import sys
from dataclasses import dataclass
from typing import Any


def get_config_path():
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    else:
        # 通常のPythonスクリプトとして実行される場合
        base_path = os.path.dirname(__file__)

    return os.path.join(base_path, 'config.ini')


CONFIG_PATH = get_config_path()


def get_config_value(config: configparser.ConfigParser, section: str, key: str, default: Any) -> Any:
    try:
        value = config[section][key]
        # bool型の場合は文字列を正しくパース
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        return type(default)(value)
    except (KeyError, ValueError, TypeError):
        return default


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


def get_uploaded_dir() -> str:
    """アップロード成功後にファイルを移動する保管先ディレクトリパスを取得"""
    config = load_config()
    uploaded_dir = config.get('Paths', 'uploaded_dir', fallback='').strip()
    # 未設定の場合はファイル消失を防ぐため監視ディレクトリ配下に保管する
    return uploaded_dir or os.path.join(config.get('Paths', 'src_dir'), '_uploaded')


@dataclass(frozen=True)
class UploadDestination:
    """ファイル名パターンとアップロード先URLの組"""
    name: str
    pattern: re.Pattern
    url: str


# config.iniの [URL] のキー名。パターンは [filename] の「キー名_pattern」から読み込む
UPLOAD_DESTINATION_NAMES = ('Taskdiary', 'Receive_file')


def get_upload_destinations() -> list[UploadDestination]:
    """アップロード先ごとのファイル名パターンとURLを取得"""
    config = load_config()
    return [
        UploadDestination(
            name=name,
            pattern=_compile_suffix_pattern(config.get('filename', f'{name}_pattern', fallback='')),
            url=config.get('URL', name),
        )
        for name in UPLOAD_DESTINATION_NAMES
    ]


def _compile_suffix_pattern(pattern_str: str) -> re.Pattern:
    """ファイル名末尾にマッチする正規表現パターンを作成"""
    if not pattern_str:
        raise ValueError("パターンが設定されていません")

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


def get_batch_delay() -> float:
    """バッチ処理の待機時間を取得（秒）"""
    config = load_config()
    return config.getfloat('App', 'batch_delay', fallback=3.0)


def get_uploaded_retention_hours() -> float:
    """アップロード済みファイルを保管先に残す時間を取得（時間）"""
    config = load_config()
    return config.getfloat('App', 'uploaded_retention_hours', fallback=4.0)


def get_replace_button_text() -> str:
    """同名ファイルを上書きするボタンのテキストを取得"""
    config = load_config()
    return config.get('Uploader', 'replace_button_text', fallback='置き換える')


def get_max_wait_time() -> float:
    """完了チェックの最大待機時間を取得（秒）"""
    config = load_config()
    return config.getfloat('Uploader', 'max_wait_time', fallback=300)


def get_headless() -> bool:
    """ヘッドレスモードで実行するかどうかを取得"""
    config = load_config()
    return config.getboolean('Uploader', 'headless', fallback=True)


def get_post_upload_wait() -> float:
    """アップロード完了後の待機時間を取得（秒）"""
    config = load_config()
    return config.getfloat('Uploader', 'post_upload_wait', fallback=3.0)
