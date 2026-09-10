from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from app.services.storage_service import StorageError, StorageService


def _make_s3_error(code: str, message: str = "error", bucket: str = "", obj: str = "") -> S3Error:
    response = MagicMock()
    response.status = 500
    response.data = b"{}"
    response.getheader.return_value = ""
    return S3Error(response, code, message, resource="", request_id="", host_id="", bucket_name=bucket, object_name=obj)


@pytest.fixture
def mock_minio():
    with patch("app.services.storage_service.Minio") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def storage(mock_minio: MagicMock) -> StorageService:
    return StorageService(endpoint="localhost:9000", access_key="key", secret_key="secret", bucket="test-bucket")


@pytest.mark.asyncio
async def test_ensure_bucket_exists(storage: StorageService, mock_minio: MagicMock):
    mock_minio.bucket_exists.return_value = True
    await storage.ensure_bucket()
    mock_minio.bucket_exists.assert_called_once_with("test-bucket")
    mock_minio.make_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_bucket_creates(storage: StorageService, mock_minio: MagicMock):
    mock_minio.bucket_exists.return_value = False
    await storage.ensure_bucket()
    mock_minio.bucket_exists.assert_called_once_with("test-bucket")
    mock_minio.make_bucket.assert_called_once_with("test-bucket")


@pytest.mark.asyncio
async def test_upload_file(storage: StorageService, mock_minio: MagicMock):
    mock_result = MagicMock()
    mock_result.object_name = "uploaded-file.txt"
    mock_minio.put_object.return_value = mock_result

    result = await storage.upload_file("test.txt", b"hello", "text/plain", {"key": "val"})

    assert result == "uploaded-file.txt"
    mock_minio.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_get_file_found(storage: StorageService, mock_minio: MagicMock):
    mock_response = MagicMock()
    mock_response.read.return_value = b"file-content"
    mock_minio.get_object.return_value = mock_response

    result = await storage.get_file("test.txt")

    assert result == b"file-content"
    mock_minio.get_object.assert_called_once_with("test-bucket", "test.txt")


@pytest.mark.asyncio
async def test_get_file_not_found(storage: StorageService, mock_minio: MagicMock):
    mock_minio.get_object.side_effect = _make_s3_error("NoSuchKey", bucket="test-bucket", obj="test.txt")

    result = await storage.get_file("test.txt")

    assert result is None


@pytest.mark.asyncio
async def test_delete_file(storage: StorageService, mock_minio: MagicMock):
    await storage.delete_file("test.txt")
    mock_minio.remove_object.assert_called_once_with("test-bucket", "test.txt")


@pytest.mark.asyncio
async def test_delete_file_not_found(storage: StorageService, mock_minio: MagicMock):
    mock_minio.remove_object.side_effect = _make_s3_error("NoSuchKey", bucket="test-bucket", obj="test.txt")

    await storage.delete_file("test.txt")
    mock_minio.remove_object.assert_called_once_with("test-bucket", "test.txt")


@pytest.mark.asyncio
async def test_get_presigned_url(storage: StorageService, mock_minio: MagicMock):
    mock_minio.presigned_get_object.return_value = "http://presigned-url"
    result = await storage.get_presigned_url("test.txt", expires=3600)
    assert result == "http://presigned-url"


@pytest.mark.asyncio
async def test_stat_file_found(storage: StorageService, mock_minio: MagicMock):
    from datetime import UTC, datetime

    mock_stat = MagicMock()
    mock_stat.size = 1024
    mock_stat.content_type = "text/plain"
    mock_stat.metadata = {"original_name": "doc.txt"}
    mock_stat.last_modified = datetime(2025, 1, 1, tzinfo=UTC)
    mock_minio.stat_object.return_value = mock_stat

    result = await storage.stat_file("test.txt")

    assert result is not None
    assert result["size"] == 1024
    assert result["content_type"] == "text/plain"
    assert result["metadata"] == {"original_name": "doc.txt"}
    assert result["last_modified"] == "2025-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_stat_file_not_found(storage: StorageService, mock_minio: MagicMock):
    mock_minio.stat_object.side_effect = _make_s3_error("NoSuchKey", bucket="test-bucket", obj="test.txt")

    result = await storage.stat_file("test.txt")
    assert result is None


@pytest.mark.asyncio
async def test_upload_file_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.put_object.side_effect = _make_s3_error("PutObjectFailed")

    with pytest.raises(StorageError):
        await storage.upload_file("test.txt", b"data", "text/plain")


@pytest.mark.asyncio
async def test_ensure_bucket_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.bucket_exists.side_effect = _make_s3_error("ListBucketsFailed")

    with pytest.raises(StorageError):
        await storage.ensure_bucket()


@pytest.mark.asyncio
async def test_get_file_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.get_object.side_effect = _make_s3_error("GetObjectFailed")

    with pytest.raises(StorageError):
        await storage.get_file("test.txt")


@pytest.mark.asyncio
async def test_delete_file_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.remove_object.side_effect = _make_s3_error("DeleteFailed")

    with pytest.raises(StorageError):
        await storage.delete_file("test.txt")


@pytest.mark.asyncio
async def test_get_presigned_url_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.presigned_get_object.side_effect = _make_s3_error("PresignFailed")

    with pytest.raises(StorageError):
        await storage.get_presigned_url("test.txt")


