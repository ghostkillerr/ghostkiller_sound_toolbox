"""Explicit smoke-device selection without requiring a physical GPU."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock

from app_settings import AppSettings
from smoke_training import configure_fixture_device


class SmokeDeviceTests(unittest.TestCase):
    def test_requested_device_reaches_job_preflight_without_persisting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.json'
            path.write_text('{"device":"cpu"}', encoding='utf-8')
            for device in ('cpu', 'cuda:0', 'cuda:1', 'xpu:0', 'xpu:1'):
                with self.subTest(device=device):
                    manager = Mock()
                    settings = AppSettings(path=str(path), manager=manager)
                    configure_fixture_device(settings, device)
                    self.assertEqual(settings.prepare_job(['contentvec']), device)
                    manager.require_ready.assert_called_once_with(['contentvec'])
                    self.assertEqual(path.read_text(encoding='utf-8'), '{"device":"cpu"}')

    def test_unknown_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            configure_fixture_device(Mock(), 'directml:0')


if __name__ == '__main__':
    unittest.main()
