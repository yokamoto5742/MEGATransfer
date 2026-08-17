import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

# ユーザーセッション単位の排他。別ユーザーが同時ログオンしている場合は各自1つ起動できる
MUTEX_NAME = r"Local\MEGATransfer_SingleInstance"
ERROR_ALREADY_EXISTS = 183

_mutex_handle: int | None = None  # プロセス終了までハンドルを保持する


def acquire_single_instance_lock() -> bool:
    """多重起動でなければTrue、既に起動中ならFalseを返す"""
    global _mutex_handle

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE

    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = ctypes.get_last_error()

    if not handle:
        # ロックを取得できない場合でもアプリの起動自体は妨げない
        logger.error(f"多重起動チェック用ミューテックスの作成に失敗しました (error={last_error})")
        return True

    if last_error == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    # 解放はプロセス終了時にOSが行うため、明示的なCloseHandleは不要
    _mutex_handle = handle
    return True
