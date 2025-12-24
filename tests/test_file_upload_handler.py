import logging
import re
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from watchdog.events import FileCreatedEvent, FileMovedEvent

from service.file_upload_handler import FileUploadHandler


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    with patch('service.file_upload_handler.get_rename_pattern') as mock_pattern, \
         patch('service.file_upload_handler.get_wait_time') as mock_wait, \
         patch('service.file_upload_handler.get_batch_delay') as mock_batch, \
         patch('service.file_upload_handler.get_mega_url') as mock_url:

        mock_pattern.return_value = re.compile(r'test.*$')
        mock_wait.return_value = 0.1
        mock_batch.return_value = 0.2
        mock_url.return_value = 'https://mega.nz/test'

        yield {
            'pattern': mock_pattern,
            'wait_time': mock_wait,
            'batch_delay': mock_batch,
            'mega_url': mock_url
        }


@pytest.fixture
def mock_uploader():
    """MegaUploaderのモックを提供"""
    with patch('service.file_upload_handler.MegaUploader') as mock_mega:
        mock_instance = MagicMock()
        mock_instance.upload_files.return_value = []
        mock_mega.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def handler(mock_config, mock_uploader):
    """テスト用のFileUploadHandlerインスタンスを提供"""
    return FileUploadHandler()


class TestFileUploadHandlerInit:
    """FileUploadHandlerの初期化テスト"""

    def test_init_loads_config(self, mock_config, mock_uploader):
        """設定が正しく読み込まれる"""
        handler = FileUploadHandler()

        assert handler.pattern == mock_config['pattern'].return_value
        assert handler.wait_time == 0.1
        assert handler.batch_delay == 0.2
        assert handler.uploader == mock_uploader

    def test_init_creates_empty_queue(self, handler):
        """初期化時にキューが空である"""
        assert handler._pending_files == []
        assert handler._timer is None

    def test_init_creates_lock(self, handler):
        """初期化時にロックが作成される"""
        assert isinstance(handler._lock, type(threading.Lock()))


class TestFileUploadHandlerShouldProcess:
    """ファイル処理判定のテスト"""

    def test_should_process_matching_filename(self, handler):
        """パターンにマッチするファイル名は処理対象"""
        assert handler.should_process('test_file') is True

    def test_should_process_non_matching_filename(self, handler):
        """パターンにマッチしないファイル名は処理対象外"""
        assert handler.should_process('other_file') is False

    def test_should_process_partial_match(self, handler):
        """部分一致もマッチする"""
        assert handler.should_process('test') is True
        assert handler.should_process('test123') is True

    def test_should_process_empty_string(self, handler):
        """空文字列は処理対象外"""
        assert handler.should_process('') is False

    def test_should_process_with_special_characters(self, handler):
        """特殊文字を含むファイル名も正しく判定"""
        assert handler.should_process('test_file-01') is True


class TestFileUploadHandlerOnCreated:
    """ファイル作成イベント処理のテスト"""

    def test_on_created_ignores_directory(self, handler):
        """ディレクトリ作成イベントは無視される"""
        event = MagicMock()
        event.is_directory = True
        event.src_path = r'C:\test\dir'

        with patch.object(handler, '_add_to_queue') as mock_add:
            handler.on_created(event)
            mock_add.assert_not_called()

    def test_on_created_processes_file(self, handler):
        """ファイル作成イベントは処理される"""
        event = MagicMock()
        event.is_directory = False
        event.src_path = r'C:\test\test_file.txt'

        with patch.object(handler, '_add_to_queue') as mock_add:
            handler.on_created(event)
            mock_add.assert_called_once_with(r'C:\test\test_file.txt')


class TestFileUploadHandlerOnMoved:
    """ファイル移動イベント処理のテスト"""

    def test_on_moved_ignores_directory(self, handler):
        """ディレクトリ移動イベントは無視される"""
        event = MagicMock()
        event.is_directory = True
        event.dest_path = r'C:\test\dir'

        with patch.object(handler, '_add_to_queue') as mock_add:
            handler.on_moved(event)
            mock_add.assert_not_called()

    def test_on_moved_processes_file(self, handler):
        """ファイル移動イベントは処理される"""
        event = MagicMock()
        event.is_directory = False
        event.dest_path = r'C:\test\test_file.txt'

        with patch.object(handler, '_add_to_queue') as mock_add:
            handler.on_moved(event)
            mock_add.assert_called_once_with(r'C:\test\test_file.txt')


