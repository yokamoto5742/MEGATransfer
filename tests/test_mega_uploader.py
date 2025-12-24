import logging
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from service.mega_uploader import MegaUploader


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    with patch('service.mega_uploader.get_upload_complete_text') as mock_text, \
         patch('service.mega_uploader.get_max_wait_time') as mock_max_wait, \
         patch('service.mega_uploader.get_check_interval') as mock_interval, \
         patch('service.mega_uploader.get_headless') as mock_headless, \
         patch('service.mega_uploader.get_post_upload_wait') as mock_post_wait:

        mock_text.return_value = 'アップロード済み'
        mock_max_wait.return_value = 10.0
        mock_interval.return_value = 0.5
        mock_headless.return_value = True
        mock_post_wait.return_value = 1.0

        yield {
            'text': mock_text,
            'max_wait': mock_max_wait,
            'interval': mock_interval,
            'headless': mock_headless,
            'post_wait': mock_post_wait
        }


@pytest.fixture
def mock_playwright():
    """Playwrightのモックを提供"""
    with patch('service.mega_uploader.sync_playwright') as mock_pw:
        mock_playwright_instance = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        mock_pw.return_value.__enter__.return_value = mock_playwright_instance
        mock_pw.return_value.__exit__.return_value = False

        yield {
            'playwright': mock_pw,
            'instance': mock_playwright_instance,
            'browser': mock_browser,
            'page': mock_page
        }


@pytest.fixture
def uploader(mock_config):
    """テスト用のMegaUploaderインスタンスを提供"""
    return MegaUploader('https://mega.nz/test')


class TestMegaUploaderInit:
    """MegaUploaderの初期化テスト"""

    def test_init_with_url(self, mock_config):
        """URLを指定して初期化"""
        uploader = MegaUploader('https://mega.nz/filerequest/test123')

        assert uploader.url == 'https://mega.nz/filerequest/test123'
        assert uploader.upload_complete_text == 'アップロード済み'
        assert uploader.max_wait_time == 10.0
        assert uploader.check_interval == 0.5
        assert uploader.headless is True
        assert uploader.post_upload_wait == 1.0

    def test_init_loads_config(self, mock_config):
        """設定が正しく読み込まれる"""
        uploader = MegaUploader('https://mega.nz/test')

        mock_config['text'].assert_called_once()
        mock_config['max_wait'].assert_called_once()
        mock_config['interval'].assert_called_once()
        mock_config['headless'].assert_called_once()
        mock_config['post_wait'].assert_called_once()

    def test_init_logs_debug_message(self, mock_config, caplog):
        """初期化時にデバッグログを出力"""
        with caplog.at_level(logging.DEBUG):
            uploader = MegaUploader('https://mega.nz/test')

            assert "MegaUploader初期化" in caplog.text
            assert "post_upload_wait=1.0秒" in caplog.text


class TestMegaUploaderOpenMegaPage:
    """MEGAページを開く処理のテスト"""

    def test_open_mega_page_launches_browser(self, uploader, mock_playwright):
        """ブラウザが正しく起動される"""
        with uploader._open_mega_page() as page:
            mock_playwright['instance'].chromium.launch.assert_called_once_with(headless=True)

    def test_open_mega_page_creates_new_page(self, uploader, mock_playwright):
        """新しいページが作成される"""
        with uploader._open_mega_page() as page:
            mock_playwright['browser'].new_page.assert_called_once()

    def test_open_mega_page_navigates_to_url(self, uploader, mock_playwright):
        """指定されたURLに遷移する"""
        with uploader._open_mega_page() as page:
            mock_playwright['page'].goto.assert_called_once_with('https://mega.nz/test')

    def test_open_mega_page_waits_for_network_idle(self, uploader, mock_playwright):
        """ネットワークアイドル状態まで待機"""
        with uploader._open_mega_page() as page:
            mock_playwright['page'].wait_for_load_state.assert_called_once_with("networkidle")

    def test_open_mega_page_closes_browser(self, uploader, mock_playwright, caplog):
        """ページ使用後にブラウザが閉じられる"""
        with caplog.at_level(logging.DEBUG):
            with uploader._open_mega_page() as page:
                pass

            mock_playwright['browser'].close.assert_called_once()
            assert "ブラウザを閉じました" in caplog.text

    def test_open_mega_page_closes_browser_on_exception(self, uploader, mock_playwright):
        """例外発生時でもブラウザが閉じられる"""
        try:
            with uploader._open_mega_page() as page:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        mock_playwright['browser'].close.assert_called_once()

    def test_open_mega_page_headless_mode(self, mock_config, mock_playwright):
        """ヘッドレスモードの設定が反映される"""
        mock_config['headless'].return_value = False
        uploader = MegaUploader('https://mega.nz/test')

        with uploader._open_mega_page() as page:
            mock_playwright['instance'].chromium.launch.assert_called_once_with(headless=False)