@pytest.mark.asyncio
async def test_stat_file_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.stat_object.side_effect = _make_s3_error("StatFailed")

    with pytest.raises(StorageError):
        await storage.stat_file("test.txt")


@pytest.mark.asyncio
async def test_stat_file_null_content_type(storage: StorageService, mock_minio: MagicMock):

    mock_stat = MagicMock()
    mock_stat.size = 512
    mock_stat.content_type = None
    mock_stat.metadata = {}
    mock_stat.last_modified = None
    mock_minio.stat_object.return_value = mock_stat

    result = await storage.stat_file("test.txt")

    assert result is not None
    assert result["content_type"] == "application/octet-stream"
    assert result["last_modified"] is None


@pytest.mark.asyncio
async def test_list_files(storage: StorageService, mock_minio: MagicMock):
    from datetime import UTC, datetime

    obj1 = MagicMock()
    obj1.object_name = "file1.txt"
    obj1.size = 100
    obj1.content_type = "text/plain"
    obj1.last_modified = datetime(2025, 1, 1, tzinfo=UTC)
    obj2 = MagicMock()
    obj2.object_name = "file2.txt"
    obj2.size = 200
    obj2.content_type = None
    obj2.last_modified = None
    mock_minio.list_objects.return_value = [obj1, obj2]

    result = await storage.list_files()

    assert len(result) == 2
    assert result[0]["file_name"] == "file1.txt"
    assert result[0]["content_type"] == "text/plain"
    assert result[1]["file_name"] == "file2.txt"
    assert result[1]["content_type"] == "application/octet-stream"
    assert result[1]["last_modified"] is None
    mock_minio.list_objects.assert_called_once_with("test-bucket", prefix="", recursive=True)


@pytest.mark.asyncio
async def test_list_files_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.list_objects.side_effect = _make_s3_error("ListFailed")

    with pytest.raises(StorageError):
        await storage.list_files()


@pytest.mark.asyncio
async def test_download_file_iterator(storage: StorageService, mock_minio: MagicMock):
    mock_response = MagicMock()
    read_calls = [b"chunk1", b"chunk2", b""]
    mock_response.read.side_effect = read_calls
    mock_minio.get_object.return_value = mock_response

    chunks = []
    async for chunk in storage.download_file_iterator("test.txt"):
        chunks.append(chunk)

    assert chunks == [b"chunk1", b"chunk2"]
    mock_minio.get_object.assert_called_once_with("test-bucket", "test.txt")
    mock_response.close.assert_called_once()
    mock_response.release_conn.assert_called_once()


@pytest.mark.asyncio
async def test_download_file_iterator_not_found(storage: StorageService, mock_minio: MagicMock):
    mock_minio.get_object.side_effect = _make_s3_error("NoSuchKey", bucket="test-bucket", obj="test.txt")

    chunks = []
    async for chunk in storage.download_file_iterator("test.txt"):
        chunks.append(chunk)

    assert chunks == []


@pytest.mark.asyncio
async def test_download_file_iterator_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.get_object.side_effect = _make_s3_error("StreamFailed")

    with pytest.raises(StorageError):
        async for _ in storage.download_file_iterator("test.txt"):
            pass


@pytest.mark.asyncio
async def test_move_file(storage: StorageService, mock_minio: MagicMock):
    mock_result = MagicMock()
    mock_result.object_name = "dest/file.txt"
    mock_minio.copy_object.return_value = mock_result

    result = await storage.move_file("source/file.txt", "dest/file.txt")

    assert result == "dest/file.txt"
    mock_minio.copy_object.assert_called_once()
    mock_minio.remove_object.assert_called_once_with("test-bucket", "source/file.txt")


@pytest.mark.asyncio
async def test_move_file_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.copy_object.side_effect = _make_s3_error("CopyFailed")

    with pytest.raises(StorageError):
        await storage.move_file("source/file.txt", "dest/file.txt")


@pytest.mark.asyncio
async def test_delete_files_by_prefix(storage: StorageService, mock_minio: MagicMock):
    obj1 = MagicMock()
    obj1.object_name = "temp/file1.txt"
    obj2 = MagicMock()
    obj2.object_name = "temp/file2.txt"
    mock_minio.list_objects.return_value = [obj1, obj2]
    mock_minio.remove_objects.return_value = []

    result = await storage.delete_files_by_prefix("temp/")

    assert result == 2
    mock_minio.list_objects.assert_called_once_with("test-bucket", prefix="temp/", recursive=True)
    mock_minio.remove_objects.assert_called_once_with("test-bucket", ["temp/file1.txt", "temp/file2.txt"])


@pytest.mark.asyncio
async def test_delete_files_by_prefix_no_files(storage: StorageService, mock_minio: MagicMock):
    mock_minio.list_objects.return_value = []

    result = await storage.delete_files_by_prefix("temp/")

    assert result == 0
    mock_minio.remove_objects.assert_not_called()


@pytest.mark.asyncio
async def test_delete_files_by_prefix_s3_error(storage: StorageService, mock_minio: MagicMock):
    mock_minio.list_objects.side_effect = _make_s3_error("ListFailed")

    with pytest.raises(StorageError):
        await storage.delete_files_by_prefix("temp/")
