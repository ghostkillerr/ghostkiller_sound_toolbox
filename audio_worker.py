"""Audio inference runs here, outside the GUI process. No network fallback."""
import gc
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback
from audio_service import write_message


def short_input(source, directory):
    source = Path(os.path.abspath(source))
    if not source.is_file():
        raise FileNotFoundError(f'Giriş ses dosyası bulunamadı: {source}')
    target = Path(directory)/('input'+source.suffix.lower())
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)
    return str(target)


def check_audio_memory(path):
    import soundfile as sf
    from training.resources import memory_status
    info = sf.info(path)
    free = memory_status().get('available_ram_mb')
    # Decode/resample + filter/FFT temporaries and output; reject before allocation.
    estimate = info.frames*max(2,info.channels)*8*12/1024**2
    if free and estimate > free*.6:
        raise MemoryError(f'Ses için tahmini RAM {estimate:.0f} MiB; kullanılabilir RAM {free:.0f} MiB. Daha kısa bir kayıt seçin.')


class AudioEngine:
    def __init__(self, progress=None, cancelled=None, live_controls=None):
        self.converter = None
        self.device = None
        self.progress, self.cancelled = progress, cancelled
        self.live_controls = live_controls

    def execute(self, kind, payload):
        if kind == 'hardware_probe':
            from dataclasses import asdict
            from hardware import detect_hardware
            return asdict(detect_hardware())
        if kind == 'calibrate_gate':
            from live_gate import CalibrationOptions, calibrate_gate
            return calibrate_gate(CalibrationOptions(**payload),
                                  cancelled=self.cancelled or (lambda: False),
                                  progress=self.progress or (lambda message: None))
        from hardware import configure_runtime
        device = payload.get('device', 'cpu')
        configure_runtime(device)
        if kind == 'ping':
            return {'pid':os.getpid(), 'device':device,
                    'helper_cache_entries':len(self.converter.helper_cache) if self.converter is not None else 0}
        if kind == 'live_cover':
            from live_cover import LiveOptions, run_live
            options = LiveOptions(**payload['options']).validate()
            if options.device != device:
                raise ValueError('Canlı ses cihazı işlem ayarıyla eşleşmiyor.')
            return run_live(options, cancelled=self.cancelled or (lambda: False),
                            progress=self.progress or (lambda message: None), controls=self.live_controls)
        if kind == 'instruments':
            from instruments.engine import separate_file
            return separate_file(payload['input_file'],payload['output_dir'],payload['model_root'],
                                 profile=payload['profile'],stems=payload['stems'],device=device,
                                 cancelled=self.cancelled,progress=self.progress,
                                 output_format=payload.get('output_format', 'flac'),
                                 output_channels=payload.get('output_channels', 'original'))
        if kind == 'cover':
            from rvc.infer.infer import VoiceConverter
            from rvc.infer.quality_policy import InferenceQualityPolicy
            if self.converter is None or device != self.device:
                self.close()
                self.converter = VoiceConverter(device=device, allow_model_download=False)
                self.device = device
            options = dict(payload['options'])
            options['quality_policy'] = InferenceQualityPolicy(**payload.get('quality_policy', {}))
            try:
                self.converter.convert_audio(**options)
                return options['audio_output_path']
            finally:
                self.converter.cleanup_model(release_helpers=False)
        if kind == 'restore_vocal':
            from restoration.engine import restore_file
            from app_runtime import validate_audio_file
            for path in (payload['reference_file'],payload['cleaned_file']):
                check_audio_memory(path)
                validate_audio_file(path)
            # The separator's allocator cache must not occupy the repair model's VRAM.
            gc.collect()
            import torch
            if device.startswith('cuda'):
                torch.cuda.empty_cache()
            return restore_file(payload['reference_file'],payload['cleaned_file'],
                payload['output_file'],payload['model_dir'],device,
                cancelled=self.cancelled,progress=self.progress)
        if kind == 'separate':
            from separator_backend import LocalSeparator
            import tempfile
            import soundfile as sf
            from separation_audio import reflected_vr_input, trim_to_source_duration
            from app_runtime import validate_audio_file
            check_audio_memory(payload['input_file'])
            validate_audio_file(payload['input_file'])
            source_info = sf.info(payload['input_file'])
            is_vr = payload['model_name'] in ('UVR-DeEcho-DeReverb.pth','UVR-DeNoise.pth')
            with tempfile.TemporaryDirectory(prefix='input_', dir=payload['output_dir']) as folder:
                source = (reflected_vr_input(payload['input_file'],folder) if is_vr else
                          short_input(payload['input_file'], folder))
                separator = LocalSeparator(output_dir=payload['output_dir'], output_format='FLAC',
                    model_file_dir=payload['model_dir'], device=device, use_autocast=False)
                try:
                    separator.load_model(model_filename=payload['model_name'])
                    outputs = separator.separate(source)
                    if not isinstance(outputs, (tuple,list)) or not outputs:
                        raise RuntimeError('Ayrıştırma motoru çıktı dosyası döndürmedi.')
                    paths = []
                    root = os.path.realpath(payload['output_dir'])
                    for output in outputs:
                        path = os.path.realpath(output if os.path.isabs(output) else os.path.join(root,output))
                        if os.path.normcase(os.path.commonpath([root,path])) != os.path.normcase(root) or not os.path.isfile(path):
                            raise RuntimeError('Geçersiz ayrıştırma çıktısı.')
                        if is_vr:
                            trim_to_source_duration(path,source_info)
                        paths.append(path)
                    return paths
                finally:
                    del separator
                    gc.collect()
        raise ValueError('Bilinmeyen ses worker isteği.')

    def close(self):
        if self.converter is not None:
            self.converter.cleanup_model()
            self.converter = None


