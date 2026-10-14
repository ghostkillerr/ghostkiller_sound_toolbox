"""Public site staging must never expose unrelated local application data."""
import tempfile
from pathlib import Path
import unittest
from tools.build_site import ROOT, build_site


class SiteBuildTests(unittest.TestCase):
    def test_only_public_assets_are_staged(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            target = build_site(folder)
            self.assertEqual({item.name for item in target.iterdir()},
                             {'index.html','styles.css','app.mjs','logo.ico','lisans.txt','version.json','.nojekyll'})
            self.assertEqual((target/'version.json').read_bytes(), (ROOT/'version.json').read_bytes())

    def test_existing_private_file_is_rejected_without_deleting_it(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as folder:
            secret = Path(folder)/'private-settings.json'
            secret.write_bytes(b'private fixture')
            with self.assertRaisesRegex(ValueError, 'unrelated files'):
                build_site(folder)
            self.assertEqual(secret.read_bytes(), b'private fixture')

    def test_output_cannot_escape_build_directory(self):
        with self.assertRaisesRegex(ValueError, 'inside build'):
            build_site(ROOT/'public-unsafe-output')


if __name__ == '__main__':
    unittest.main()
