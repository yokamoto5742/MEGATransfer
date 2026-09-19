import os
from pathlib import Path

import pytest

from utils.env_loader import get_env_path, load_environment_variables


class TestGetEnvPath:
    """.envファイルのパス解決テスト"""

    def test_source_run_uses_project_root(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delattr('sys.frozen', raising=False)
        project_root = Path(__file__).parent.parent
        assert get_env_path() == os.path.join(project_root, '.env')

    def test_frozen_run_uses_meipass(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr('sys.frozen', True, raising=False)
        monkeypatch.setattr('sys._MEIPASS', str(tmp_path), raising=False)
        assert get_env_path() == os.path.join(tmp_path, '.env')


class TestLoadEnvironmentVariables:
    """.envファイルの読み込みテスト"""

    def test_loads_env_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        env_path = tmp_path / '.env'
        env_path.write_text('MEGATRANSFER_TEST_KEY=value\n', encoding='utf-8')
        monkeypatch.setattr('utils.env_loader.get_env_path', lambda: str(env_path))
        monkeypatch.delenv('MEGATRANSFER_TEST_KEY', raising=False)

        load_environment_variables()

        assert os.environ['MEGATRANSFER_TEST_KEY'] == 'value'
        monkeypatch.delenv('MEGATRANSFER_TEST_KEY')

    def test_missing_env_file_does_not_raise(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        monkeypatch.setattr('utils.env_loader.get_env_path', lambda: str(tmp_path / '.env'))
        load_environment_variables()
