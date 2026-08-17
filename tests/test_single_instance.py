import logging
from unittest.mock import MagicMock, patch

import pytest

from utils import single_instance
from utils.single_instance import ERROR_ALREADY_EXISTS, MUTEX_NAME, acquire_single_instance_lock


@pytest.fixture(autouse=True)
def reset_mutex_handle():
    """テスト間でモジュール変数の状態が残らないようにする"""
    single_instance._mutex_handle = None
    yield
    single_instance._mutex_handle = None


@pytest.fixture
def mock_kernel32():
    """kernel32とget_last_errorのモックを提供"""
    with patch('utils.single_instance.ctypes') as mock_ctypes:
        kernel32 = MagicMock()
        mock_ctypes.WinDLL.return_value = kernel32
        yield mock_ctypes, kernel32


class TestAcquireSingleInstanceLock:
    """多重起動チェックのテスト"""

    def test_first_instance_acquires_lock(self, mock_kernel32):
        """新規作成に成功した場合はTrueを返しハンドルを保持"""
        mock_ctypes, kernel32 = mock_kernel32
        kernel32.CreateMutexW.return_value = 1234
        mock_ctypes.get_last_error.return_value = 0

        assert acquire_single_instance_lock() is True
        assert single_instance._mutex_handle == 1234
        kernel32.CloseHandle.assert_not_called()

    def test_second_instance_is_rejected(self, mock_kernel32):
        """既にミューテックスが存在する場合はFalseを返しハンドルを閉じる"""
        mock_ctypes, kernel32 = mock_kernel32
        kernel32.CreateMutexW.return_value = 1234
        mock_ctypes.get_last_error.return_value = ERROR_ALREADY_EXISTS

        assert acquire_single_instance_lock() is False
        kernel32.CloseHandle.assert_called_once_with(1234)
        assert single_instance._mutex_handle is None

    def test_creation_failure_allows_startup(self, mock_kernel32, caplog):
        """ミューテックスを作成できない場合でも起動を妨げない"""
        mock_ctypes, kernel32 = mock_kernel32
        kernel32.CreateMutexW.return_value = 0
        mock_ctypes.get_last_error.return_value = 5

        with caplog.at_level(logging.ERROR):
            assert acquire_single_instance_lock() is True

        assert "ミューテックスの作成に失敗しました" in caplog.text
        assert single_instance._mutex_handle is None

    def test_mutex_name_is_session_local(self, mock_kernel32):
        """セッション単位のミューテックス名で作成される"""
        mock_ctypes, kernel32 = mock_kernel32
        kernel32.CreateMutexW.return_value = 1234
        mock_ctypes.get_last_error.return_value = 0

        acquire_single_instance_lock()

        assert kernel32.CreateMutexW.call_args[0][2] == MUTEX_NAME
        assert MUTEX_NAME.startswith('Local\\')