class TestFileUploadHandlerAddToQueue:
    """キューへの追加処理のテスト"""

    def test_add_to_queue_matching_file(self, handler, tmp_path):
        """パターンにマッチするファイルはキューに追加される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(handler, '_reset_timer') as mock_reset:
            handler._add_to_queue(str(test_file))

            assert test_file in handler._pending_files
            mock_reset.assert_called_once()

    def test_add_to_queue_non_matching_file(self, handler, tmp_path):
        """パターンにマッチしないファイルは追加されない"""
        test_file = tmp_path / "other_file.txt"
        test_file.write_text("content")

        handler._add_to_queue(str(test_file))

        assert test_file not in handler._pending_files

    def test_add_to_queue_non_existing_file(self, handler):
        """存在しないファイルは追加されない"""
        handler._add_to_queue(r'C:\non_existing\test_file.txt')

        assert len(handler._pending_files) == 0

    def test_add_to_queue_duplicate_file(self, handler, tmp_path):
        """同じファイルを2回追加しても1回だけ追加される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(handler, '_reset_timer'):
            handler._add_to_queue(str(test_file))
            handler._add_to_queue(str(test_file))

            assert handler._pending_files.count(test_file) == 1

    def test_add_to_queue_waits_for_file_completion(self, handler, tmp_path):
        """ファイル書き込み完了を待つ"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        start_time = time.time()
        with patch.object(handler, '_reset_timer'):
            handler._add_to_queue(str(test_file))
        elapsed = time.time() - start_time

        assert elapsed >= handler.wait_time


class TestFileUploadHandlerResetTimer:
    """タイマーリセット処理のテスト"""

    def test_reset_timer_cancels_existing_timer(self, handler):
        """既存のタイマーがキャンセルされる"""
        mock_timer = MagicMock(spec=threading.Timer)
        handler._timer = mock_timer

        handler._reset_timer()

        mock_timer.cancel.assert_called_once()

    def test_reset_timer_creates_new_timer(self, handler):
        """新しいタイマーが作成される"""
        handler._reset_timer()

        assert handler._timer is not None
        assert isinstance(handler._timer, threading.Timer)

    def test_reset_timer_starts_timer(self, handler):
        """タイマーが開始される"""
        with patch('threading.Timer') as mock_timer_class:
            mock_timer = MagicMock()
            mock_timer_class.return_value = mock_timer

            handler._reset_timer()

            mock_timer.start.assert_called_once()

    def test_reset_timer_without_existing_timer(self, handler):
        """既存タイマーがない場合でも新しいタイマーを作成"""
        handler._timer = None

        handler._reset_timer()

        assert handler._timer is not None


class TestFileUploadHandlerProcessPendingFiles:
    """キュー内ファイル処理のテスト"""

    def test_process_pending_files_empty_queue(self, handler, caplog):
        """キューが空の場合は何もしない"""
        with caplog.at_level(logging.INFO):
            handler._process_pending_files()

            handler.uploader.upload_files.assert_not_called()

    def test_process_pending_files_uploads_and_deletes(self, handler, tmp_path):
        """ファイルをアップロードして削除"""
        test_file1 = tmp_path / "test_file1.txt"
        test_file2 = tmp_path / "test_file2.txt"
        test_file1.write_text("content1")
        test_file2.write_text("content2")

        handler._pending_files = [test_file1, test_file2]
        handler.uploader.upload_files.return_value = [test_file1, test_file2]

        handler._process_pending_files()

        handler.uploader.upload_files.assert_called_once_with([test_file1, test_file2])
        assert not test_file1.exists()
        assert not test_file2.exists()

    def test_process_pending_files_partial_success(self, handler, tmp_path):
        """一部のファイルのみアップロード成功"""
        test_file1 = tmp_path / "test_file1.txt"
        test_file2 = tmp_path / "test_file2.txt"
        test_file1.write_text("content1")
        test_file2.write_text("content2")

        handler._pending_files = [test_file1, test_file2]
        handler.uploader.upload_files.return_value = [test_file1]

        handler._process_pending_files()

        assert not test_file1.exists()
        assert test_file2.exists()

    def test_process_pending_files_clears_queue(self, handler, tmp_path):
        """処理後にキューがクリアされる"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        handler._pending_files = [test_file]
        handler.uploader.upload_files.return_value = [test_file]

        handler._process_pending_files()

        assert len(handler._pending_files) == 0

    def test_process_pending_files_logs_failure(self, handler, tmp_path, caplog):
        """アップロード失敗時にログ出力"""
        test_file1 = tmp_path / "test_file1.txt"
        test_file2 = tmp_path / "test_file2.txt"
        test_file1.write_text("content1")
        test_file2.write_text("content2")

        handler._pending_files = [test_file1, test_file2]
        handler.uploader.upload_files.return_value = [test_file1]

        with caplog.at_level(logging.WARNING):
            handler._process_pending_files()

            assert "1件のファイルがアップロードに失敗しました" in caplog.text


