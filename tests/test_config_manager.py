import configparser
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.config_manager import UploadDestination, get_upload_destinations


def _config(text: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_string(text)
    return config


VALID_CONFIG = """
[filename]
Taskdiary_pattern = _taskdiary
Receive_file_pattern = _magnate$
"""


@pytest.fixture
def upload_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('Taskdiary', 'https://1drv.ms/f/taskdiary')
    monkeypatch.setenv('Receive_file', 'https://1drv.ms/f/receive')


@pytest.mark.usefixtures('upload_urls')
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

    def test_missing_url_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv('Taskdiary')
        with patch('utils.config_manager.load_config', return_value=_config(VALID_CONFIG)):
            with pytest.raises(ValueError, match='Taskdiary'):
                get_upload_destinations()

    def test_empty_url_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv('Receive_file', '')
        with patch('utils.config_manager.load_config', return_value=_config(VALID_CONFIG)):
            with pytest.raises(ValueError, match='Receive_file'):
                get_upload_destinations()

    def test_strip_pattern_defaults_to_false(self):
        with patch('utils.config_manager.load_config', return_value=_config(VALID_CONFIG)):
            destinations = get_upload_destinations()

        assert [d.strip_pattern for d in destinations] == [False, False]

    def test_reads_strip_pattern(self):
        config = _config(VALID_CONFIG + "Receive_file_strip_pattern = True\n")
        with patch('utils.config_manager.load_config', return_value=config):
            destinations = get_upload_destinations()

        assert [d.strip_pattern for d in destinations] == [False, True]

    def test_reads_actual_config_ini(self):
        """同梱のconfig.iniから2件のアップロード先が読み込める"""
        destinations = get_upload_destinations()

        assert [(d.name, d.strip_pattern) for d in destinations] == [
            ('Taskdiary', False),
            ('Receive_file', True),
        ]


class TestUploadName:
    """アップロード時のファイル名変換のテスト"""

    @pytest.mark.parametrize(('strip_pattern', 'filename', 'expected'), [
        (True, 'test_magnate.md', 'test.md'),
        (True, 'a_magnate_magnate.md', 'a_magnate.md'),
        (True, '_magnate.md', '_magnate.md'),
        (False, 'test_magnate.md', 'test_magnate.md'),
    ])
    def test_upload_name(self, strip_pattern: bool, filename: str, expected: str):
        destination = UploadDestination('Receive_file', re.compile('_magnate$'), 'https://1drv.ms/f/r', strip_pattern)

        assert destination.upload_name(Path(filename)) == expected
