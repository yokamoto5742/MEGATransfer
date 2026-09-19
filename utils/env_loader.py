import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def get_env_path() -> str:
    if getattr(sys, 'frozen', False):
        # PyInstallerでビルドされた実行ファイルの場合は同梱した.envを読む
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = Path(__file__).parent.parent

    return os.path.join(base_dir, '.env')


def load_environment_variables() -> None:
    env_path = get_env_path()

    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(".envファイルを読み込みました")
    else:
        logger.warning(f".envファイルが見つかりません: {env_path}")
