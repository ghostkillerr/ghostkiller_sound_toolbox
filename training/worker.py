"""Isolated training entry point, also dispatched by the packaged EXE."""
import argparse
from contextlib import ExitStack
import gc
import json
import os
from pathlib import Path
import sys
import time
import traceback


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("job",nargs="?")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--probe",type=Path,help="Yerel CPU backward tanısını JSON dosyasına yaz")
    args = parser.parse_args(argv)
    if args.probe is not None:
        if args.job is not None or args.resume:
            parser.error("--probe bir eğitim oturumu veya --resume ile kullanılamaz.")
        return _run_probe(args.probe)
    if args.job is None:
        parser.error("Eğitim oturum klasörü gerekli.")
    job = Path(args.job).resolve()
    if sys.stdout is None:
        sys.stdout = (job/"worker.log").open("a",encoding="utf-8",buffering=1)
    if sys.stderr is None:
        sys.stderr = sys.stdout
    from registry_store import registry_lock
    with ExitStack() as stack:
        try:
            stack.enter_context(registry_lock(job/"worker.guard",timeout=.1))
        except TimeoutError as error:
            # A rejected second worker must not overwrite the active manifest or
            # write cancellation/checkpoint state belonging to the first worker.
            print("Eğitim oturumu başka bir alt işlemde kullanılıyor: "+str(error),file=sys.stderr,flush=True)
            return 1
        return _run_worker(job,args.resume)


def _run_probe(target):
    """Packaged worker dispatch check: no model, data session or download."""
    try:
        target = Path(target).resolve()
        if target.exists() and not target.is_file():
            raise ValueError("Tanı çıktı yolu bir JSON dosyası olmalı.")
        import torch
        torch.set_num_threads(1)
        model = torch.nn.Linear(4,2,device="cpu",dtype=torch.float32)
        source = torch.ones(2,4,device="cpu",dtype=torch.float32,requires_grad=True)
        loss = model(source).square().mean()
        loss.backward()
        gradients = [source.grad,*[parameter.grad for parameter in model.parameters()]]
        if not torch.isfinite(loss).item() or any(value is None or not torch.isfinite(value).all().item() for value in gradients):
            raise RuntimeError("Yerel CPU forward/backward tanısı geçersiz değer üretti.")
        from app_settings import write_json_atomic
        write_json_atomic(str(target),{"ok":True,"pid":os.getpid(),"device":"cpu",
                                      "torch_version":str(torch.__version__),"torch":str(torch.__version__),
                                      "forward_backward":True})
        return 0
    except Exception as error:
        message = f"Eğitim worker tanısı başarısız: {type(error).__name__}: {str(error) or 'Açıklamasız hata'}"
        if sys.stderr is not None:
            print(message,file=sys.stderr,flush=True)
        else:
            import logging
            logging.getLogger(__name__).error(message)
        return 1


