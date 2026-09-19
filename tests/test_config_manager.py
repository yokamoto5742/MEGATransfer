import configparser
from unittest.mock import patch

import pytest

from utils.config_manager import get_upload_destinations


def _config(text: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_string(text)
    return config


VALID_CONFIG = """
[URL]
Taskdiary = https://1drv.ms/f/taskdiary
Receive_file = https://1drv.ms/f/receive

[filename]
Taskdiary_pattern = _taskdiary
Receive_file_pattern = _magnate$
"""


class TestGetUploadDestinations:
    """アップロード先設定の読み込みテスト"""

    def test_reads_pattern_and_url_pairs(self):
        with patch('utils.config_manager.load_config', return_value=_config(VALID_CONFIG)):
            destinations = get_upload_destinations()

        assert [(d.name, d.pattern.pattern, d.url) for d in destinations] == [
            ('Taskdiary', '_taskdiary$', 'https://1drv.ms/f/taskdiary'),
            ('Receive_file', '_magnate$', 'https://1drv.ms/f/receive'),
        ]

    def test_missing_pattern_raises(self):
        config = _config(VALID_CONFIG.replace("Receive_file_pattern = _magnate$", ""))
        with patch('utils.config_manager.load_config', return_value=config):
            with pytest.raises(ValueError):
                get_upload_destinations()

    def test_missing_url_raises(self):
        config = _config(VALID_CONFIG.replace("Taskdiary = https://1drv.ms/f/taskdiary", ""))
        with patch('utils.config_manager.load_config', return_value=config):
            with pytest.raises(configparser.NoOptionError):
                get_upload_destinations()

    def test_reads_actual_config_ini(self):
        """同梱のconfig.iniから2件のアップロード先が読み込める"""
        assert [d.name for d in get_upload_destinations()] == ['Taskdiary', 'Receive_file']
