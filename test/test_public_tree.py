"""Prevent accidental publication of local configuration and diagnostic data."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.check_public_tree import check_index, inspect_entry


class PublicTreeTests(unittest.TestCase):
    def test_personal_registry_settings_and_output_files_are_rejected(self):
        for name in ('settings.json','models.json','nested/settings.json.lock',
                     'training_presets.json','models/voices/example.pth',
                     'deneme/input.wav','build/report.json','.env.local'):
            with self.subTest(name=name):
                self.assertTrue(inspect_entry(name,b'{}'))

    def test_required_default_architecture_configs_are_allowed(self):
        for name in ('rvc/configs/40000.json','training/vendor/config_40000.json',
                     'instruments/vendor/config.yaml',
                     'docs/REVIEWED_UVR_SOURCE_HASHES.json','version.json'):
            with self.subTest(name=name):
                self.assertEqual(inspect_entry(name,b'{"sample_rate": 40000}'),[])

    def test_plain_and_json_escaped_user_paths_are_rejected(self):
        user_path = chr(92).join(('C:','Users','PrivateUser','voice.pth'))
        for content in (user_path,json.dumps({'path':user_path})):
            with self.subTest(content_type=type(content).__name__):
                self.assertIn('absolute user-directory path',
                              inspect_entry('docs/report.md',content.encode()))

    def test_local_reports_stay_private_without_needing_a_known_model_name(self):
        self.assertIn('local diagnostic report',inspect_entry('docs/MEASUREMENTS.json',b'{}'))

    def test_access_tokens_are_reported_without_returning_their_contents(self):
        token = b'ghp_'+b'x'*36
        findings = inspect_entry('config.py',token)
        self.assertEqual(findings,['GitHub access token'])
        self.assertNotIn(token.decode(),str(findings))

    def test_upstream_runtime_provenance_is_preserved(self):
        path = chr(92).join(('C:','Users','Builder','python'))
        self.assertEqual(inspect_entry('third_party/runtime/PYTHON.json',path.encode()),[])
        self.assertTrue(inspect_entry('copied_runtime.json',path.encode()))

    def test_checks_staged_bytes_even_after_working_copy_is_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            file = root/'report.md'
            file.write_text(chr(92).join(('C:','Users','PrivateUser','voice.pth')))
            subprocess.run(['git','-C',str(root),'add','report.md'],check=True)
            file.write_text('clean working copy')
            findings = check_index(root)
            self.assertEqual(findings,[('report.md',['absolute user-directory path'])])


if __name__ == '__main__':
    unittest.main()
