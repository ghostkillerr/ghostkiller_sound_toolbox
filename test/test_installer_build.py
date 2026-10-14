"""Installer preflight rejects unsafe/incomplete inputs before launching ISCC."""
import json
from pathlib import Path
import tempfile
import unittest
from app_version import read_application_version
from unittest.mock import patch
from tools.release.build_installer import validate_installer_input, compile_installer
from tools.release.preflight import ROOT, sha256
from tools.release.source_identity import source_digest


class InstallerBuildTests(unittest.TestCase):
    def fixture(self,root):
        internal = root/'_internal'
        internal.mkdir()
        info = {'backend':'cpu','purpose':'release','release_eligible':True,
                'python':'3.12.15',
                'application_version':read_application_version(),
                'application_source_sha256':source_digest(),
                'dependency_lock_sha256':sha256(ROOT/'requirements/cpu.lock'),
                'common_lock_sha256':sha256(ROOT/'requirements/common.lock')}
        (internal/'build-info.json').write_text(json.dumps(info))
        (internal/'version.json').write_bytes((ROOT/'version.json').read_bytes())
        for relative in ('Ghostkiller_Sound_Cleaner_V2.exe','_internal/python312.dll','_internal/ffmpeg.exe','_internal/ffprobe.exe',
                         '_internal/vcruntime140.dll','_internal/vcruntime140_1.dll','_internal/msvcp140.dll',
                         '_internal/logo.ico','_internal/lisans.txt','_internal/third_party/python/manifest.json',
                         '_internal/update_helper.ps1',
                         '_internal/rvc/configs/24000.json','_internal/rvc/configs/32000.json',
                         '_internal/rvc/configs/40000.json','_internal/rvc/configs/48000.json',
                         '_internal/rvc/lib/algorithm/commons.py','_internal/rvc/lib/algorithm/synthesizers.py',
                         '_internal/training/vendor/config_32000.json','_internal/training/vendor/config_40000.json',
                         '_internal/training/vendor/config_48000.json','_internal/training/vendor/LICENSE',
                         '_internal/training/vendor/NOTICE.md','_internal/THIRD_PARTY_NOTICES.md'):
            path = root/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            source = ROOT/relative.removeprefix('_internal/')
            path.write_bytes(source.read_bytes() if source.is_file() else b'test fixture')
        material = internal/'third_party/ffmpeg'
        material.mkdir(parents=True)
        (material/'source.txt').write_bytes(b'fixture source material')
        entry = {'path':'source.txt','sha256':sha256(material/'source.txt')}
        manifest = {'source_completeness':'complete', 'configure':'--enable-libsoxr',
                    'source_components':{'ffmpeg':['source.txt'],'libsoxr':['source.txt']},
                    'licenses':[entry], 'sources':[entry], 'build_recipes':[entry],
                    'binaries':[{'path':name,'sha256':sha256(internal/name)} for name in ('ffmpeg.exe','ffprobe.exe')]}
        (material/'manifest.json').write_text(json.dumps(manifest))
        runtime=internal/'third_party/runtime'
        runtime.mkdir()
        entries=[]
        for name in ('LICENSE.txt','LICENSE.cpython.txt','PYTHON.json'):
            (runtime/name).write_bytes(b'synthetic runtime license fixture')
            entries.append({'path':name,'sha256':sha256(runtime/name)})
        (runtime/'manifest.json').write_text(json.dumps({'python':info['python'],
            'python_dll_sha256':sha256(internal/'python312.dll'),'files':entries}))
        return internal, info

    def test_complete_fixture_and_missing_training_data(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,_ = self.fixture(root)
            self.assertEqual(validate_installer_input(root,'cpu'),read_application_version())
            (internal/'training/vendor/config_40000.json').unlink()
            with self.assertRaisesRegex(ValueError,'config_40000'):validate_installer_input(root,'cpu')

    def test_diagnostic_wrong_backend_and_stale_locks_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,info = self.fixture(root)
            with self.assertRaisesRegex(ValueError,'backend'):validate_installer_input(root,'cuda')
            for changed in ({'purpose':'diagnostic','release_eligible':False},{'common_lock_sha256':'stale'},
                            {'application_source_sha256':'stale'},{'python':'3.12.0'}):
                (internal/'build-info.json').write_text(json.dumps({**info,**changed}))
                with patch('tools.release.build_installer.subprocess.run') as execute:
                    with self.assertRaises(ValueError):compile_installer(root,'cpu','ISCC.exe')
                    execute.assert_not_called()

    def test_incomplete_or_tampered_ffmpeg_material_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,_ = self.fixture(root)
            (internal/'third_party/ffmpeg/source.txt').write_bytes(b'changed')
            with self.assertRaises(ValueError):validate_installer_input(root,'cpu')

    def test_private_models_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            self.fixture(root)
            (root/'private.pth').write_bytes(b'personal model')
            with self.assertRaisesRegex(ValueError,'private.pth'):validate_installer_input(root,'cpu')

    def test_each_rvc_config_and_product_resource_is_required(self):
        for relative in ('rvc/configs/24000.json','rvc/configs/32000.json','rvc/configs/40000.json',
                         'rvc/configs/48000.json','logo.ico','lisans.txt','third_party/python/manifest.json',
                         'vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll',
                         'third_party/runtime/manifest.json',
                         'update_helper.ps1',
                         'rvc/lib/algorithm/commons.py','rvc/lib/algorithm/synthesizers.py'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = Path(folder)
                internal,_ = self.fixture(root)
                (internal/relative).unlink()
                with self.assertRaisesRegex(ValueError,'Required packaged file missing'):
                    validate_installer_input(root,'cpu')

    def test_wrong_config_rate_and_build_version_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,info = self.fixture(root)
            (internal/'build-info.json').write_text(json.dumps({**info,'application_version':'9.9.9'}))
            with self.assertRaisesRegex(ValueError,'version'): validate_installer_input(root,'cpu')
            (internal/'build-info.json').write_text(json.dumps(info))
            (internal/'rvc/configs/40000.json').write_text('{"data":{"sample_rate":48000},"model":{}}')
            with self.assertRaisesRegex(ValueError,'model config invalid'): validate_installer_input(root,'cpu')

    def test_torchscript_source_must_match_the_compiled_application(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,_ = self.fixture(root)
            source = internal/'rvc/lib/algorithm/commons.py'
            source.write_bytes(source.read_bytes()+b'\n# stale source fixture\n')
            with self.assertRaisesRegex(ValueError,'TorchScript source differs'):
                validate_installer_input(root,'cpu')

    def test_cpython_binary_and_license_material_must_match(self):
        for changed in ('python312.dll','third_party/runtime/LICENSE.txt'):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root=Path(folder)
                internal,_=self.fixture(root)
                (internal/changed).write_bytes(b'changed runtime fixture')
                with self.assertRaises(ValueError):
                    validate_installer_input(root,'cpu')

    def test_compilation_records_fresh_installer_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            internal,info = self.fixture(root)
            (root/'Ghostkiller_Kurulum.iss').write_text('; compiler fixture')
            version = read_application_version()
            def compiler(command,**kwargs):
                output = Path(next(arg[2:] for arg in command if arg.startswith('/O')))
                (output/f'Ghostkiller_V2_Setup_cpu_{version}.exe').write_bytes(b'MZsynthetic compiler fixture')
            with patch('tools.release.build_installer.ROOT',root), \
                 patch('tools.release.build_installer.validate_installer_input',return_value=version), \
                 patch('tools.release.build_installer.shutil.which',return_value='fixture-compiler'), \
                 patch('tools.release.build_installer.subprocess.run',side_effect=compiler):
                installer = compile_installer(root,'cpu','fixture-compiler')
            receipt = json.loads(installer.with_suffix('.build.json').read_text())
            self.assertEqual(receipt['installer']['sha256'],sha256(installer))
            self.assertEqual(receipt['build_info_sha256'],sha256(internal/'build-info.json'))
            self.assertEqual(receipt['application_version'],version)

    def test_success_without_new_output_cannot_relabel_old_installer(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            self.fixture(root)
            version = read_application_version()
            output = root/'Setup'
            output.mkdir()
            old = output/f'Ghostkiller_V2_Setup_cpu_{version}.exe'
            old.write_bytes(b'MZprevious installer')
            with patch('tools.release.build_installer.ROOT',root), \
                 patch('tools.release.build_installer.validate_installer_input',return_value=version), \
                 patch('tools.release.build_installer.shutil.which',return_value='fixture-compiler'), \
                 patch('tools.release.build_installer.subprocess.run'):
                with self.assertRaisesRegex(ValueError,'fresh installer'):
                    compile_installer(root,'cpu','fixture-compiler')
            self.assertEqual(old.read_bytes(),b'MZprevious installer')
