"""Opening the GUI stays engine-free; offline setups preserve their data slices."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test import test_installer_build as installer_tests
from tools.release.build_installer import validate_installer_input
from tools.release.build_offline_installer import compile_offline_installer
from startup_diagnostics import process_age_seconds

ROOT = Path(__file__).resolve().parents[1]


class StartupPackagingTests(unittest.TestCase):
    def test_external_archive_is_required_before_building_installer(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            installer_tests.InstallerBuildTests().fixture(root)
            (root / 'Ghostkiller_Sound_Cleaner_V2.pkg').unlink()
            with self.assertRaisesRegex(ValueError, 'Ghostkiller_Sound_Cleaner_V2.pkg'):
                validate_installer_input(root, 'cpu')

    def test_hidden_startup_probe_uses_empty_data_without_importing_engines(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / 'probe.json'
            snapshots = {name: (ROOT / name).read_bytes() for name in ('settings.json', 'models.json')
                         if (ROOT / name).exists()}
            result = subprocess.run([sys.executable, 'main.py', '--startup-probe', str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertTrue(report['ok'])
            self.assertEqual(report['heavy_modules'], [])
            self.assertGreater(report['python_to_frame_s'], 0)
            self.assertFalse(any(Path(directory).glob('startup-probe-*')))
            for name, content in snapshots.items():
                self.assertEqual((ROOT / name).read_bytes(), content)

    @unittest.skipUnless(os.name == 'nt', 'Windows process creation timestamp')
    def test_process_age_includes_loader_time(self):
        age = process_age_seconds()
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)

    def test_real_hardware_probe_keeps_torch_out_of_parent_process(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            code = ("import sys; from unittest.mock import patch; "
                    "from hardware import detect_hardware_isolated; "
                    "import app_runtime; "
                    "app_runtime.data_directory=lambda:sys.argv[1]; "
                    "report=detect_hardware_isolated(); "
                    "assert report.cpu.device=='cpu' and report.runtime.startswith('PyTorch'); "
                    "assert 'torch' not in sys.modules and 'onnxruntime' not in sys.modules")
            result = subprocess.run([sys.executable, '-c', code, directory], cwd=ROOT,
                                    capture_output=True, text=True, timeout=90,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hardware_probe_can_cancel_before_dll_initialization_finishes(self):
        from audio_service import NativeAudioSession
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            command = [sys.executable, '-c', 'import time; time.sleep(60)']
            with NativeAudioSession(command=command, directory=directory) as session:
                with self.assertRaisesRegex(InterruptedError, 'Donanım kontrolü iptal'):
                    session.execute('hardware_probe', {}, cancelled=lambda: True)
                self.assertIsNotNone(session.process.poll())
                self.assertTrue(session._closed)

    def offline_fixture(self, root, outcome='good'):
        package = root / 'package'
        (package / '_internal').mkdir(parents=True)
        (package / '_internal/build-info.json').write_text(json.dumps({'application_source_sha256': 'a' * 64}))
        def compiler(command, **kwargs):
            self.assertIn('/DOfflineBundle=1', command)
            stage = Path(next(value[2:] for value in command if value.startswith('/O')))
            stem = 'Ghostkiller_V2_Setup_cpu_2.1.0'
            (stage / (stem + '.exe')).write_bytes(b'MZlauncher' if outcome != 'bad_pe' else b'invalid')
            if outcome == 'large_exe':
                with (stage / (stem + '.exe')).open('ab') as stream:
                    stream.truncate(6 * 1024**2)
            if outcome != 'missing_slice':
                (stage / (stem + '-1.bin')).write_bytes(b'compressed installer data')
            if outcome == 'changed_metadata':
                (package / '_internal/build-info.json').write_text('{}')
        return package, compiler

    def test_zip_contains_exact_launcher_data_and_hash_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            package, compiler = self.offline_fixture(root)
            with patch('tools.release.build_offline_installer.validate_installer_input', return_value='2.1.0'), \
                 patch('tools.release.build_offline_installer.find_compiler', return_value='fixture'), \
                 patch('tools.release.build_offline_installer.subprocess.run', side_effect=compiler):
                archive = compile_offline_installer(package, 'cpu', output_dir=root / 'output')
            receipt = json.loads(archive.with_suffix('.build.json').read_text(encoding='utf-8'))
            self.assertEqual(receipt['format'], 'offline-zip')
            self.assertEqual(receipt['installer']['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()), {entry['filename'] for entry in receipt['files']})
                for entry in receipt['files']:
                    data = bundle.read(entry['filename'])
                    self.assertEqual(len(data), entry['size'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])

    def test_invalid_compiler_outputs_never_replace_previous_package(self):
        for outcome in ('missing_slice', 'bad_pe', 'large_exe', 'changed_metadata'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                package, compiler = self.offline_fixture(root, outcome)
                output = root / 'output'
                output.mkdir()
                previous = output / 'Ghostkiller_V2_Setup_cpu_2.1.0_offline.zip'
                previous.write_bytes(b'previous accepted bundle')
                with patch('tools.release.build_offline_installer.validate_installer_input', return_value='2.1.0'), \
                     patch('tools.release.build_offline_installer.find_compiler', return_value='fixture'), \
                     patch('tools.release.build_offline_installer.subprocess.run', side_effect=compiler):
                    with self.assertRaises(ValueError):
                        compile_offline_installer(package, 'cpu', output_dir=output)
                self.assertEqual(previous.read_bytes(), b'previous accepted bundle')

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell 7 extraction verifier')
    def test_offline_extraction_validates_entries_before_writing(self):
        for outcome in ('good', 'traversal', 'duplicate', 'bad_hash', 'missing'):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                archive = root / 'bundle.zip'
                setup = 'Ghostkiller_V2_Setup_cpu_2.1.0.exe'
                files = {setup: b'MZfixture', setup[:-4] + '-1.bin': b'data', 'ONCE_OKU.txt': b'guide'}
                entries = [{'filename': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                           for name, data in files.items()]
                if outcome == 'traversal':
                    files['../outside.txt'] = b'outside'
                elif outcome == 'missing':
                    files.pop('ONCE_OKU.txt')
                elif outcome == 'bad_hash':
                    files['ONCE_OKU.txt'] = b'wrong'
                with zipfile.ZipFile(archive, 'w') as bundle:
                    for name, data in files.items():
                        bundle.writestr(name, data)
                    if outcome == 'duplicate':
                        bundle.writestr('once_oku.txt', b'guide')
                receipt = root / 'receipt.json'
                receipt.write_text(json.dumps({'format': 'offline-zip', 'setup_filename': setup,
                    'files': entries, 'installer': {'filename': archive.name, 'size': archive.stat().st_size,
                    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}}))
                destination = root / 'expanded'
                result = subprocess.run(['pwsh', '-NoProfile', '-File',
                    str(ROOT / 'tools/release/expand_offline_installer.ps1'), '-Archive', str(archive),
                    '-Receipt', str(receipt), '-Destination', str(destination)], capture_output=True,
                    text=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if outcome == 'good':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual((destination / setup).read_bytes(), b'MZfixture')
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(destination.exists())
                    self.assertFalse((root / 'outside.txt').exists())