def _run_worker(job, resume=False):
    from app_runtime import configure_runtime_cache, app_directory
    configure_runtime_cache()
    os.environ["PATH"] = str(Path(app_directory())/"tools"/"ffmpeg")+os.pathsep+os.environ.get("PATH","")
    from training.storage import read_manifest,update_manifest,cleanup_incomplete_artifacts
    from training.config import TrainingOptions, BACKEND_COMMIT, FORMAT_VERSION, TRAINER_REVISION
    from training.dataset import check_cancel
    resources = None
    from training.heartbeat import WorkerHeartbeat
    heartbeat = WorkerHeartbeat(job).start()
    last_progress = {}
    def emit(stage,**values):
        heartbeat.progress(stage)
        values.update(stage=stage,time=time.time())
        with (job/"events.jsonl").open("a",encoding="utf-8") as stream:
            stream.write(json.dumps(values,ensure_ascii=False)+"\n")
        now = time.monotonic()
        if stage not in ("prepare","features","pitch","index") or now-last_progress.get(stage,0) >= .25 or values.get("percent")==100:
            print("GHOST_TRAIN "+json.dumps(values,ensure_ascii=False),flush=True)
            last_progress[stage] = now
        if resources is not None and stage != "resources":
            resources.sample()
    try:
        partials = cleanup_incomplete_artifacts(job)
        if partials:
            emit("recovery",message=f"Önceki kesintiden kalan {len(partials)} yarım eğitim dosyası temizlendi; atomik devam noktası korundu.")
        manifest = read_manifest(job)
        if (manifest.get("backend_commit") != BACKEND_COMMIT or manifest.get("format_version") != FORMAT_VERSION
                or manifest.get("trainer_revision", "ghostkiller-rvc-v2-fp32-1") != TRAINER_REVISION):
            raise ValueError("Eğitim oturumu backend sürümüyle uyumlu değil.")
        options = TrainingOptions.from_dict(manifest["options"])
        device = manifest["device"]
        from hardware import ensure_training_backend
        ensure_training_backend(device)
        import torch
        torch.set_num_threads(options.cpu_threads)
        from compute_backend import backend_module,clear_cache
        api = backend_module(device)
        if api is not None and not api.is_available():
            raise RuntimeError("Ayarlar'da seçilen GPU eğitim alt işleminde kullanılamıyor; CPU'ya sessiz geçiş yapılmadı.")
        from training.resources import ResourceMonitor
        resources = ResourceMonitor(device,emit)
        from training.dataset import prepare,extract
        update_manifest(job,status="running",error="",torch_version=str(torch.__version__),python_version=sys.version)
        if not resume or not (job/"train.txt").exists() or not (job/"holdout.txt").exists():
            options.validate()
            from training.analysis import analyze_sources, report_text
            from app_settings import write_json_atomic
            report = analyze_sources(options.sources, options.sample_rate,
                                     lambda: (job/"cancel.request").exists(), emit)
            write_json_atomic(str(job/"quality_report.json"), report)
            (job/"quality_report.txt").write_text(report_text(report), encoding="utf-8")
            for record in report["sources"]:
                for warning in record["warnings"]:
                    emit("quality", message=f"{Path(record['path']).name}: {warning}")
            prepare(job,options,emit)
            resources.sample(True)
            extract(job,options,device,emit)
            resources.sample(True)
            gc.collect()
            clear_cache(device)
        if (job/"pitch_report.json").exists():
            emit("pitch_summary",report=json.loads((job/"pitch_report.json").read_text(encoding="utf-8")),
                 message="Eğitim ve değerlendirme perde kapsamı hazır.")
        dataset = json.loads((job/"dataset.json").read_text(encoding="utf-8"))
        # Detect changed training artifacts before resume instead of training on mixed data.
        from model_manager import file_digest
        artifacts = {str(p):file_digest(p,lambda:(job/"cancel.request").exists()) for piece in dataset["pieces"]
                     for p in (piece["audio"],piece["features"],piece["pitch"],piece["pitchf"])}
        for filename in ("dataset.json", "train.txt", "holdout.txt"):
            path = job/filename
            artifacts[str(path)] = file_digest(path,lambda:(job/"cancel.request").exists())
        previous = manifest.get("dataset_artifacts")
        if resume and previous and artifacts != previous:
            raise ValueError("Hazırlanmış eğitim verisi değişmiş; devam işlemi durduruldu.")
        update_manifest(job,dataset_artifacts=artifacts)
        from training.engine import run_training
        summary = run_training(job,options,device,manifest["model_root"],emit,
                               resume=resume and (job/"resume.pth").exists())
        gc.collect()
        clear_cache(device)
        from training.index import build_index
        index,count = build_index(job,dataset,options.cpu_threads,emit)
        # Test actual application inference before any registry write.
        check_cancel(job)
        from rvc.infer.infer import VoiceConverter
        from app_runtime import validate_audio_file
        converter = VoiceConverter(device=device,allow_model_download=False)
        holdout = next(p["audio"] for p in dataset["pieces"] if p["split"]=="holdout")
        models = []
        try:
            for candidate in ("latest.pth","best_validation.pth"):
                check_cancel(job)
                output = str(job/f"test_{Path(candidate).stem}.wav")
                no_index = str(job/f"test_{Path(candidate).stem}_no_index.wav")
                for target,ratio in ((no_index,0.),(output,.75)):
                    emit("smoke",message=f"AI Cover uyumluluk testi: {candidate}; index oranı {ratio:.2f}")
                    converter.convert_audio(holdout,target,str(job/candidate),index if ratio else "",
                                            f0_method=options.f0_method,index_rate=ratio,clean_audio=False)
                    validate_audio_file(target)
                    check_cancel(job)
                models.append({"file":candidate,"pth":str(job/candidate),"sha256":file_digest(job/candidate),
                               "smoke_passed":True,"test_audio":output,"test_audio_no_index":no_index,
                               "test_index_rate":.75})
        finally:
            converter.cleanup_model()
        from app_settings import write_json_atomic
        result = {**summary,"models":models,"index":index,"index_sha256":file_digest(index),"index_vectors":count}
        write_json_atomic(str(job/"result.json"),result)
        update_manifest(job,status="completed")
        resources.sample(True)
        emit("completed",message="Eğitim tamamlandı; iki aday model AI Cover uyumluluk testinden geçti.")
        return 0
    except InterruptedError as error:
        update_manifest(job,status="cancelled",error=str(error))
        emit("cancelled",message=str(error))
        return 2
    except Exception as error:
        message = str(error).strip() or f"{type(error).__name__}: eğitim alt işleminde açıklamasız hata."
        update_manifest(job,status="failed",error=message)
        emit("failed",message=message)
        traceback.print_exc()
        return 1
    finally:
        heartbeat.stop()


if __name__=="__main__":
    sys.exit(main())
