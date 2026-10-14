"""Noninteractive packaged native smoke; no model downloads or user data writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback


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
