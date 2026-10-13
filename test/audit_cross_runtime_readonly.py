"""Historical cross-component reproductions, now reporting fixed rejections.

Uses owned synthetic files/processes only. Standard regression tests are the
maintained pass/fail contract; no real model or user audio is modified here.
"""
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def logging_recursion(folder):
    from startup_diagnostics import LogStream
    root = logging.getLogger()
    previous_handlers,previous_level = list(root.handlers),root.level
    previous_stderr = sys.stderr
    handler = RotatingFileHandler(Path(folder)/"shared.log",maxBytes=128,backupCount=1,encoding="utf-8")
    held = (Path(folder)/"shared.log").open("a",encoding="utf-8")
    caught = None
    try:
        root.handlers = [handler]
        root.setLevel(logging.INFO)
        sys.stderr = LogStream(logging.ERROR)
        try:
            logging.getLogger("motor").error("x"*256)
        except BaseException as error:
            caught = type(error).__name__
    finally:
        sys.stderr = previous_stderr
        held.close()
        handler.close()
        root.handlers,root.level = previous_handlers,previous_level
    return {"windows":os.name=="nt","exception":caught}


def callback_lifecycle(folder):
    from audio_service import NativeAudioSession
    script = Path(folder)/"hang_fixture.py"
    script.write_text("import time\ntime.sleep(60)\n",encoding="utf-8")
    session = NativeAudioSession(command=[sys.executable,"-u",str(script)],directory=folder)
    clock = iter((0.,6.))
    try:
        with patch("audio_service.time.monotonic",side_effect=lambda:next(clock,6.)):
            try:
                session.execute("hang",{},progress=Mock(side_effect=ValueError("synthetic callback failure")))
            except ValueError:
                return {"worker_live_after_callback_error":session.process.poll() is None,
                        "session_closed_after_callback_error":session._closed}
    finally:
        session.close()


def fallback_quality(folder):
    import numpy as np
    import soundfile as sf
    import types
    import ui_cover
    source = Path(folder)/"source.wav"
    model = Path(folder)/"synthetic.pth"
    sf.write(source,np.ones(1600,dtype="float32")*.1,16000)
    model.write_bytes(b"synthetic model never loaded")
    seen = {}
    class FakeConverter:
        def __init__(self,**kwargs): pass
        def convert_audio(self,**kwargs):
            seen.update(kwargs)
            sf.write(kwargs["audio_output_path"],np.ones(1600,dtype="float32")*.1,16000)
        def cleanup_model(self): pass
    module = types.ModuleType("rvc.infer.infer")
    module.VoiceConverter = FakeConverter
    panel = SimpleNamespace(audio_session_factory=None,is_cancelled=False,app_dir=folder,
                            input_audio_path=str(source),output_folder_path=folder,
                            models={"voice":{"pth":str(model),"index":""}},
                            LogMessage=Mock(),UpdateStatus=Mock())
    settings = {"device":"cpu","pitch":0,"f0_method":"rmvpe","index_rate":0.,
                "quality_policy":{"input_highpass_80hz":False,"pipeline_highpass_48hz":False,"smooth_pitch":False}}
    with patch.dict(sys.modules,{"rvc.infer.infer":module}),patch("hardware.configure_runtime"), \
         patch.object(ui_cover,"ensure_rvc_prerequisites"),patch.object(ui_cover,"post_ui"):
        ui_cover.CoverPanel._run_inference_queue(panel,["voice"],settings)
    from dataclasses import asdict,is_dataclass
    received = seen.get("quality_policy")
    return {"requested_policy":settings["quality_policy"],
            "converter_received_policy":asdict(received) if is_dataclass(received) else received}


def stale_full_integrity_save(folder):
    from model_manager import ModelManager
    first,second = ModelManager(folder),ModelManager(folder)
    target = str(Path(folder)/"integrity.json")
    first.manifest_path = second.manifest_path = target
    first.records = {"shared":{"files":{},"schema_version":2,"tag":"new"}}
    second.records = {"shared":{"files":{},"schema_version":2,"tag":"old"},"other":{"files":{},"schema_version":2}}
    first.save("shared")
    rejected = False
    try:
        second.save()
    except ValueError:
        rejected = True
    return {"stale_save_rejected":rejected,
            "full_save_stored_value":json.loads(Path(target).read_text())["models"]["shared"]["tag"]}


def separator_metadata_bounds(folder):
    from model_manager import validate_metadata
    config = {"audio":{"chunk_size":4096,"sample_rate":44100,"num_channels":2},
              "model":{"dim":64,"depth":1,"heads":1,"stft_n_fft":2048,"stft_hop_length":512},
              "training":{"instruments":["vocals"],"target_instrument":"vocals"},
              "inference":{"batch_size":1,"num_overlap":2}}
    result = {}
    for key in ("num_stems","linear_transformer_depth"):
        value = {**config,"model":{**config["model"],key:1_000_000}}
        try:
            validate_metadata(value,"config.yaml")
            result[key+"_million_accepted"] = True
        except ValueError:
            result[key+"_million_accepted"] = False
    return result


def main():
    results = {}
    for name,case in (("logging_rollover",logging_recursion),("callback_lifecycle",callback_lifecycle),
                      ("fallback_quality",fallback_quality),("stale_integrity_save",stale_full_integrity_save),
                      ("separator_metadata_bounds",separator_metadata_bounds)):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            results[name] = case(folder)
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__ == "__main__": main()
