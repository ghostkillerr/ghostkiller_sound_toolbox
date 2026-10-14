import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app_version import read_application_version


class ApplicationVersionTests(unittest.TestCase):
    def test_runtime_reads_packaged_version_after_version_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'version.json'
            path.write_text(json.dumps({'version':'2.1.0'}))
            with patch('app_version.resource_directory',return_value=folder):
                self.assertEqual(read_application_version(),'2.1.0')

    def test_invalid_version_is_not_silently_replaced_with_old_version(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'version.json'
            for value in ({},[],{'version':'2.0'},{'version':2},{'version':'broken'}):
                path.write_text(json.dumps(value))
                with self.subTest(value=value),self.assertRaises(ValueError):
                    read_application_version(path)
