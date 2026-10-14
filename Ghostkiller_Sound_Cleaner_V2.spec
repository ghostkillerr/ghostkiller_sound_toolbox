# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
from tools.release.prepare_build import prepare_build, external_backend_files

backend = os.environ.get('GHOSTKILLER_BACKEND', '')
purpose = os.environ.get('GHOSTKILLER_BUILD_PURPOSE', 'release')
ffmpeg_dir = os.environ.get('GHOSTKILLER_FFMPEG_DIR', os.path.join(SPECPATH, 'tools', 'ffmpeg'))
release_datas, release_binaries = prepare_build(backend, ffmpeg_dir, purpose=purpose)
backend_datas, backend_binaries = external_backend_files(backend)
artifact_name = 'Ghostkiller_Sound_Cleaner_V2' if purpose == 'release' else 'Ghostkiller_Sound_Toolbox_Diagnostic_' + backend

datas = [
    ('version.json', '.'),
    ('logo.ico', '.'),
    ('lisans.txt', '.'),
    ('update_helper.ps1', '.'),
    ('rvc/configs/*.json', 'rvc/configs'),
    ('training/vendor/config_*.json', 'training/vendor'),
    ('training/vendor/LICENSE', 'training/vendor'),
    ('training/vendor/NOTICE.md', 'training/vendor'),
]
datas += release_datas + backend_datas
binaries = release_binaries + backend_binaries
hiddenimports = [
    'updater',
    'app_runtime',
    'native_process',
    'compute_backend',
    'registry_store',
    'startup_diagnostics',
    'audio_worker',
    'audio_service',
    'release_security',
    'windows_installer',
    'release_self_test',
    'rvc.infer.model_validation',
    'app_settings',
    'hardware',
    'model_manager',
    'separator_backend',
    'separation_steps',
    'ui_settings',
    'ui_training',
    'ui_common',
    'training.worker',
    'training.engine',
    'training.dataset',
    'training.analysis',
    'training.pitch_quality',
    'training.index',
    'ui_separator',
    'ui_cover',
    'wx',
    'pydub',
    'scipy.special',
    'scipy.spatial.transform._rotation_groups',
    'soundfile',
    'tqdm',
    'onnxruntime',
    'yaml',
    'json',
    're',
    'threading',
    'subprocess',
    'gc',
    'sys',
    'os',
    'transformers',
    'torchcrepe',
    'torchfcpe',
    'safetensors',
    'faiss',
    'stftpitchshift',
    'pedalboard',
    'soxr',
    'noisereduce'
]

def collect_runtime(package):
    return collect_all(package, exclude_datas=['**/tests/**', '**/test/**', '**/__pycache__/**'],
                       filter_submodules=lambda name: not any(part in {'test', 'tests'} for part in name.split('.')))


tmp_ret = collect_runtime('torch')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('torchvision')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('torchaudio')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('audio_separator')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('librosa')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('samplerate')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('torchcrepe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_runtime('torchfcpe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    # TorchScript reads the original RVC functions/classes at runtime.
    module_collection_mode={'rvc': 'pyz+py', 'training': 'pyz+py'},
    runtime_hooks=['tools/release/pyi_rth_backend.py'],
    excludes=['test', 'tests', 'pytest', 'tkinter', 'IPython', 'notebook'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=artifact_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=artifact_name,
)
