"""Capture small reviewable evidence before owned integration sessions are removed."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import validate_audio_file
from model_manager import file_digest


def main():
    import numpy as np
    import soundfile as sf
    import torch
    from training.storage import validate_checkpoint_backend
    from rvc.infer.safe_index import inspect_index
    torch.set_num_threads(2)
    reports = ROOT/'build'/'local_reports'
    reports.mkdir(parents=True,exist_ok=True)
    log = reports/"TRAINING_FIXED_REAL_SMOKE.log"
    lines = log.read_text(encoding="utf-8").splitlines()
    job = Path(next(line[4:] for line in lines if line.startswith("JOB "))).resolve()
    verification = Path(next(line[13:] for line in lines if line.startswith("VERIFICATION "))).resolve()
    for path,prefix in ((job,"Synthetic compatibility test_"),(verification,"release_verification_")):
        if path.parent != (ROOT/"training_runs").resolve() or not path.name.startswith(prefix):
            raise ValueError("Evidence path is not an owned synthetic test session")
    events = [json.loads(line) for line in (job/"events.jsonl").read_text(encoding="utf-8").splitlines()]
    result = json.loads((job/"result.json").read_text(encoding="utf-8"))
    manifest = json.loads((job/"manifest.json").read_text(encoding="utf-8"))
    dataset = json.loads((job/"dataset.json").read_text(encoding="utf-8"))
    cursor = json.loads(next(line[7:] for line in lines if line.startswith("CURSOR ")))
    protected_before = json.loads((verification/"protected_before.json").read_text(encoding="utf-8"))
    protected_after = json.loads((verification/"protected_after.json").read_text(encoding="utf-8"))
    if protected_before != protected_after or "PROTECTED_FILES_UNCHANGED True" not in lines:
        raise AssertionError("Protected file comparison failed")
    audio = []
    for record in result["models"]:
        for key in ("test_audio_no_index","test_audio"):
            path = Path(record[key])
            validate_audio_file(path)
            data,rate = sf.read(path,dtype="float32",always_2d=True)
            audio.append({"candidate":record["file"],"index_enabled":key=="test_audio",
                          "frames":len(data),"sample_rate":rate,"channels":data.shape[1],
                          "finite":bool(np.isfinite(data).all()),"peak":float(np.max(np.abs(data))),
                          "rms":float(np.sqrt(np.mean(data.astype("float64")**2))),"sha256":file_digest(path)})
    state = torch.load(job/"resume.pth",map_location="cpu",weights_only=True,mmap=True)
    validate_checkpoint_backend(state,"cuda:0")
    checkpoint = {key:state[key] for key in ("epoch","next_batch","step","batch","rng_layout")}
    checkpoint.update(scheduler_g_epoch=state["scheduler_g"]["last_epoch"],
                      scheduler_d_epoch=state["scheduler_d"]["last_epoch"],
                      generator_tensors=len(state["generator"]),discriminator_tensors=len(state["discriminator"]),
                      optimizer_g_states=len(state["optimizer_g"]["state"]),optimizer_d_states=len(state["optimizer_d"]["state"]),
                      cpu_rng_bytes=state["torch_rng"].numel(),gpu_rng_bytes=[value.numel() for value in state["device_rng"]],
                      bytes=(job/"resume.pth").stat().st_size)
    del state
    index = inspect_index(result["index"],expected_dimension=768)
    assert manifest["status"] == "completed" and result["steps"] == 12 and len(audio) == 4
    assert cursor == {"epoch":1,"next_batch":6,"step":6,"batch":1}
    assert checkpoint["epoch"] == 3 and checkpoint["next_batch"] == 0 and checkpoint["step"] == 12
    sources_unchanged = all(file_digest(value["path"]) == value["sha256"] for value in dataset["sources"])
    assert sources_unchanged
    evidence = {"client_date":"2026-10-13","passed":True,"backend":"cuda:0",
                "gpu":torch.cuda.get_device_name(0),"torch":str(torch.__version__),
                "scenario":"FP32 real RVC V2 GAN, two 6-second synthetic recordings, 40 kHz, batch 1, 2 CPU threads, 2 epochs, stop at step 6 and resume, exact FlatL2 and four cover conversions",
                "cancel_checkpoint_cursor":cursor,"final_checkpoint":checkpoint,
                "result_summary":{key:result[key] for key in ("epochs","steps","batch","holdout_mel_l1","index_vectors")},
                "index":{"kind":index.kind,"dimension":index.dimension,"vectors":index.vectors,"sha256":result["index_sha256"]},
                "four_cover_outputs":audio,"sampled_peak_vram_mb":max(value.get("vram_peak_mb",0) for value in events),
                "sampled_peak_worker_rss_mb":max(value.get("rss_mb",0) for value in events),
                "event_span_seconds":max(value["time"] for value in events)-min(value["time"] for value in events),
                "protected_files_unchanged":True,"synthetic_sources_unchanged":sources_unchanged,
                "protected_sha256":protected_after,"asset_verification":"Full real schema, CRC and pinned publisher SHA-256; only temporary integrity manifest written",
                "cuda_exact_fixture":json.loads((reports/"TRAINING_FIXED_CUDA_CHECKPOINT_EXACT.json").read_text(encoding="utf-8")),
                "readonly_findings_fixed":["Resume could drop incompatible GPU RNG on backend migration; explicit backend/runtime/count/index guard added.","Duplicate parent controller could clear session markers before child guard; parent controller lock and active-worker startup guard added.","Official RMVPE frozen FP16 BN counter +Inf was rejected by generic finiteness; root narrowed exception to exact published RMVPE hash and scalar positive-infinite num_batches_tracked counters."],
                "limitations":["Small synthetic audio validates execution and formats, not voice quality.","Real GAN bitwise reproducibility across CUDA kernels is not asserted; separate small deterministic CUDA checkpoint fixture is bitwise equal.","No physical AMD/Intel GPU, packaged clean Windows, NVDA/JAWS or long-recording quality claim."],
                "temporary_sessions":[str(job),str(verification)],"temporary_sessions_cleaned":False}
    target = reports/"TRAINING_FIXED_REAL_CHECK.json"
    target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":True,"steps":12,"outputs":len(audio),"index_vectors":index.vectors,
                      "peak_vram_mb":evidence["sampled_peak_vram_mb"],"peak_rss_mb":evidence["sampled_peak_worker_rss_mb"],
                      "event_span_seconds":evidence["event_span_seconds"],"evidence":str(target)}))


if __name__ == "__main__":
    main()
