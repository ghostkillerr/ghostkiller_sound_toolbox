"""Read-only release-audit reproductions; only temporary fixtures are written.

Run from the repository root: python test/audit_release_checks.py
These checks report existing behavior, rather than changing application code.
"""
from pathlib import Path
import json
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_runtime import configure_runtime_cache
configure_runtime_cache()

import numpy as np
import torch
import onnxruntime as ort
from app_runtime import JOB_LOCK, safe_filename
from rvc.configs.config import Config
from rvc.lib.predictors.RMVPE import RMVPE0Predictor
from training.config import TrainingOptions
from training.service import TrainingProcess
from model_manager import validate_weight_schema
import ui_cover
import ui_separator


class Harness:
    def __init__(self, root):
        self.output_directory = str(root)
        self.current_input_file = str(root / "input.wav")
        Path(self.current_input_file).write_bytes(b"fixture")
        self.is_cancelled = False
        self.statuses = []
    def LogMessage(self, message):
        pass
    def UpdateStatus(self, message, percent=None):
        self.statuses.append(message)
    def EnableUI(self, enabled):
        pass
    def IsBeingDeleted(self):
        return False


def main():
    torch.set_num_threads(2)
    results = {}
    try:
        Config(device="xpu:0")
    except ValueError as error:
        results["xpu_rejected"] = str(error)

    results["onnx_runtime"] = {"version": ort.__version__, "providers": ort.get_available_providers()}

    # Third-party MDXC loader calls sys.exit(1) on model/OOM RuntimeError.
    class ExitingSeparator:
        def __init__(self, **kwargs):
            pass
        def load_model(self, **kwargs):
            raise SystemExit(1)
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        job = Harness(Path(directory))
        job.model_dir = directory
        job.RunSeparatorCommand = lambda *args: ui_separator.SeparatorPanel.RunSeparatorCommand(job, *args)
        JOB_LOCK.acquire()
        with patch.object(ui_separator, "Separator", ExitingSeparator), patch.object(ui_separator, "post_ui"), patch.object(ui_separator.wx, "CallAfter", side_effect=lambda fn, *args: fn(*args)):
            try:
                ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            except SystemExit as error:
                results["separator_system_exit"] = {"exit": error.code, "final_status": job.statuses[-1], "lock_released": not JOB_LOCK.locked()}

    # Two independently opened application instances can overwrite stale registries.
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        base = {"base": {"pth": "base.pth", "index": ""}}
        ui_cover.save_models(directory, base)
        first, second = ui_cover.load_models(directory), ui_cover.load_models(directory)
        second["second"] = {"pth": "second.pth", "index": ""}
        ui_cover.save_models(directory, second)
        first["first"] = {"pth": "first.pth", "index": ""}
        ui_cover.save_models(directory, first)
        results["stale_registry_lost_update"] = {"remaining": list(ui_cover.load_models(directory)), "lost": "second"}

    # The overlap validator accepts a zero sample step after rounding.
    options = TrainingOptions("audit", ("unused.wav",), segment_seconds=1., overlap_seconds=.999999)
    options.validate(False)
    results["rounded_segment_step"] = round(options.segment_seconds*options.sample_rate)-round(options.overlap_seconds*options.sample_rate)

    # Group-prefix validation accepts NaN and arbitrary tensor shapes for separators.
    weights = {prefix+"bad": torch.tensor([float("nan")]) for prefix in ("layers.", "band_split.", "mask_estimators.")}
    validate_weight_schema(weights, "example.ckpt")
    results["separator_invalid_weights_pass_schema"] = True

    # A hard worker failure with error='' in the manifest has no actionable message.
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        job = Path(directory)
        (job/"manifest.json").write_text(json.dumps({"options": TrainingOptions("audit", ("unused.wav",)).to_dict(), "error": ""}), encoding="utf-8")
        class FailedProcess:
            returncode = 1
            def poll(self):
                return 1
        with patch("training.service.subprocess.Popen", return_value=FailedProcess()):
            try:
                TrainingProcess().run(directory, lambda event: None)
            except RuntimeError as error:
                results["worker_failure_message"] = str(error)

    # RMVPE processes up to 320 seconds in a single U-Net forward call.
    predictor = object.__new__(RMVPE0Predictor)
    shapes = []
    def fake_network(mel):
        shapes.append(mel.shape[-1])
        return torch.zeros(1, mel.shape[-1], 360)
    predictor.model = fake_network
    predictor.mel2hidden(torch.zeros(1, 128, 33000))
    results["rmvpe_forward_frame_counts"] = shapes

    # Filename component limits can fail even when Windows long paths are enabled.
    results["separator_output_component_length"] = len("a"*240+"_Ghostkiller_1_Ayrilmis_Vokal.flac")
    results["cover_output_component_length"] = len(safe_filename("a"*240)+"_"+safe_filename("b"*240)+".wav")

    import faiss
    from rvc.infer.pipeline import Pipeline
    vectors = np.array([[10.,0.],[1.,1.]], dtype="float32")
    index = faiss.IndexFlatIP(2)
    index.add(vectors)
    pipeline = object.__new__(Pipeline)
    pipeline.device = "cpu"
    retrieved = pipeline._retrieve_speaker_embeddings(torch.tensor([[[1.,0.]]]), index, vectors, 1.)
    results["inner_product_index_accepted_with_l2_weighting"] = {"scores":index.search(np.array([[1.,0.]],dtype="float32"),2)[0].tolist(),"retrieved":retrieved.numpy().tolist()}

    # Exercise the actual trainer with a virtual clock and small substituted nets.
    # Every epoch fits in one batch, so the periodic save guard skips every batch.
    import training.engine as engine
    clock = [0.]
    saves = []
    dataset = [torch.ones(1) for _ in range(3)]
    def step(*args):
        clock[0] += 61.
        args[3].step()
        args[4].step()
        return {"loss_g": 1., "loss_d": 1., "loss_mel": 1., "loss_kl": 1.}
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        options = TrainingOptions("audit", ("unused.wav",), epochs=10, save_every=10, batch_size=3)
        with patch.object(engine, "TextAudioLoaderMultiNSFsid", return_value=dataset), \
             patch.object(engine, "TextAudioCollateMultiNSFsid", return_value=lambda batch: [torch.ones(1)]), \
             patch.object(engine, "model_pair", side_effect=lambda *a: (torch.nn.Linear(1,1), torch.nn.Linear(1,1))), \
             patch.object(engine, "load_pretrained"), patch.object(engine, "train_step", side_effect=step), \
             patch.object(engine, "evaluate", return_value=1.), patch.object(engine, "export_model"), \
             patch.object(engine, "update_manifest"), patch.object(engine, "ResourceMonitor"), \
             patch.object(engine, "atomic_torch_save", side_effect=lambda value, path: saves.append({"step":value["step"],"virtual_seconds":clock[0]})), \
             patch.object(engine.time, "monotonic", side_effect=lambda: clock[0]):
            engine.run_training(directory, options, "cpu", directory, lambda *a, **k: None)
    results["single_batch_epoch_checkpoint_times"] = saves
    if "--save-evidence" in sys.argv:
        (ROOT/"docs"/"YAYIN_DENETIMI_HATA_KANITLARI.json").write_text(json.dumps(results, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