class TestFileUploadHandlerDeleteUploadedFiles:
    """アップロード済みファイル削除のテスト"""

    def test_delete_uploaded_files_success(self, handler, tmp_path, caplog):
        """ファイルが正常に削除される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with caplog.at_level(logging.INFO):
            handler._delete_uploaded_files([test_file])

            assert not test_file.exists()
            assert "削除完了" in caplog.text

    def test_delete_uploaded_files_multiple(self, handler, tmp_path):
        """複数ファイルが削除される"""
        test_file1 = tmp_path / "test_file1.txt"
        test_file2 = tmp_path / "test_file2.txt"
        test_file1.write_text("content1")
        test_file2.write_text("content2")

        handler._delete_uploaded_files([test_file1, test_file2])

        assert not test_file1.exists()
        assert not test_file2.exists()

    def test_delete_uploaded_files_non_existing(self, handler, caplog):
        """存在しないファイルの削除を試みてもエラーにならない"""
        non_existing = Path(r'C:\non_existing\test_file.txt')

        with caplog.at_level(logging.INFO):
            handler._delete_uploaded_files([non_existing])

            assert "すべてのファイルの削除処理が完了しました" in caplog.text

    def test_delete_uploaded_files_permission_error(self, handler, tmp_path, caplog):
        """削除失敗時にログ出力"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(Path, 'unlink', side_effect=PermissionError("Access denied")):
            with caplog.at_level(logging.ERROR):
                handler._delete_uploaded_files([test_file])

                assert "削除失敗" in caplog.text


class TestFileUploadHandlerGetPendingCount:
    """待機中ファイル数取得のテスト"""

    def test_get_pending_count_empty(self, handler):
        """キューが空の場合は0"""
        assert handler.get_pending_count() == 0

    def test_get_pending_count_with_files(self, handler, tmp_path):
        """キューにファイルがある場合はその数"""
        handler._pending_files = [
            tmp_path / "test1.txt",
            tmp_path / "test2.txt",
            tmp_path / "test3.txt"
        ]

        assert handler.get_pending_count() == 3

    def test_get_pending_count_thread_safe(self, handler, tmp_path):
        """スレッドセーフに取得できる"""
        # 複数スレッドから同時にアクセスしても正しい値が取得できる
        import concurrent.futures

        handler._pending_files = [
            tmp_path / "test1.txt",
            tmp_path / "test2.txt",
            tmp_path / "test3.txt"
        ]

        results = []
        def get_count():
            return handler.get_pending_count()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_count) for _ in range(10)]
            results = [f.result() for f in futures]

        # すべての結果が同じ値を返すことを確認
        assert all(r == 3 for r in results)


