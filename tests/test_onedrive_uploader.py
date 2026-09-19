from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from service.onedrive_uploader import OneDriveUploader


def _response(ok: bool, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.ok = ok
    response.status = status
    return response


def _response_context(response: MagicMock) -> MagicMock:
    """page.expect_response() の戻り値（with文で .value を返す）を模倣"""
    context = MagicMock()
    context.__enter__.return_value.value = response
    return context


@pytest.fixture
def mock_config():
    """設定のモックを提供"""
    with patch('service.onedrive_uploader.get_replace_button_text', return_value='置き換える'), \
         patch('service.onedrive_uploader.get_max_wait_time', return_value=10.0), \
         patch('service.onedrive_uploader.get_headless', return_value=True), \
         patch('service.onedrive_uploader.get_post_upload_wait', return_value=0.0):
        yield


@pytest.fixture
def uploader(mock_config):
    return OneDriveUploader('https://1drv.ms/f/test')


@pytest.fixture
def mock_playwright():
    """Playwrightのモックを提供"""
    with patch('service.onedrive_uploader.sync_playwright') as mock_pw:
        instance = MagicMock()
        browser = MagicMock()
        page = MagicMock()
        instance.chromium.launch.return_value = browser
        browser.new_page.return_value = page
        mock_pw.return_value.__enter__.return_value = instance
        yield {'instance': instance, 'browser': browser, 'page': page}


class TestOpenFolderPage:
    """共有フォルダのページを開く処理のテスト"""

    def test_opens_url_with_edge(self, uploader, mock_playwright):
        with uploader._open_folder_page():
            mock_playwright['instance'].chromium.launch.assert_called_once_with(channel="msedge", headless=True)
            mock_playwright['browser'].new_page.assert_called_once_with(locale="ja-JP")
            mock_playwright['page'].goto.assert_called_once_with('https://1drv.ms/f/test')

    def test_closes_browser_on_error(self, uploader, mock_playwright):
        with pytest.raises(RuntimeError):
            with uploader._open_folder_page():
                raise RuntimeError("error")

        mock_playwright['browser'].close.assert_called_once()


class TestIsUploadResponse:
    """送信API応答の判定テスト"""

    def test_matches_upload_api_post(self):
        response = MagicMock()
        response.request.method = "POST"
        response.url = "https://onedrive.live.com/_api/web/GetFolderByServerRelativePath(x)/Files/AddUsingPath(DecodedUrl=@a2)"
        assert OneDriveUploader._is_upload_response(response) is True

    def test_ignores_other_api(self):
        response = MagicMock()
        response.request.method = "POST"
        response.url = "https://onedrive.live.com/_api/web/GetListUsingPath(x)/RenderListDataAsStream"
        assert OneDriveUploader._is_upload_response(response) is False

    def test_ignores_get_request(self):
        response = MagicMock()
        response.request.method = "GET"
        response.url = "https://onedrive.live.com/_api/web/Files/AddUsingPath(x)"
        assert OneDriveUploader._is_upload_response(response) is False


class TestUploadSingleFile:
    """1ファイルのアップロード処理のテスト"""

    def test_success(self, uploader):
        page = MagicMock()
        page.expect_response.return_value = _response_context(_response(ok=True))

        assert uploader._upload_single_file(page, Path("a_taskdiary.md")) is True
        page.expect_file_chooser.return_value.__enter__.return_value.value.set_files.assert_called_once_with(
            "a_taskdiary.md"
        )
        page.get_by_role.assert_not_called()

    def test_replaces_existing_file(self, uploader):
        """同名ファイルで拒否された場合は「置き換える」を押して再送信する"""
        page = MagicMock()
        page.expect_response.side_effect = [
            _response_context(_response(ok=False, status=400)),
            _response_context(_response(ok=True)),
        ]

        assert uploader._upload_single_file(page, Path("a_taskdiary.md")) is True
        page.get_by_role.assert_called_once_with("button", name="置き換える")
        page.get_by_role.return_value.click.assert_called_once()

    def test_fails_when_replace_rejected(self, uploader):
        page = MagicMock()
        page.expect_response.side_effect = [
            _response_context(_response(ok=False, status=400)),
            _response_context(_response(ok=False, status=500)),
        ]

        assert uploader._upload_single_file(page, Path("a_taskdiary.md")) is False

    def test_fails_when_replace_button_missing(self, uploader):
        page = MagicMock()
        page.expect_response.return_value = _response_context(_response(ok=False, status=400))
        page.get_by_role.return_value.click.side_effect = TimeoutError("not found")

        assert uploader._upload_single_file(page, Path("a_taskdiary.md")) is False

    def test_fails_on_response_timeout(self, uploader):
        page = MagicMock()
        page.expect_response.return_value.__enter__.side_effect = TimeoutError("timeout")

        assert uploader._upload_single_file(page, Path("a_taskdiary.md")) is False


class TestUploadFiles:
    """複数ファイルのアップロード処理のテスト"""

    def test_empty_list(self, uploader, mock_playwright):
        assert uploader.upload_files([]) == []
        mock_playwright['instance'].chromium.launch.assert_not_called()

    def test_returns_only_successful_files(self, uploader, mock_playwright):
        files = [Path("a_taskdiary.md"), Path("b_taskdiary.md")]
        with patch.object(uploader, '_upload_single_file', side_effect=[True, False]):
            assert uploader.upload_files(files) == [files[0]]

    def test_uses_single_browser_for_all_files(self, uploader, mock_playwright):
        files = [Path("a_taskdiary.md"), Path("b_taskdiary.md")]
        with patch.object(uploader, '_upload_single_file', return_value=True):
            uploader.upload_files(files)
        mock_playwright['instance'].chromium.launch.assert_called_once()

    def test_browser_launch_failure(self, uploader, mock_playwright):
        mock_playwright['instance'].chromium.launch.side_effect = Exception("Edge not found")
        assert uploader.upload_files([Path("a_taskdiary.md")]) == []
