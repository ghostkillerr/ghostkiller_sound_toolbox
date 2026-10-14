"""Release/update regression scenarios without running an EXE, UAC or installer."""
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from app_runtime import JOB_LOCK
import updater
from release_security import (InstallerPackage, RELEASE_REPOSITORY, validate_package,
                              validate_response_url, verify_installer)
from windows_installer import InstallerLaunchCancelled, ShellExecuteInfo, launch_elevated_installer, hold_installer_file
from tools.release import preflight
from tools.release.make_update_manifest import create_manifest


PAYLOAD = b'MZ' + b'verified synthetic installer fixture' * 4
URL = f'https://github.com/{RELEASE_REPOSITORY}/releases/download/v2.1.0/Ghostkiller_V2_Setup_cpu.exe'


def manifest(payload=PAYLOAD):
    return {'version': '2.1.0', 'packages': {'cpu': {'download_url': URL,
            'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}}}


def installer_build_fixture(root, installer):
    """Synthetic compile receipt for release metadata tests; never a real installer."""
    info = root/'build-info.json'
    source = hashlib.sha256(b'synthetic application sources').hexdigest()
    info.write_text(json.dumps({'backend':'cpu','purpose':'release','release_eligible':True,
                               'application_version':'2.1.0','application_source_sha256':source}))
    installer.with_suffix('.build.json').write_text(json.dumps({
        'schema_version':1,'backend':'cpu','purpose':'release','release_eligible':True,
        'application_version':'2.1.0','application_source_sha256':source,
        'build_info_sha256':preflight.sha256(info),
        'installer':{'filename':installer.name,'size':installer.stat().st_size,
                     'sha256':preflight.sha256(installer)}}))
    return info


class ImmediateThread:
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


class Parent:
    def IsBeingDeleted(self):
        return False


class Progress:
    def IsBeingDeleted(self):
        return False

    def Update(self, *args):
        return True, False

    Pulse = Update

    def Destroy(self):
        pass


class ReleaseSecurityTests(unittest.TestCase):
    def test_immutable_url_and_backend_are_required(self):
        valid = validate_package(manifest(), 'cpu')
        self.assertEqual((valid.version, valid.backend, valid.url), ('2.1.0', 'cpu', URL))
        bad_urls = [
            URL.replace('github.com', 'example.test'), URL.replace('v2.1.0', 'v2.2.0'),
            URL.replace('/download/v2.1.0/', '/latest/download/'), URL + '?version=2.1.0',
            URL.replace('github.com', 'user@github.com'), URL.replace('github.com', 'github.com:443'),
            URL.replace('ghostkillerr/', 'attacker/'), URL.replace('https:', 'http:'),
            URL.replace('Ghostkiller_V2_Setup_cpu.exe', '../setup.exe'),
            URL.replace('Ghostkiller_V2_Setup_cpu.exe', '%2e%2e.exe'), URL + '#ignored',
        ]
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                data = manifest()
                data['packages']['cpu']['download_url'] = url
                validate_package(data, 'cpu')
        with self.assertRaisesRegex(ValueError, 'paketi yok'):
            validate_package(manifest(), 'cuda')

    def test_missing_or_placeholder_hash_never_yields_package(self):
        for digest in ('', None, '0' * 64, 'a' * 64, 'bad', 'x' * 64):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                data = manifest()
                data['packages']['cpu']['sha256'] = digest
                validate_package(data, 'cpu')

    def test_legacy_hashless_manifest_cannot_be_installed(self):
        data = {'version': '2.1.0', 'download_url': URL}
        with patch.object(updater.wx, 'MessageDialog') as dialog, patch.object(updater.wx, 'MessageBox') as message, patch.object(updater, 'runtime_backend', return_value='cpu'):
            updater._show_update_dialog(Parent(), data)
        dialog.assert_not_called()
        self.assertIn('doğrulanmış kurulum', message.call_args.args[0])
        self.assertIn('/releases', message.call_args.args[0])

    def test_size_schema_rejects_bool_float_negative_and_oversize(self):
        for size in (False, -1, 0, 1.5, preflight.ROOT.stat().st_size + 9 * 1024 ** 3):
            with self.subTest(size=size), self.assertRaises(ValueError):
                data = manifest()
                data['packages']['cpu']['size'] = size
                validate_package(data, 'cpu')

    def test_redirect_host_must_remain_github_release_assets(self):
        package = validate_package(manifest(), 'cpu')
        validate_response_url(URL, package)
        validate_response_url('https://release-assets.githubusercontent.com/github-production-release-asset/file?sig=test', package)
        for url in ('http://release-assets.githubusercontent.com/file', 'https://example.test/file',
                    'https://release-assets.githubusercontent.com.evil.test/file',
                    'https://user@release-assets.githubusercontent.com/file'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_response_url(url, package)

    def test_hash_size_and_executable_header_are_independent_checks(self):
        package = validate_package(manifest(), 'cpu')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(PAYLOAD)
            verify_installer(path, package)
            path.write_bytes(PAYLOAD[:-1] + b'x')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                verify_installer(path, package)
            path.write_bytes(PAYLOAD[:-1])
            with self.assertRaisesRegex(ValueError, 'boyutu'):
                verify_installer(path, package)
            path.write_bytes(b'ZZ' + PAYLOAD[2:])
            with self.assertRaisesRegex(ValueError, 'Windows'):
                verify_installer(path, package)


class UpdateDownloadTests(unittest.TestCase):
    def setUp(self):
        self.dispatch = patch.object(updater.wx, 'CallAfter', side_effect=lambda fn, *args: fn(*args))
        self.dispatch.start()
        self.threads = patch.object(updater.threading, 'Thread', ImmediateThread)
        self.threads.start()

    def tearDown(self):
        self.dispatch.stop()
        self.threads.stop()
        if JOB_LOCK.locked():
            JOB_LOCK.release()

    def download(self, folder, body, *, response_url=URL, content_length=None, progress=None):
        response = io.BytesIO(body)
        response.headers = {} if content_length is None else {'Content-Length': str(content_length)}
        response.geturl = lambda: response_url
        with patch.object(updater.tempfile, 'mkdtemp', return_value=folder), \
             patch.object(updater.wx, 'ProgressDialog', return_value=progress or Progress()), \
             patch.object(updater.threading, 'Thread', ImmediateThread), \
             patch.object(updater.urllib.request, 'urlopen', return_value=response), \
             patch.object(updater.wx, 'MessageBox') as message, \
             patch.object(updater, '_launch_setup_and_exit', return_value=True) as launch:
            updater._download_and_run_installer(Parent(), manifest(), backend='cpu')
        return launch, message

    def test_valid_download_passes_verified_package_to_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            launch, message = self.download(folder, PAYLOAD, content_length=len(PAYLOAD))
            launch.assert_called_once()
            self.assertIsInstance(launch.call_args.args[1], InstallerPackage)
            message.assert_not_called()
            self.assertFalse(JOB_LOCK.locked())

    def test_modified_download_cleans_temp_without_launching(self):
        with tempfile.TemporaryDirectory() as folder:
            launch, message = self.download(folder, PAYLOAD[:-1] + b'x')
            launch.assert_not_called()
            self.assertIn('SHA-256', message.call_args.args[0])
            self.assertFalse(Path(folder).exists())
            self.assertFalse(JOB_LOCK.locked())

    def test_redirect_to_untrusted_host_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            launch, message = self.download(folder, PAYLOAD, response_url='https://example.test/setup.exe')
            launch.assert_not_called()
            self.assertIn('yönlendirildi', message.call_args.args[0])

    def test_content_length_mismatch_is_refused_before_file_write(self):
        with tempfile.TemporaryDirectory() as folder:
            launch, message = self.download(folder, PAYLOAD, content_length=len(PAYLOAD) + 1)
            launch.assert_not_called()
            self.assertIn('boyutu', message.call_args.args[0])

    def test_cancel_at_final_callback_does_not_launch(self):
        class Cancel(Progress):
            def Update(self, *args):
                return False, False
        with tempfile.TemporaryDirectory() as folder:
            launch, _ = self.download(folder, PAYLOAD, progress=Cancel())
            launch.assert_not_called()
            self.assertFalse(Path(folder).exists())

    def test_tamper_after_download_is_rechecked_before_uac(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(PAYLOAD[:-1] + b'x')
            with patch.object(updater, 'run_in_place_update') as launch, patch.object(updater.wx, 'GetApp') as app, patch.object(updater.wx, 'MessageBox'):
                self.assertFalse(updater._launch_setup_and_exit(path, validate_package(manifest(), 'cpu')))
            launch.assert_not_called()
            app.assert_not_called()
            self.assertFalse(JOB_LOCK.locked())

    def test_declined_uac_keeps_application_open(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(PAYLOAD)
            with patch.object(updater, 'run_in_place_update', side_effect=InstallerLaunchCancelled('cancelled')), patch.object(updater.wx, 'GetApp') as app, patch.object(updater.wx, 'MessageBox'):
                self.assertFalse(updater._launch_setup_and_exit(path, validate_package(manifest(), 'cpu'), on_failure=path.unlink))
            app.assert_not_called()
            self.assertFalse(path.exists())
            self.assertFalse(JOB_LOCK.locked())


class NativeInstallerTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows native file sharing contract')
    def test_final_hash_file_guard_blocks_write_and_delete_until_launch_finishes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'setup.exe'
            path.write_bytes(PAYLOAD)
            guard = hold_installer_file(path)
            try:
                with self.assertRaises(PermissionError):
                    path.write_bytes(b'tampered')
                with self.assertRaises(PermissionError):
                    path.unlink()
                self.assertEqual(path.read_bytes(), PAYLOAD)
            finally:
                guard.close()
            path.write_bytes(b'new')
            path.unlink()

    def test_runas_launch_uses_real_shell_contract_and_closes_handle(self):
        observed = {}
        def execute(pointer):
            info = ctypes.cast(pointer, ctypes.POINTER(ShellExecuteInfo)).contents
            observed.update(verb=info.lpVerb, file=info.lpFile, mask=info.fMask, size=info.cbSize)
            info.hProcess = 345
            return True
        close = Mock()
        self.assertTrue(launch_elevated_installer('fixture.exe', _api=(execute, lambda: 0, close)))
        self.assertEqual(observed['verb'], 'runas')
        self.assertTrue(Path(observed['file']).is_absolute())
        self.assertEqual(observed['size'], ctypes.sizeof(ShellExecuteInfo))
        self.assertTrue(observed['mask'] & 0x40)
        self.assertTrue(observed['mask'] & 0x100)
        close.assert_called_once_with(345)

    def test_shell_reports_uac_cancel_separately_from_launch_failure(self):
        for error, expected in [(1223, InstallerLaunchCancelled), (740, OSError), (2, OSError)]:
            with self.subTest(error=error), self.assertRaises(expected):
                launch_elevated_installer('fixture.exe', _api=(lambda pointer: False, lambda: error, Mock()))


class ReleaseBuildTests(unittest.TestCase):
    def test_python_3120_and_wrong_minor_cannot_produce_frozen_builds(self):
        for version in ((3,12,0),(3,11,9),(3,13,0)):
            with self.subTest(version=version),self.assertRaises(ValueError):
                preflight.validate_python_version(version)
        preflight.validate_python_version((3,12,1))
        preflight.validate_python_version((3,12,15))

    def test_vendored_licenses_retain_exact_manifest_hashes_on_windows(self):
        vendor = json.loads((preflight.ROOT/'third_party/python/manifest.json').read_text(encoding='utf-8'))
        for package in vendor.values():
            for item in package['files']:
                with self.subTest(path=item['path']):
                    preflight.checked_local_asset(preflight.ROOT,item)

    def test_real_tiny_cpu_onnx_session(self):
        preflight.validate_onnx_session('cpu')

    def test_diagnostic_artifacts_cannot_generate_update_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installer = root / 'Setup_cpu.exe'
            installer.write_bytes(PAYLOAD)
            info = root / 'build-info.json'
            info.write_text('{"backend":"cpu","purpose":"diagnostic","release_eligible":false}')
            with self.assertRaisesRegex(ValueError, 'Diagnostic'):
                create_manifest('2.1.0', [('cpu', installer, info)])

    def test_update_manifest_uses_actual_installer_hash_and_explicit_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installer = root / 'Setup_cpu.exe'
            installer.write_bytes(PAYLOAD)
            info = installer_build_fixture(root,installer)
            data = create_manifest('2.1.0', [('cpu', installer, info)], release_date='2026-10-13')
            self.assertEqual(data['packages']['cpu']['sha256'], hashlib.sha256(PAYLOAD).hexdigest())
            self.assertEqual(data['release_date'], '2026-10-13')
            self.assertTrue(data['packages']['cpu']['download_url'].endswith('/v2.1.0/Setup_cpu.exe'))

    def test_manifest_cannot_relabel_an_old_build_with_a_new_version(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installer = root/'Setup_cpu.exe'
            installer.write_bytes(PAYLOAD)
            info = installer_build_fixture(root,installer)
            with self.assertRaisesRegex(ValueError,'version'):
                create_manifest('2.2.0',[('cpu',installer,info)])

    def test_manifest_requires_matching_receipt_bytes_and_build_info(self):
        for change in ('missing_receipt','installer_bytes','build_info','wrong_backend'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                installer = root/'Setup_cpu.exe'
                installer.write_bytes(PAYLOAD)
                info = installer_build_fixture(root,installer)
                receipt = installer.with_suffix('.build.json')
                if change == 'missing_receipt':
                    receipt.unlink()
                elif change == 'installer_bytes':
                    installer.write_bytes(PAYLOAD+b'different compilation')
                elif change == 'build_info':
                    info.write_text(info.read_text()+'\n')
                else:
                    data = json.loads(receipt.read_text())
                    data['backend'] = 'cuda'
                    receipt.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    create_manifest('2.1.0',[('cpu',installer,info)])

    def test_manifest_rejects_duplicate_backend(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installer = root/'Setup_cpu.exe'
            installer.write_bytes(PAYLOAD)
            info = installer_build_fixture(root,installer)
            with self.assertRaisesRegex(ValueError,'Duplicate backend'):
                create_manifest('2.1.0',[('cpu',installer,info),('cpu',installer,info)])

    def test_all_native_profiles_are_hash_locked_and_have_one_ort(self):
        for backend in ('cpu', 'cuda', 'xpu'):
            with self.subTest(backend=backend):
                expected = preflight.locked_versions(preflight.ROOT / 'requirements' / f'{backend}.lock')
                self.assertEqual(set(expected) & preflight.ORT_NAMES,
                                 {'onnxruntime-gpu'} if backend == 'cuda' else {'onnxruntime'})
                self.assertIn('torch', expected)
                self.assertIn('audio-separator', expected)
        xpu = preflight.locked_versions(preflight.ROOT / 'requirements' / 'xpu.lock')
        self.assertEqual(xpu['intel-sycl-rt'], '2025.3.2')
        self.assertEqual(xpu['triton-xpu'], '3.7.0')

    def test_mixed_ort_distributions_are_rejected_even_when_pip_check_passes(self):
        with self.assertRaisesRegex(ValueError, 'Exactly one ORT'):
            preflight.validate_environment('cuda', expected={}, installed={'onnxruntime': '1', 'onnxruntime-gpu': '1'})

    def test_wrong_torch_backend_or_missing_cuda_provider_cannot_be_packaged(self):
        cpu = types.SimpleNamespace(version=types.SimpleNamespace(cuda=None, hip=None), __version__='2.11.0+cpu')
        cuda = types.SimpleNamespace(version=types.SimpleNamespace(cuda='12.8', hip=None), __version__='2.11.0+cu128')
        ort = types.SimpleNamespace(get_available_providers=lambda: ['CPUExecutionProvider'])
        with self.assertRaisesRegex(ValueError, 'runtime is cpu'):
            preflight.validate_environment('cuda', expected={}, installed={'onnxruntime-gpu': '1'}, torch_module=cpu, ort_module=ort, require_clean=False)
        with self.assertRaisesRegex(ValueError, 'no ONNX CUDA'):
            preflight.validate_environment('cuda', expected={}, installed={'onnxruntime-gpu': '1'}, torch_module=cuda, ort_module=ort, require_clean=False)

    def test_cpu_profile_allows_only_the_reviewed_environment(self):
        torch = types.SimpleNamespace(version=types.SimpleNamespace(cuda=None, hip=None), __version__='2.11.0+cpu')
        ort = types.SimpleNamespace(get_available_providers=lambda: ['CPUExecutionProvider'])
        expected = {'onnxruntime': '1', 'torch': '2.11.0+cpu'}
        result = preflight.validate_environment('cpu', expected=expected, installed=expected,
                                                torch_module=torch, ort_module=ort)
        self.assertEqual(result['backend'], 'cpu')
        with self.assertRaisesRegex(ValueError, 'Unreviewed packages'):
            preflight.validate_environment('cpu', expected=expected, installed={**expected, 'unrelated-app': '1'},
                                           torch_module=torch, ort_module=ort)

    def test_package_check_refuses_personal_models_but_allows_known_library_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'build-info.json').write_text('{"backend":"cpu"}')
            (root / 'THIRD_PARTY_NOTICES.md').write_text('fixture notices')
            library = root / '_internal' / 'torchcrepe' / 'assets'
            library.mkdir(parents=True)
            (library / 'full.pth').write_bytes(b'library fixture')
            self.assertGreater(preflight.validate_package_tree(root)['bytes'], 0)
            personal = root / 'private.pth'
            personal.write_bytes(b'personal fixture')
            with self.assertRaisesRegex(ValueError, 'private.pth'):
                preflight.validate_package_tree(root)

    def test_ffmpeg_source_missing_or_incomplete_blocks_build_without_executing(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(preflight.subprocess, 'run') as execute:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'manifest.json'):
                preflight.validate_ffmpeg_bundle(root)
            (root / 'manifest.json').write_text('{"version":"8.1.1","source_completeness":"ffmpeg-only"}')
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                preflight.validate_ffmpeg_bundle(root)
            execute.assert_not_called()

    def test_ffmpeg_missing_version_is_not_accepted_as_matching_every_binary(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(preflight.subprocess, 'run') as execute:
            root = Path(folder)
            for version in (None, '', 8, '8.1.1;echo'):
                (root / 'manifest.json').write_text(json.dumps({'version': version, 'source_completeness': 'complete'}))
                with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'version identifier'):
                    preflight.validate_ffmpeg_bundle(root)
            execute.assert_not_called()

    def test_release_asset_paths_cannot_escape_the_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'bundle'
            root.mkdir()
            outside = root.parent / 'outside.txt'
            outside.write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'outside bundle'):
                preflight.checked_local_asset(root, {'path': '../outside.txt', 'sha256': preflight.sha256(outside)})


if __name__ == '__main__':
    unittest.main()