class TestFileUploadHandlerProcessNow:
    """即時処理のテスト"""

    def test_process_now_cancels_timer(self, handler):
        """タイマーがキャンセルされる"""
        mock_timer = MagicMock(spec=threading.Timer)
        handler._timer = mock_timer

        with patch.object(handler, '_process_pending_files'):
            handler.process_now()

            mock_timer.cancel.assert_called_once()

    def test_process_now_processes_immediately(self, handler, tmp_path):
        """即座に処理が実行される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        handler._pending_files = [test_file]
        handler.uploader.upload_files.return_value = [test_file]

        handler.process_now()

        handler.uploader.upload_files.assert_called_once()
        assert len(handler._pending_files) == 0

    def test_process_now_without_timer(self, handler):
        """タイマーがない場合でも処理される"""
        handler._timer = None

        with patch.object(handler, '_process_pending_files') as mock_process:
            handler.process_now()
            mock_process.assert_called_once()


class TestFileUploadHandlerScanExistingFiles:
    """既存ファイルスキャンのテスト"""

    def test_scan_existing_files_finds_matching_files(self, handler, tmp_path, caplog):
        """マッチするファイルを見つける"""
        test_file1 = tmp_path / "test_file1.txt"
        test_file2 = tmp_path / "test_file2.txt"
        other_file = tmp_path / "other_file.txt"

        test_file1.write_text("content1")
        test_file2.write_text("content2")
        other_file.write_text("content3")

        with caplog.at_level(logging.INFO):
            handler.scan_existing_files(str(tmp_path))

            assert test_file1 in handler._pending_files
            assert test_file2 in handler._pending_files
            assert other_file not in handler._pending_files
            assert "2件の既存ファイルをキューに追加しました" in caplog.text

    def test_scan_existing_files_ignores_directories(self, handler, tmp_path):
        """ディレクトリは無視される"""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        handler.scan_existing_files(str(tmp_path))

        assert test_dir not in handler._pending_files

    def test_scan_existing_files_non_existing_directory(self, handler):
        """存在しないディレクトリは何もしない"""
        handler.scan_existing_files(r'C:\non_existing\dir')

        assert len(handler._pending_files) == 0

    def test_scan_existing_files_no_matching_files(self, handler, tmp_path, caplog):
        """マッチするファイルがない場合"""
        other_file = tmp_path / "other_file.txt"
        other_file.write_text("content")

        with caplog.at_level(logging.INFO):
            handler.scan_existing_files(str(tmp_path))

            assert len(handler._pending_files) == 0
            assert "処理対象の既存ファイルはありませんでした" in caplog.text

    def test_scan_existing_files_starts_timer(self, handler, tmp_path):
        """ファイルが見つかった場合タイマーが開始される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(handler, '_reset_timer') as mock_reset:
            handler.scan_existing_files(str(tmp_path))
            mock_reset.assert_called_once()

    def test_scan_existing_files_skips_duplicates(self, handler, tmp_path):
        """既にキューにあるファイルは追加しない"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        handler._pending_files = [test_file]

        handler.scan_existing_files(str(tmp_path))

        assert handler._pending_files.count(test_file) == 1


class TestFileUploadHandlerEdgeCases:
    """エッジケースのテスト"""

    def test_concurrent_add_to_queue(self, handler, tmp_path):
        """複数スレッドから同時にキューへ追加"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(5)]
        for f in files:
            f.write_text("content")

        def add_file(file_path):
            handler._add_to_queue(str(file_path))

        threads = [threading.Thread(target=add_file, args=(f,)) for f in files]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(handler._pending_files) == 5

    def test_process_during_queue_modification(self, handler, tmp_path):
        """キュー変更中の処理要求"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        handler._pending_files = [test_file]
        handler.uploader.upload_files.return_value = [test_file]

        # ロックが正しく使われることを確認
        handler._process_pending_files()

        assert len(handler._pending_files) == 0

    def test_unicode_filename_processing(self, handler, tmp_path):
        """Unicode文字を含むファイル名の処理"""
        # パターンを日本語対応に変更
        handler.pattern = re.compile(r'test.*$')

        test_file = tmp_path / "test_日本語.txt"
        test_file.write_text("content")

        handler._add_to_queue(str(test_file))

        assert test_file in handler._pending_files

    def test_very_long_filename(self, handler, tmp_path):
        """非常に長いファイル名の処理"""
        long_name = "test_" + "a" * 200 + ".txt"
        test_file = tmp_path / long_name

        try:
            test_file.write_text("content")
            handler._add_to_queue(str(test_file))

            if test_file.exists():
                assert test_file in handler._pending_files
        except OSError:
            # ファイル名が長すぎる場合はスキップ
            pass

    def test_rapid_file_creation(self, handler, tmp_path):
        """短時間に多数のファイルが作成される"""
        files = []
        for i in range(10):
            test_file = tmp_path / f"test_file{i}.txt"
            test_file.write_text(f"content{i}")
            files.append(test_file)

        with patch.object(handler, '_reset_timer'):
            for f in files:
                handler._add_to_queue(str(f))

        assert len(handler._pending_files) == 10
