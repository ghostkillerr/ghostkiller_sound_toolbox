"""GUI-independent subprocess controller and atomic, validated model registration."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import shutil
import uuid
import time
from app_runtime import data_directory, app_directory, safe_filename
from app_settings import write_json_atomic
from audio_export import selected_output_format, selected_output_channels
from training.config import TrainingOptions, BACKEND_COMMIT, FORMAT_VERSION, TRAINER_REVISION
from training.storage import read_manifest, update_manifest,rng_layout
from registry_store import registry_lock, validate_models
from training.cleanup import training_job_size, delete_training_job


def create_job(options, settings, parent_job=None):
    options.validate()
    device = settings.prepare_job(["contentvec", "rmvpe"] if options.f0_method=="rmvpe" else ["contentvec"])
    from hardware import ensure_training_backend
    ensure_training_backend(device)
    settings.manager.require_ready([f"training_v2_{options.sample_rate//1000}k"])
    root = Path(data_directory()) / 'training_runs'
    with registry_lock(root / 'lifecycle.guard'):
        return _create_job(root, options, settings, device, parent_job)


def _create_job(root, options, settings, device, parent_job):
    job = root/(safe_filename(options.name)+"_"+uuid.uuid4().hex[:12])
    job.mkdir()
    write_json_atomic(str(job/"manifest.json"),{
        "format_version":FORMAT_VERSION,"backend_commit":BACKEND_COMMIT,
        "trainer_revision":TRAINER_REVISION,
        "options":options.to_dict(),"device":device,"model_root":settings.manager.root,
        "output_format":selected_output_format(settings),
        "output_channels":selected_output_channels(settings),
        "rng_layout":rng_layout(device),
        "status":"created","asset_records":{key:settings.manager.records.get(key,{}) for key in
            ("contentvec","rmvpe",f"training_v2_{options.sample_rate//1000}k")},
    })
    if parent_job:
        try:
            with registry_lock(Path(parent_job)/'worker.guard', timeout=.1):
                parent = read_manifest(parent_job)
                if parent.get('status') == 'deleting':
                    raise ValueError('Başlangıç eğitim oturumu temizleniyor.')
                previous = TrainingOptions.from_dict(parent['options'])
                if previous.sample_rate != options.sample_rate or parent.get('trainer_revision',TRAINER_REVISION)!=TRAINER_REVISION:
                    raise ValueError('Başlangıç eğitiminin mimarisi ve örnekleme hızı yeni eğitimle aynı olmalı.')
                checkpoint = Path(parent_job).resolve()/'resume.pth'
                from model_manager import file_digest
                update_manifest(job, initial_from={'checkpoint':str(checkpoint), 'sha256':file_digest(checkpoint),
                                                   'session':str(Path(parent_job).resolve())})
        except BaseException:
            update_manifest(job, status='failed', error='Başlangıç eğitim kaydı doğrulanamadı.')
            raise
    return str(job)


def validate_resume(job, settings):
    with registry_lock(Path(job)/'controller.guard', timeout=.1), registry_lock(Path(job)/'worker.guard', timeout=.1):
        return _validate_resume(job, settings)


def _validate_resume(job, settings):
    manifest = read_manifest(job)
    if manifest.get('status') == 'deleting':
        raise ValueError('Bu eğitim oturumunun teknik dosyaları temizleniyor.')
    if manifest.get("format_version") != FORMAT_VERSION or manifest.get("backend_commit") != BACKEND_COMMIT:
        raise ValueError("Bu eğitim oturumu farklı bir backend sürümüyle oluşturulmuş.")
    if manifest.get("trainer_revision", "ghostkiller-rvc-v2-fp32-1") != TRAINER_REVISION:
        raise ValueError("Eğitim döngüsü sürümü değişmiş; bu oturuma aynen devam edilemez.")
    options = TrainingOptions.from_dict(manifest["options"])
    device = settings.prepare_job(["contentvec","rmvpe"] if options.f0_method=="rmvpe" else ["contentvec"])
    from hardware import ensure_training_backend
    ensure_training_backend(device)
    previous_layout = manifest.get("rng_layout")
    if previous_layout is not None:
        if previous_layout != rng_layout(device):
            raise ValueError("Eğitim oturumunun donanım backend'i veya GPU/RNG düzeni değişmiş; aynı düzeni seçin veya yeni eğitim oturumu başlatın.")
    elif str(manifest.get("device","cpu")) != str(device):
        raise ValueError("Eski eğitim oturumunda donanım/RNG düzeni tam kayıtlı değil; farklı cihazda aynen devam desteklenmiyor.")
    settings.manager.require_ready([f"training_v2_{options.sample_rate//1000}k"])
    # Freeze feature/pretrain identities for exact resume; changed assets need a new job.
    for key, record in manifest["asset_records"].items():
        current = settings.manager.records.get(key,{})
        old_hashes = {k:v["sha256"] for k,v in record.get("files",{}).items()}
        new_hashes = {k:v["sha256"] for k,v in current.get("files",{}).items()}
        if old_hashes != new_hashes:
            raise ValueError("Model yardımcı dosyaları değişmiş; bu eğitime aynen devam edilemez.")
    update_manifest(job,device=device,model_root=settings.manager.root,
                    output_format=selected_output_format(settings),output_channels=selected_output_channels(settings))
    return options


class TrainingProcess:
    def __init__(self):
        self.process = None
        self.job = None
        self._cancel_lock = threading.Lock()
        self._cancel_requested = False
        self._force_requested = threading.Event()
        self._force_stopped = False
        self._cancel_time = None
        self._group = None

    def cancel(self):
        with self._cancel_lock:
            self._cancel_requested = True
            if self._cancel_time is None:
                self._cancel_time = time.monotonic()
            if self.job:
                (Path(self.job)/"cancel.request").touch()

    def force_stop(self):
        """Explicit user recovery; never claim the interrupted step was saved."""
        self.cancel()
        self._force_requested.set()

    @property
    def cancel_requested(self):
        return self._cancel_requested

    def _stop_process(self):
        process = self.process
        if process is None or process.poll() is not None:
            return
        self._group.terminate(timeout=3)

    def _error_detail(self, code):
        try:
            manifest = read_manifest(self.job)
        except (OSError,ValueError):
            manifest = {}
        message = str(manifest.get("error") or "").strip() or "Eğitim alt işlemi beklenmedik biçimde kapandı."
        stage = manifest.get("status", "başlangıç")
        try:
            stage = json.loads((Path(self.job)/"heartbeat.json").read_text(encoding="utf-8")).get("stage") or stage
        except (OSError,ValueError):
            pass
        detail = f"{message}\nÇıkış kodu: {code} (0x{code & 0xffffffff:08X}); son aşama: {stage}."
        root = Path(self.job).resolve()
        path = root/"worker.log"
        # Windowed native workers may have None stdout/stderr. Their early
        # diagnostics therefore use separate per-process files in this session.
        runtime_logs = []
        for pattern in ("worker_runtime_*.log","runtime_*.log"):
            for candidate in root.glob(pattern):
                try:
                    if not candidate.is_symlink() and candidate.resolve().parent == root and candidate.is_file():
                        runtime_logs.append((candidate.stat().st_mtime_ns,candidate))
                except OSError:
                    pass
        runtime_logs = [value[1] for value in sorted(set(runtime_logs),reverse=True)[:2]]
        for log_path in [path,*runtime_logs]:
            try:
                with log_path.open("rb") as stream:
                    stream.seek(max(0,log_path.stat().st_size-4096))
                    tail = stream.read().decode("utf-8",errors="replace").strip()
                if tail:
                    detail += f"\nGünlüğün sonu ({log_path.name}):\n"+tail
            except OSError:
                pass
        return detail+f"\nTam günlük klasörü: {root}; worker.log. Son sağlam devam kontrol noktası korundu."

    def run(self, job, callback, resume=False):
        from registry_store import registry_lock
        # Keep parent controllers from clearing each other's markers while a
        # worker starts or runs. The worker's own guard remains independent.
        with registry_lock(Path(job)/"controller.guard",timeout=.1):
            return self._run(job,callback,resume)

    def _run(self, job, callback, resume=False):
        from registry_store import registry_lock
        events = Path(job)/"events.jsonl"
        heartbeat = Path(job)/"heartbeat.json"
        with registry_lock(Path(job)/"worker.guard",timeout=.1):
            if read_manifest(job).get('status') == 'deleting':
                raise ValueError('Bu eğitim oturumunun teknik dosyaları temizleniyor.')
            with self._cancel_lock:
                self.job = job
                marker = Path(job)/"cancel.request"
                if self._cancel_requested:
                    marker.touch()
                elif marker.exists():
                    marker.unlink()
            heartbeat.unlink(missing_ok=True)
            offset = events.stat().st_size if events.exists() else 0
        command = [sys.executable, "--training-worker", job]
        if not getattr(sys,"frozen",False):
            command = [sys.executable,"-u","-m","training.worker",job]
        if resume:
            command.append("--resume")
        options = TrainingOptions.from_dict(read_manifest(job)["options"])
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8",OMP_NUM_THREADS=str(options.cpu_threads),
                   MKL_NUM_THREADS=str(options.cpu_threads),OPENBLAS_NUM_THREADS=str(options.cpu_threads))
        creationflags = subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
        started = last_progress = time.monotonic()
        unresponsive = False
        # Durable event-file IPC also works with PyInstaller's windowed EXE,
        # where sys.stdout can be None. No pipe backpressure or huge output capture.
        from native_process import NativeProcessGroup
        with NativeProcessGroup() as self._group, (Path(job)/"worker.log").open("a",encoding="utf-8") as log:
            self.process = self._group.spawn(command,cwd=app_directory(),env=env,stdout=log,
                                           stderr=subprocess.STDOUT,creationflags=creationflags,
                                           **({"start_new_session":True} if os.name != "nt" else {}))
            def read_events():
                nonlocal offset,last_progress
                if not events.exists():
                    return
                latest = {}
                pending = []
                with events.open("rb") as stream:
                    stream.seek(offset)
                    while True:
                        position = stream.tell()
                        line = stream.readline()
                        if not line or not line.endswith(b"\n"):
                            offset = position
                            break
                        value = json.loads(line.decode("utf-8"))
                        if value["stage"] != "resources":
                            last_progress = time.monotonic()
                        if value["stage"] in ("analysis","prepare","features","pitch","index","resources"):
                            latest[value["stage"]] = value
                        else:
                            pending.append(value)
                for value in sorted(pending+list(latest.values()), key=lambda value: value.get("time", 0)):
                    callback(value)
            try:
                while self.process.poll() is None:
                    if self._force_requested.is_set():
                        self._force_stopped = True
                        self._stop_process()
                        break
                    read_events()
                    now = time.monotonic()
                    stale = now-started > 30
                    stage = "başlangıç"
                    try:
                        signal = json.loads(heartbeat.read_text(encoding="utf-8"))
                        stale = time.time()-signal["time"] > 15
                        stage = signal.get("stage",stage)
                    except (OSError,ValueError,KeyError,TypeError):
                        pass
                    pending_cancel = self._cancel_time is not None and now-self._cancel_time > 30
                    stalled = stale or now-last_progress > 600 or pending_cancel
                    if stalled and not unresponsive:
                        if stale:
                            reason = "worker_unresponsive"
                            message = f"Eğitim alt işleminden güncel yanıt alınamıyor ({stage})."
                        elif pending_cancel:
                            reason = "cancel_pending"
                            message = f"Eğitim alt işlemi çalışıyor; durdurma isteği mevcut işlem tamamlanınca uygulanacak ({stage})."
                        else:
                            reason = "long_operation"
                            message = f"Eğitim alt işlemi çalışıyor; 10 dakikadır yeni ilerleme bildirmeyen uzun bir işlem sürüyor ({stage})."
                        callback({"stage":"unresponsive","reason":reason,"message":message+" Bekleyebilir veya Zorla durdur düğmesini kullanabilirsiniz. Son sağlam checkpoint korunur; henüz kaydedilmeyen adımlar kaybolabilir.","allow_force_stop":True})
                        unresponsive = True
                    elif not stalled and unresponsive:
                        callback({"stage":"responsive","message":"Eğitim alt işlemi yeniden ilerleme bildiriyor."})
                        unresponsive = False
                    try:
                        self.process.wait(timeout=.2)
                    except subprocess.TimeoutExpired:
                        pass
                read_events()
            except BaseException:
                self.cancel()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._stop_process()
                raise
        if self._force_stopped:
            update_manifest(job,status="interrupted",error="Kullanıcı eğitimi zorla durdurdu; yalnız son tamamlanmış atomik checkpoint'ten devam edilebilir.")
            raise InterruptedError("Eğitim zorla durduruldu. Henüz kaydedilmeyen adımlar kaybolabilir; son sağlam devam kontrol noktası korundu.")
        code = self.process.returncode
        if code == 2:
            raise InterruptedError("Eğitim iptal edildi. Oturum ve varsa devam kontrol noktası korundu.")
        if code:
            raise RuntimeError(self._error_detail(code))
        return json.loads((Path(job)/"result.json").read_text(encoding="utf-8"))


def register_model(job, candidate, registry_path, name=None):
    from model_manager import file_digest
    result = json.loads((Path(job)/"result.json").read_text(encoding="utf-8"))
    if read_manifest(job).get("status") != "completed":
        raise ValueError("Eğitim ve uyumluluk testi tamamlanmadı.")
    record = next((m for m in result["models"] if m["file"]==candidate),None)
    if not record or not record.get("smoke_passed"):
        raise ValueError("Bu model uyumluluk testinden geçmedi.")
    for path, digest in ((record["pth"],record["sha256"]),(result["index"],result["index_sha256"])):
        if file_digest(path) != digest:
            raise ValueError("Test edilen model veya index sonradan değişmiş; kayıt yapılmadı.")
    path = Path(registry_path)
    name = read_manifest(job)["options"]["name"] if name is None else name
    if not isinstance(name,str) or not name.strip() or len(name)>100:
        raise ValueError('Model adı 1–100 karakter olmalı.')
    # Registry models must survive removal of temporary training sessions.
    root = path.resolve().parent/"trained_models"
    root.mkdir(exist_ok=True)
    destination = root/(safe_filename(name)+"_"+uuid.uuid4().hex[:12])
    destination.mkdir()
    try:
        for source, filename, digest in ((record["pth"],"voice.pth",record["sha256"]),
                                        (result["index"],"voice.index",result["index_sha256"])):
            target = destination/filename
            shutil.copyfile(source,target)
            if file_digest(target) != digest:
                raise ValueError("Kalıcı modele kopyalanan dosya kontrolü başarısız; liste değiştirilmedi.")
        write_json_atomic(str(destination/"provenance.json"),
                          {"name":name,"candidate":candidate,"model_sha256":record["sha256"],
                           "index_sha256":result["index_sha256"],"smoke_passed":True})
        def add_model(models):
            if name in models:
                raise ValueError("Bu adla AI Cover modeli zaten kayıtlı. Mevcut modelin üzerine yazılmadı.")
            models[name] = {"pth":str(destination/"voice.pth"),"index":str(destination/"voice.index")}
        from registry_store import update_registry
        update_registry(path,add_model,validate_models)
    except BaseException:
        if destination.resolve().parent != root.resolve():
            raise RuntimeError("Kalıcı model temizleme yolu geçersiz.")
        shutil.rmtree(destination)
        raise
    return name


def register_models(job, registry_path, name=None):
    """Install every retained epoch snapshot in one clean, user-facing folder."""
    from model_manager import file_digest
    from registry_store import update_registry

    job = Path(job)
    result = json.loads((job/"result.json").read_text(encoding="utf-8"))
    manifest = read_manifest(job)
    if manifest.get("status") != "completed":
        raise ValueError("Eğitim ve uyumluluk testi tamamlanmadı.")
    name = manifest["options"]["name"] if name is None else name
    if not isinstance(name,str) or not name.strip() or len(name)>100:
        raise ValueError('Model adı 1–100 karakter olmalı.')

    # latest/best are technical comparison exports.  The snapshot records are
    # the exact, bounded epoch history chosen by the user on the training page.
    by_epoch = {}
    for record in result.get("models",()):
        epoch = record.get("epoch")
        if type(epoch) is int and epoch > 0 and record.get("smoke_passed"):
            by_epoch[epoch] = record
    if not by_epoch:
        # Completed jobs made by older versions do not have epoch snapshots.
        record = next((r for r in result.get("models",())
                       if r.get("file") == "latest.pth" and r.get("smoke_passed")),None)
        if record:
            by_epoch[int(result.get("epochs") or manifest["options"]["epochs"])] = record
    records = sorted(by_epoch.items())
    if not records:
        raise ValueError("Kaydedilecek, uyumluluk testinden geçmiş epoch modeli bulunamadı.")

    index_source = Path(result["index"])
    index_digest = result["index_sha256"]
    if file_digest(index_source) != index_digest:
        raise ValueError("Test edilen index sonradan değişmiş; kayıt yapılmadı.")
    for _epoch, record in records:
        if file_digest(record["pth"]) != record["sha256"]:
            raise ValueError("Test edilen epoch modellerinden biri sonradan değişmiş; kayıt yapılmadı.")

    registry_path = Path(registry_path)
    root = registry_path.resolve().parent/"trained_models"
    root.mkdir(exist_ok=True)
    base = safe_filename(name.strip())
    destination = root/base
    suffix = 2
    while True:
        try:
            destination.mkdir()
            break
        except FileExistsError:
            destination = root/f"{base} ({suffix})"
            suffix += 1
    installed_base = destination.name
    installed = []
    try:
        index_target = destination/f"{installed_base}.index"
        shutil.copyfile(index_source,index_target)
        if file_digest(index_target) != index_digest:
            raise ValueError("Kalıcı modele kopyalanan index kontrolü başarısız; liste değiştirilmedi.")
        for epoch, record in records:
            target = destination/f"{installed_base}_Epoch_{epoch:03d}.pth"
            shutil.copyfile(record["pth"],target)
            if file_digest(target) != record["sha256"]:
                raise ValueError("Kalıcı modele kopyalanan epoch dosyası kontrolü başarısız; liste değiştirilmedi.")
            installed.append((f"{installed_base} - Epoch {epoch}",target))

        def add_models(models):
            duplicate = next((label for label,_target in installed if label in models),None)
            if duplicate:
                raise ValueError(f"'{duplicate}' adlı AI Cover modeli zaten kayıtlı. Mevcut modelin üzerine yazılmadı.")
            for label,target in installed:
                models[label] = {"pth":str(target),"index":str(index_target)}
        update_registry(registry_path,add_models,validate_models)
    except BaseException:
        if destination.resolve().parent != root.resolve():
            raise RuntimeError("Kalıcı model temizleme yolu geçersiz.")
        shutil.rmtree(destination)
        raise
    return [label for label,_target in installed], str(destination)
