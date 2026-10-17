"""Real-weight synthetic RMVPE check; never touches personal recordings."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_runtime import configure_runtime_cache, model_directory
configure_runtime_cache()
import json
import time
import numpy as np
import torch
import torch.nn.functional as F
from rvc.lib.predictors.RMVPE import RMVPE0Predictor
from compute_backend import clear_cache, synchronize


def signal(seconds):
    t = np.arange(int(16000 * seconds), dtype=np.float64) / 16000
    frequency = 170 + 30 * np.sin(2 * np.pi * .2 * t) + 5 * np.sin(2 * np.pi * 5 * t)
    phase = np.cumsum(2 * np.pi * frequency / 16000)
    audio = (.2 * np.sin(phase) + .1 * np.sin(phase * 2) + .04 * np.sin(phase * 3)).astype(np.float32)
    for start, end in ((6, 7), (19, 20), (30, 32)):
        audio[int(start * 16000):int(end * 16000)] = 0
    return audio


def old_forward(predictor, audio):
    tensor = torch.from_numpy(audio).unsqueeze(0).to(predictor.device)
    with torch.no_grad():
        mel = predictor.mel_extractor(tensor)
        frames = mel.shape[-1]
        mel = F.pad(mel, (0, (-frames) % 32), mode="reflect")
        hidden = predictor.model(mel)[:, :frames].cpu().numpy()[0]
    return predictor.decode(hidden)


def run(device):
    torch.set_num_threads(2)
    predictor = RMVPE0Predictor(str(Path(model_directory()) / 'predictors' / 'rmvpe.pt'), device=device, max_forward_frames=2048)
    result = {'device': device}
    for seconds in (8, 45):
        audio = signal(seconds)
        clear_cache(device)
        if device.startswith('cuda'):
            torch.cuda.reset_peak_memory_stats(device)
        started = time.monotonic()
        baseline = old_forward(predictor, audio)
        synchronize(device)
        old_seconds = time.monotonic() - started
        old_peak = torch.cuda.max_memory_allocated(device) if device.startswith('cuda') else None
        clear_cache(device)
        if device.startswith('cuda'):
            torch.cuda.reset_peak_memory_stats(device)
        shapes = []
        handle = predictor.model.register_forward_pre_hook(lambda model, inputs: shapes.append(inputs[0].shape[-1]))
        started = time.monotonic()
        actual = predictor.infer_from_audio(audio)
        synchronize(device)
        new_seconds = time.monotonic() - started
        handle.remove()
        new_peak = torch.cuda.max_memory_allocated(device) if device.startswith('cuda') else None
        both = (baseline > 0) & (actual > 0)
        cents = np.abs(1200 * np.log2(actual[both] / baseline[both]))
        boundary = np.zeros(len(actual), dtype=bool)
        core = predictor._window_limits()[2]
        for point in range(core, len(actual), core):
            boundary[max(0, point - 25):point + 25] = True
        at_boundary = boundary[both]
        result[str(seconds)] = {'frames':len(actual), 'forward_frames':shapes,
            'old_seconds':old_seconds, 'new_seconds':new_seconds,
            'old_peak_bytes':old_peak,'new_peak_bytes':new_peak,
            'maximum_f0_hz_difference':float(np.max(np.abs(actual-baseline))),
            'voicing_disagreement_frames':int(np.count_nonzero((actual > 0)!=(baseline > 0))),
            'median_cents_difference':float(np.median(cents)) if len(cents) else None,
            'p95_cents_difference':float(np.quantile(cents,.95)) if len(cents) else None,
            'boundary_p95_cents_difference':float(np.quantile(cents[at_boundary],.95)) if at_boundary.any() else None}
    del predictor
    clear_cache(device)
    return result

if __name__ == '__main__':
    devices = sys.argv[1:] or ['cpu','cuda:0']
    values = [run(device) for device in devices]
    target = Path(__file__).resolve().parents[1]/'build'/'local_reports'/'INFERENCE_RMVPE_REAL_CHECK.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(values,indent=2),encoding='utf-8')
    print(json.dumps(values,indent=2))
