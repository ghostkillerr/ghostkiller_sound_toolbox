"""Noninteractive packaged native smoke; no model downloads or user data writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback


def check_audio_exports(directory):
    """Exercise the installed codecs and channel conversion without user audio."""
    import numpy as np
    import soundfile as sf
    from audio_export import OUTPUT_FORMATS, OUTPUT_CHANNELS, export_audio

    results = []
    with tempfile.TemporaryDirectory(prefix='audio_formats_', dir=directory) as folder:
        folder = Path(folder)
        rate = 40000  # Also exercises the MP3 resampler used by RVC outputs.
        signal = .15 * np.sin(np.arange(4000, dtype='float32') * .07)
        for source_channels in (1, 2):
            data = signal if source_channels == 1 else np.column_stack((signal, signal * .5))
            source = folder / f'Kaynak {source_channels}.wav'
            sf.write(source, data, rate, subtype='FLOAT')
            for output_format in OUTPUT_FORMATS:
                for mode in OUTPUT_CHANNELS:
                    target = folder / f'Çıktı {source_channels} {mode}.{output_format}'
                    saved = Path(export_audio(source, target, output_format, output_channels=mode))
                    decoded, actual_rate = sf.read(saved, dtype='float32', always_2d=True)
                    info = sf.info(saved)
                    channels = source_channels if mode == 'original' else 1 if mode == 'mono' else 2
                    expected_frames = round(len(signal) * actual_rate / rate)
                    if (info.format != output_format.upper() or decoded.shape[1] != channels
                            or abs(len(decoded) - expected_frames) > 1
                            or not np.isfinite(decoded).all() or float(np.max(np.abs(decoded))) < .01):
                        raise RuntimeError(f'Audio export roundtrip failed: {output_format}/{mode}/{source_channels}')
                    if output_format in ('wav', 'flac'):
                        expected = data[:, None] if source_channels == 1 else data
                        if mode == 'mono':
                            expected = expected.mean(axis=1, keepdims=True)
                        elif mode == 'stereo' and source_channels == 1:
                            expected = expected.repeat(2, axis=1)
                        if info.subtype != 'PCM_24' or not np.allclose(decoded, expected, atol=2**-23, rtol=0):
                            raise RuntimeError('Lossless export precision or channel conversion failed.')
                    results.append({'format': output_format, 'source_channels': source_channels,
                                    'mode': mode, 'channels': channels, 'sample_rate': actual_rate})
        previous = saved.read_bytes()
        numbered = Path(export_audio(source, target, output_format, output_channels=mode))
        if numbered.name != target.stem + ' (2)' + target.suffix or saved.read_bytes() != previous:
            raise RuntimeError('Numbered export replaced a previous result.')
    return {'roundtrips': results, 'numbered_output_preserved': True}


def check_live_gate():
    """Validate packaged live modules without opening a real microphone/output."""
    import numpy as np
    from live_audio import AudioDevice, RATE
    from live_cover import LiveWindow
    from live_gate import CalibrationOptions, NoiseGate, calibrate_gate
    from ui_live_cover import LiveCoverPanel

    gate = NoiseGate(True, -1000)
    if gate.process(np.zeros(RATE//100, dtype='float32'))[1]:
        raise RuntimeError('Very low gate threshold opened on digital silence.')
    closed, reads = [], []

    class SyntheticInput:
        actual_device = AudioDevice(0, 'Synthetic calibration input')
        def __enter__(self):
            return self
        def __exit__(self, *_):
            closed.append(True)
        def read(self, stopped):
            if stopped():
                raise InterruptedError()
            reads.append(1)
            return np.full(RATE//50, .0001, dtype='float32')

    result = calibrate_gate(CalibrationOptions(0, SyntheticInput.actual_device.name),
                            input_factory=lambda device: SyntheticInput())
    if (closed != [True] or len(reads) != 500 or result['seconds'] != 10
            or result['threshold_db'] != -70 or result['close_db'] != -76):
        raise RuntimeError('Packaged microphone calibration or cleanup failed.')
    window = LiveWindow(RATE//4)
    converted = window.process(np.full(RATE//4, .1, dtype='float32'), lambda audio: audio*.5)
    if len(converted) != RATE//4-window.overlap or not np.isfinite(converted).all():
        raise RuntimeError('Packaged live audio window failed.')
    return {'calibration_seconds': 10, 'input_closed': True, 'microphone_opened': False,
            'output_opened': False, 'low_threshold_silence': True, 'ui_module': LiveCoverPanel.__name__}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        raise ValueError('Self-test result JSON path required.')
    output = Path(argv[0]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)),
              'pid': os.getpid(), 'python': sys.version,
              'scope': 'Local host native smoke; not a clean Windows VM or AMD/Intel GPU validation.'}
    started = time.monotonic()
    try:
        import numpy as np
        import torch
        import soundfile as sf
        import wx
        from app_runtime import resource_directory, ffmpeg_executable
        from audio_service import NativeAudioSession
        from tools.release.preflight import validate_onnx_session
        # Imports validate DLL loading and module collection without model assets.
        from rvc.infer.infer import VoiceConverter
        from rvc.infer import model_validation
        from training import engine
        from separator_backend import LocalSeparator
        from instruments.models import load_model
        from restoration.engine import restore_file
        import model_download
        import ui_operation
        from ui_model_terms import RestorationTermsDialog, DemucsTermsDialog
        resources = Path(resource_directory())
        info_path = resources / 'build-info.json'
        result['build'] = json.loads(info_path.read_text(encoding='utf-8')) if info_path.is_file() else {'purpose': 'source'}
        result['torch'] = torch.__version__
        x = torch.randn(8, 8, requires_grad=True)
        loss = (x @ x.T).square().mean()
        loss.backward()
        if not bool(torch.isfinite(x.grad).all().item()):
            raise RuntimeError('CPU forward/backward non-finite.')
        result['cpu_forward_backward'] = True
        validate_onnx_session('cpu')
        result['onnx_cpu_session'] = True
        worker_device = 'cpu'
        if result['build'].get('backend') == 'cuda':
            if torch.cuda.is_available():
                # Exercise the packaged DLLs on a real GPU when this host has
                # one; a CUDA package must also start on a CPU-only Windows VM.
                worker_device = 'cuda:0'
                x = torch.randn(8, 8, device=worker_device, requires_grad=True)
                (x @ x.T).square().mean().backward()
                if not bool(torch.isfinite(x.grad).all().item()):
                    raise RuntimeError('CUDA forward/backward non-finite.')
                result['cuda_forward_backward'] = True
                result['cuda_device'] = torch.cuda.get_device_name(0)
                validate_onnx_session('cuda')
                result['onnx_cuda_session'] = True
            else:
                result['cuda_hardware_check'] = 'skipped: no available NVIDIA GPU on this host'
        app = wx.App(False)
        frame = wx.Frame(None, title='Native smoke', size=(300, 200))
        frame.Show(False)
        panel = wx.Panel(frame)
        button = wx.Button(panel, label='Native test button')
        button.SetName('Native test button')
        gauge = wx.Gauge(panel, range=100)
        gauge.SetValue(50)
        if not frame.GetHandle() or button.GetName() != 'Native test button' or gauge.GetValue() != 50:
            raise RuntimeError('Native wx control initialization failed.')
        result['wx'] = wx.version()
        result['hidden_native_controls'] = True
        for dialog_type in (RestorationTermsDialog, DemucsTermsDialog):
            with dialog_type(frame) as dialog:
                if dialog.GetDefaultItem().GetId() != wx.ID_CANCEL:
                    raise RuntimeError('Optional model terms must default to cancel.')
        result['optional_model_dialogs'] = True
        from ui_models import AddModelDialog
        from ui_help import HELP, application_identity
        with AddModelDialog(frame, ()) as dialog:
            if dialog.Value() != ('', {'pth': '', 'index': ''}):
                raise RuntimeError('Packaged model form has unexpected defaults.')
        identity = application_identity()
        if len(HELP) != 5 or 'Ghostkiller Sound Toolbox' not in identity:
            raise RuntimeError('Packaged offline help or application identity missing.')
        if result['frozen'] and result['build']['backend'].upper() not in identity:
            raise RuntimeError('Packaged About information does not identify its backend.')
        result['usability_help_and_model_form'] = True
        frame.Destroy()
        app.Destroy()
        with tempfile.TemporaryDirectory(prefix='release_native_', dir=output.parent) as folder:
            folder = Path(folder)
            source = folder / 'Türkçe ses.wav'
            destination = folder / 'Türkçe çıktı.flac'
            sf.write(source, np.sin(np.arange(1600) * .1).astype(np.float32) * .1, 16000)
            ffmpeg = ffmpeg_executable()
            ffprobe = ffmpeg_executable('ffprobe')
            subprocess.run([str(ffmpeg), '-nostdin', '-hide_banner', '-v', 'error',
                            '-i', str(source), '-c:a', 'flac', str(destination)],
                           capture_output=True, check=True, timeout=30,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            audio, rate = sf.read(destination)
            if rate != 16000 or not np.isfinite(audio).all() or len(audio) != 1600:
                raise RuntimeError('Bundled FFmpeg FLAC roundtrip failed.')
            probe = subprocess.run([str(ffprobe), '-v', 'error', '-show_streams', '-of', 'json', str(destination)],
                                   capture_output=True, check=True, timeout=15,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if json.loads(probe.stdout)['streams'][0]['codec_name'] != 'flac':
                raise RuntimeError('Bundled FFprobe failed.')
            result['ffmpeg_flac_roundtrip_unicode'] = True
            result['audio_exports'] = check_audio_exports(folder)
            result['live_gate'] = check_live_gate()
            with NativeAudioSession(directory=output.parent / 'native_smoke_cache') as session:
                ping = session.execute('ping', {'device': worker_device})
                if ping.get('pid') == os.getpid() or ping.get('device') != worker_device:
                    raise RuntimeError('Audio worker did not run as a separate native process.')
                result['audio_worker'] = ping
            training_result = folder / 'training-probe.json'
            command = ([sys.executable, '--training-worker'] if getattr(sys, 'frozen', False)
                       else [sys.executable, '-u', '-m', 'training.worker'])
            trained = subprocess.run([*command, '--probe', str(training_result)],
                                     capture_output=True, timeout=45,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if trained.returncode != 0 or not training_result.is_file():
                raise RuntimeError(f'Training worker probe failed ({trained.returncode}): ' +
                                   trained.stderr.decode('utf-8', errors='replace'))
            probe = json.loads(training_result.read_text(encoding='utf-8'))
            if not probe.get('ok') or probe.get('pid') == os.getpid() or probe.get('device') != 'cpu':
                raise RuntimeError('Training worker did not run as a separate native process.')
            result['training_worker'] = probe
        result['ok'] = True
    except Exception as error:
        result['error'] = str(error) or type(error).__name__
        result['traceback'] = traceback.format_exc()
    result['seconds'] = round(time.monotonic() - started, 3)
    temporary = output.with_suffix('.part')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, output)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
