"""Bound downloads before disk exhaustion and metadata parsing."""
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from model_download import download


class Response(io.BytesIO):
    status = 200

    def __init__(self, body, headers):
        super().__init__(body)
        self.headers = headers


class DownloadLimitTests(unittest.TestCase):
    def test_oversized_header_is_rejected_before_reading_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'config.json'
            target.write_bytes(b'previous valid config')
            response = Response(b'new', {'Content-Length': str(1024 * 1024 + 1)})
            with patch.object(response, 'read', wraps=response.read) as read:
                with self.assertRaises(ValueError):
                    download('https://example.test/config', target, opener=Mock(return_value=response))
                read.assert_not_called()
            self.assertEqual(target.read_bytes(), b'previous valid config')

    def test_unknown_length_stream_is_bounded_and_removed_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'config.yaml'
            target.write_bytes(b'previous config')
            response = Response(b'x' * (1024 * 1024 + 1), {})
            validate = Mock()
            with self.assertRaises(ValueError):
                download('https://example.test/config', target, opener=Mock(return_value=response), validate=validate)
            validate.assert_not_called()
            self.assertEqual(target.read_bytes(), b'previous config')
            self.assertEqual(list((Path(folder) / '.downloads').glob('*.part')), [])

    def test_unknown_length_reserves_free_disk_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'model.pth'
            target.write_bytes(b'previous model')
            response = Response(b'payload', {})
            with patch('model_download.shutil.disk_usage', return_value=SimpleNamespace(free=0)):
                with self.assertRaises(OSError):
                    download('https://example.test/model', target, opener=Mock(return_value=response))
            self.assertEqual(target.read_bytes(), b'previous model')

    def test_oversized_local_metadata_is_rejected_before_json_parser(self):
        from model_manager import validate_file
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'config.json'
            source.write_bytes(b' ' * (1024 * 1024 + 1))
            with patch('model_manager.json.load') as parse:
                with self.assertRaises(ValueError):
                    validate_file(source, 'config.json')
            parse.assert_not_called()


if __name__ == '__main__':
    unittest.main()
