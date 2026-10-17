"""Short synthetic local-model compatibility test; never downloads models.

python test/audit_separation_models.py --devices cpu cuda:0
Writes only temporary sounds and a private diagnostic JSON in build/local_reports/.
"""
from pathlib import Path
import argparse
import gc
import json
import logging
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_runtime import configure_runtime_cache, validate_audio_file
configure_runtime_cache()
import numpy as np
import soundfile as sf
import torch
from model_manager import ModelManager
from separation_steps import SEPARATION_STEPS
from separator_backend import LocalSeparator
from ui_separator import setup_ffmpeg_paths
from training.resources import memory_status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--devices", nargs="+", default=["cpu"])
    args = parser.parse_args()
    setup_ffmpeg_paths(str(ROOT))
    torch.set_num_threads(2)
    manager = ModelManager()
    results = []
    for model, *_ in SEPARATION_STEPS:
        status = manager.status(model)
        if status != "Hazır":
            results.append({"model":model, "status":"skipped", "reason":status})
            continue
        for device in args.devices:
            separator = None
            record = {"model":model, "device":device}
            print("CHECK "+json.dumps(record), flush=True)
            with tempfile.TemporaryDirectory(prefix="audit_sep_", dir=ROOT) as folder:
                directory = Path(folder)
                t = np.arange(44100*4)/44100
                mono = .15*np.sin(2*np.pi*180*t)+.05*np.sin(2*np.pi*720*t)
                source = directory/"synthetic_mix.wav"
                sf.write(source,np.stack([mono,mono],axis=1),44100)
                output = directory/"output"
                output.mkdir()
                if device.startswith("cuda"):
                    torch.cuda.set_device(device)
                    torch.cuda.empty_cache()
                    torch.cuda.reset_peak_memory_stats(device)
                started = time.monotonic()
                try:
                    separator = LocalSeparator(model_file_dir=manager.root, device=device,
                                               output_dir=str(output), output_format="FLAC",
                                               use_autocast=False, log_level=logging.ERROR)
                    separator.load_model(model_filename=model)
                    record["load_seconds"] = round(time.monotonic()-started,3)
                    inference_started = time.monotonic()
                    paths = separator.separate(str(source))
                    outputs = []
                    for name in paths:
                        path = Path(name) if Path(name).is_absolute() else output/name
                        validate_audio_file(path)
                        info = sf.info(path)
                        outputs.append({"name":path.name,"seconds":round(info.duration,4),
                                        "sample_rate":info.samplerate,"channels":info.channels})
                    record.update(status="passed",inference_seconds=round(time.monotonic()-inference_started,3),outputs=outputs)
                except (Exception, SystemExit) as error:
                    record.update(status="failed",error_type=type(error).__name__,error=str(error))
                finally:
                    record["total_seconds"] = round(time.monotonic()-started,3)
                    record.update(memory_status())
                    if device.startswith("cuda"):
                        record["vram_peak_mib"] = round(torch.cuda.max_memory_allocated(device)/1024**2,2)
                    separator = None
                    gc.collect()
                    if device.startswith("cuda"):
                        torch.cuda.empty_cache()
                results.append(record)
                print(json.dumps(record,ensure_ascii=False),flush=True)
    evidence = {"date":"2026-10-13","synthetic_audio_seconds":4,"cpu_threads":2,
                "torch":str(torch.__version__),"results":results,
                "note":"Compatibility test; no perceptual quality score. No downloads or personal audio."}
    reports = ROOT/'build'/'local_reports'
    reports.mkdir(parents=True,exist_ok=True)
    (reports/"YAYIN_DENETIMI_AYRISTIRMA_KANITLARI.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