def main(argv=None):
    from app_runtime import (app_directory, resource_directory, configure_runtime_cache,
                             configure_thread_environment, configure_ffmpeg_environment)
    configure_runtime_cache()
    configure_thread_environment()
    configure_ffmpeg_environment()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise ValueError('Worker oturum klasörü gerekli.')
    root = Path(arguments[0]).resolve()
    if not root.is_dir():
        raise ValueError('Worker oturum klasörü geçersiz.')
    done = threading.Event()
    def heartbeat():
        while not done.is_set():
            (root/'heartbeat').touch()
            done.wait(1.)
    beat = threading.Thread(target=heartbeat,daemon=True)
    beat.start()
    sequence = 1
    def report(text):
        write_message(root/f'progress_{sequence}.json', {'message': text})
        if text.startswith('Mikrofon açıldı.'):
            write_message(root/f'live_started_{sequence}.json', {'message': text})

    def live_controls():
        path = root/'live_controls.json'
        if not path.exists():
            return None
        if path.stat().st_size > 4096:
            raise ValueError('Canlı ses ayarı boyut sınırını aşıyor.')
        return json.loads(path.read_text(encoding='utf-8'))

    engine = AudioEngine(progress=report,
                         live_controls=live_controls,
                         cancelled=lambda:(root/f'cancel_{sequence}').exists() or (root/'stop').exists())
    try:
        while not (root/'stop').exists():
            request_path = root/f'request_{sequence}.json'
            if not request_path.exists():
                done.wait(.08)
                continue
            try:
                if request_path.stat().st_size > 1024**2:
                    raise ValueError('Worker isteği boyut sınırını aşıyor.')
                request = json.loads(request_path.read_text(encoding='utf-8'))
                result = engine.execute(request['kind'],request['payload'])
                response = {'ok':True,'result':result}
            except (Exception,SystemExit) as error:
                traceback.print_exc()
                response = {'ok':False,'error':f'{type(error).__name__}: {str(error) or "Motor beklenmeden sonlandı."}'}
            write_message(root/f'response_{sequence}.json',response)
            sequence += 1
    finally:
        done.set()
        beat.join(timeout=2.)
        engine.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