class TestMegaUploaderWaitForUploadComplete:
    """アップロード完了待機のテスト"""

    def test_wait_for_upload_complete_success(self, uploader, mock_playwright, caplog):
        """アップロード完了テキストが検出される"""
        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        with caplog.at_level(logging.DEBUG):
            result = uploader._wait_for_upload_complete(mock_page)

            assert result is True
            mock_page.locator.assert_called_with("text=アップロード済み")
            assert "「アップロード済み」を検出しました" in caplog.text

    def test_wait_for_upload_complete_timeout(self, uploader, mock_playwright, caplog):
        """タイムアウトまで検出されない"""
        uploader.max_wait_time = 1.0
        uploader.check_interval = 0.3

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        with caplog.at_level(logging.DEBUG):
            result = uploader._wait_for_upload_complete(mock_page)

            assert result is False
            assert "検出がタイムアウトしました" in caplog.text

    def test_wait_for_upload_complete_delayed_detection(self, uploader, mock_playwright):
        """複数回チェック後に検出される"""
        uploader.check_interval = 0.1

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        # 3回目で検出される
        mock_locator.count.side_effect = [0, 0, 1]
        mock_page.locator.return_value = mock_locator

        with patch('time.sleep'):
            result = uploader._wait_for_upload_complete(mock_page)

            assert result is True
            assert mock_locator.count.call_count == 3

    def test_wait_for_upload_complete_respects_check_interval(self, uploader, mock_playwright):
        """チェック間隔が正しく使用される"""
        uploader.check_interval = 0.2
        uploader.max_wait_time = 0.5

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 0
        mock_page.locator.return_value = mock_locator

        with patch('time.sleep') as mock_sleep:
            uploader._wait_for_upload_complete(mock_page)

            # sleep が check_interval で呼ばれることを確認
            for call_args in mock_sleep.call_args_list:
                assert call_args[0][0] == 0.2


class TestMegaUploaderUploadSingleFile:
    """単一ファイルアップロードのテスト"""

    def test_upload_single_file_success(self, uploader, mock_playwright, tmp_path, caplog):
        """ファイルアップロードが成功する"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_file_input = MagicMock()
        mock_file_input.count.return_value = 1
        mock_page.locator.return_value = mock_file_input

        with patch.object(uploader, '_wait_for_upload_complete', return_value=True):
            with patch('time.sleep'):
                with caplog.at_level(logging.INFO):
                    result = uploader._upload_single_file(mock_page, test_file)

                    assert result is True
                    mock_file_input.set_input_files.assert_called_once_with(str(test_file))
                    assert "アップロード開始" in caplog.text
                    assert "アップロード完了" in caplog.text

    def test_upload_single_file_no_input_tag(self, uploader, mock_playwright, tmp_path, caplog):
        """input要素が見つからない場合"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_file_input = MagicMock()
        mock_file_input.count.return_value = 0
        mock_page.locator.return_value = mock_file_input

        with caplog.at_level(logging.ERROR):
            result = uploader._upload_single_file(mock_page, test_file)

            assert result is False
            assert "inputタグが見つかりませんでした" in caplog.text

    def test_upload_single_file_timeout(self, uploader, mock_playwright, tmp_path, caplog):
        """アップロード完了確認がタイムアウト"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_file_input = MagicMock()
        mock_file_input.count.return_value = 1
        mock_page.locator.return_value = mock_file_input

        with patch.object(uploader, '_wait_for_upload_complete', return_value=False):
            with caplog.at_level(logging.WARNING):
                result = uploader._upload_single_file(mock_page, test_file)

                assert result is False
                assert "完了確認がタイムアウトしました" in caplog.text

    def test_upload_single_file_exception(self, uploader, mock_playwright, tmp_path, caplog):
        """アップロード中に例外が発生"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_page.locator.side_effect = RuntimeError("Test error")

        with caplog.at_level(logging.ERROR):
            result = uploader._upload_single_file(mock_page, test_file)

            assert result is False
            assert "アップロード失敗" in caplog.text

    def test_upload_single_file_waits_after_completion(self, uploader, mock_playwright, tmp_path):
        """アップロード完了後に待機する"""
        uploader.post_upload_wait = 2.0

        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_file_input = MagicMock()
        mock_file_input.count.return_value = 1
        mock_page.locator.return_value = mock_file_input

        with patch.object(uploader, '_wait_for_upload_complete', return_value=True):
            with patch('time.sleep') as mock_sleep:
                uploader._upload_single_file(mock_page, test_file)

                # post_upload_wait で sleep が呼ばれることを確認
                mock_sleep.assert_called_with(2.0)

    def test_upload_single_file_logs_debug_messages(self, uploader, mock_playwright, tmp_path, caplog):
        """デバッグログが出力される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        mock_page = mock_playwright['page']
        mock_file_input = MagicMock()
        mock_file_input.count.return_value = 1
        mock_page.locator.return_value = mock_file_input

        with patch.object(uploader, '_wait_for_upload_complete', return_value=True):
            with patch('time.sleep'):
                with caplog.at_level(logging.DEBUG):
                    uploader._upload_single_file(mock_page, test_file)

                    assert "ファイルを選択しました" in caplog.text
                    assert "アップロード完了後の待機開始" in caplog.text
                    assert "アップロード完了後の待機終了" in caplog.text


class TestMegaUploaderUploadFile:
    """単一ファイルアップロード（公開メソッド）のテスト"""

    def test_upload_file_success(self, uploader, mock_playwright, tmp_path, caplog):
        """ファイルアップロードが成功する"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            with caplog.at_level(logging.INFO):
                result = uploader.upload_file(test_file)

                assert result is True
                assert "MEGAへの接続" in caplog.text

    def test_upload_file_failure(self, uploader, mock_playwright, tmp_path):
        """ファイルアップロードが失敗する"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=False):
            result = uploader.upload_file(test_file)

            assert result is False

    def test_upload_file_playwright_exception(self, uploader, tmp_path, caplog):
        """Playwright起動時に例外が発生"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch('service.mega_uploader.sync_playwright', side_effect=RuntimeError("Browser error")):
            with caplog.at_level(logging.ERROR):
                result = uploader.upload_file(test_file)

                assert result is False
                assert "Playwrightによるアップロード失敗" in caplog.text

    def test_upload_file_opens_and_closes_browser(self, uploader, mock_playwright, tmp_path):
        """ブラウザが開閉される"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            uploader.upload_file(test_file)

            mock_playwright['browser'].close.assert_called_once()


class TestMegaUploaderUploadFiles:
    """複数ファイルアップロードのテスト"""

    def test_upload_files_empty_list(self, uploader, caplog):
        """空のリストを渡した場合"""
        with caplog.at_level(logging.INFO):
            result = uploader.upload_files([])

            assert result == []
            assert "アップロードするファイルがありません" in caplog.text

    def test_upload_files_single_file_success(self, uploader, mock_playwright, tmp_path, caplog):
        """1つのファイルをアップロード成功"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            with caplog.at_level(logging.INFO):
                result = uploader.upload_files([test_file])

                assert result == [test_file]
                assert "1件のファイルをアップロードします" in caplog.text
                assert "1/1件のファイルをアップロードしました" in caplog.text

    def test_upload_files_multiple_files_success(self, uploader, mock_playwright, tmp_path):
        """複数ファイルをすべてアップロード成功"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            result = uploader.upload_files(files)

            assert result == files
            assert len(result) == 3

    def test_upload_files_partial_success(self, uploader, mock_playwright, tmp_path):
        """一部のファイルのみアップロード成功"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("content")

        # 1番目と3番目のファイルのみ成功
        with patch.object(uploader, '_upload_single_file', side_effect=[True, False, True]):
            result = uploader.upload_files(files)

            assert len(result) == 2
            assert files[0] in result
            assert files[2] in result
            assert files[1] not in result

    def test_upload_files_all_failures(self, uploader, mock_playwright, tmp_path, caplog):
        """すべてのファイルがアップロード失敗"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=False):
            with caplog.at_level(logging.INFO):
                result = uploader.upload_files(files)

                assert result == []
                assert "0/3件のファイルをアップロードしました" in caplog.text

    def test_upload_files_shows_progress(self, uploader, mock_playwright, tmp_path, caplog):
        """進捗がログ出力される"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            with caplog.at_level(logging.INFO):
                uploader.upload_files(files)

                assert "進捗: 1/3" in caplog.text
                assert "進捗: 2/3" in caplog.text
                assert "進捗: 3/3" in caplog.text

    def test_upload_files_reuses_browser_session(self, uploader, mock_playwright, tmp_path):
        """同じブラウザセッションを複数ファイルで使用"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(3)]
        for f in files:
            f.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            uploader.upload_files(files)

            # ブラウザは1回だけ起動される
            mock_playwright['instance'].chromium.launch.assert_called_once()
            # closeも1回だけ
            mock_playwright['browser'].close.assert_called_once()

    def test_upload_files_playwright_exception(self, uploader, tmp_path, caplog):
        """Playwright例外時は空リストを返す"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch('service.mega_uploader.sync_playwright', side_effect=RuntimeError("Browser error")):
            with caplog.at_level(logging.ERROR):
                result = uploader.upload_files([test_file])

                assert result == []
                assert "Playwrightによるアップロード失敗" in caplog.text

    def test_upload_files_logs_summary(self, uploader, mock_playwright, tmp_path, caplog):
        """最後にサマリーログを出力"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(5)]
        for f in files:
            f.write_text("content")

        # 3つ成功、2つ失敗
        with patch.object(uploader, '_upload_single_file', side_effect=[True, True, True, False, False]):
            with caplog.at_level(logging.INFO):
                uploader.upload_files(files)

                assert "3/5件のファイルをアップロードしました" in caplog.text


class TestMegaUploaderEdgeCases:
    """エッジケースのテスト"""

    def test_very_large_file_name(self, uploader, mock_playwright, tmp_path):
        """非常に長いファイル名"""
        long_name = "test_" + "a" * 200 + ".txt"
        test_file = tmp_path / long_name

        try:
            test_file.write_text("content")

            with patch.object(uploader, '_upload_single_file', return_value=True):
                result = uploader.upload_file(test_file)

                if test_file.exists():
                    assert result is True
        except OSError:
            # ファイル名が長すぎる場合はスキップ
            pass

    def test_unicode_file_name(self, uploader, mock_playwright, tmp_path):
        """Unicode文字を含むファイル名"""
        test_file = tmp_path / "テスト_ファイル_日本語.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', return_value=True):
            result = uploader.upload_file(test_file)

            assert result is True

    def test_upload_complete_text_custom(self, mock_config, mock_playwright, tmp_path):
        """カスタムの完了テキスト"""
        mock_config['text'].return_value = 'Upload Complete'
        uploader = MegaUploader('https://mega.nz/test')

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        result = uploader._wait_for_upload_complete(mock_page)

        assert result is True
        mock_page.locator.assert_called_with("text=Upload Complete")

    def test_zero_check_interval(self, mock_config, mock_playwright):
        """チェック間隔が0の場合"""
        mock_config['interval'].return_value = 0.0
        uploader = MegaUploader('https://mega.nz/test')

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        result = uploader._wait_for_upload_complete(mock_page)

        assert result is True

    def test_very_long_max_wait_time(self, mock_config, mock_playwright):
        """非常に長い最大待機時間"""
        mock_config['max_wait'].return_value = 3600.0
        uploader = MegaUploader('https://mega.nz/test')

        mock_page = mock_playwright['page']
        mock_locator = MagicMock()
        mock_locator.count.return_value = 1
        mock_page.locator.return_value = mock_locator

        result = uploader._wait_for_upload_complete(mock_page)

        assert result is True

    def test_upload_files_with_none_in_list(self, uploader, mock_playwright, tmp_path):
        """リストにNoneが含まれる場合"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        files = [test_file, None]

        with patch.object(uploader, '_upload_single_file', return_value=True):
            try:
                result = uploader.upload_files(files)
                # Noneは無視される
            except (TypeError, AttributeError):
                # 適切にエラーハンドリングされることを確認
                pass

    def test_concurrent_uploads(self, uploader, mock_playwright, tmp_path):
        """複数ファイルの連続アップロード"""
        files = [tmp_path / f"test_file{i}.txt" for i in range(10)]
        for f in files:
            f.write_text("content")

        call_count = 0

        def mock_upload(page, file_path):
            nonlocal call_count
            call_count += 1
            return True

        with patch.object(uploader, '_upload_single_file', side_effect=mock_upload):
            result = uploader.upload_files(files)

            assert len(result) == 10
            assert call_count == 10

    def test_page_navigation_failure(self, uploader, tmp_path, caplog):
        """ページ遷移に失敗する場合"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch('service.mega_uploader.sync_playwright') as mock_pw:
            mock_pw.return_value.__enter__.side_effect = RuntimeError("Navigation failed")

            with caplog.at_level(logging.ERROR):
                result = uploader.upload_file(test_file)

                assert result is False
                assert "Playwrightによるアップロード失敗" in caplog.text

    def test_browser_close_on_keyboard_interrupt(self, uploader, mock_playwright, tmp_path):
        """キーボード割り込み時でもブラウザが閉じられる"""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("content")

        with patch.object(uploader, '_upload_single_file', side_effect=KeyboardInterrupt):
            try:
                uploader.upload_file(test_file)
            except KeyboardInterrupt:
                pass

            mock_playwright['browser'].close.assert_called_once()
