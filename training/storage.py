"""Atomic training artifacts and complete, weights_only-compatible resume state."""
import json
import os
from pathlib import Path
import tempfile
from app_settings import write_json_atomic


def atomic_torch_save(value, path):
    import torch
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".part")
    try:
        with os.fdopen(fd, "wb") as stream:
            torch.save(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def cleanup_incomplete_artifacts(job):
    """Caller holds worker.guard; delete only our named atomic-save fragments."""
    root = Path(job).resolve()
    removed = []
    for target in ("resume.pth","latest.pth","best_validation.pth"):
        for path in root.glob(target+".*.part"):
            # Do not follow a redirected file out of the owned session folder.
            if path.is_symlink() or path.resolve().parent != root or not path.is_file():
                raise ValueError("Yarım eğitim dosyasının yolu oturum klasörü dışında; otomatik temizleme durduruldu.")
            path.unlink()
            removed.append(path.name)
    return removed


def read_manifest(job):
    return json.loads((Path(job) / "manifest.json").read_text(encoding="utf-8"))


def update_manifest(job, **values):
    data = read_manifest(job)
    data.update(values)
    write_json_atomic(str(Path(job) / "manifest.json"), data)
    return data


def map_legacy_weights(state):
    # Old weight_norm checkpoints are consumed by parametrized PyTorch modules.
    return {key.replace(".weight_g", ".parametrizations.weight.original0")
               .replace(".weight_v", ".parametrizations.weight.original1"): value
            for key, value in state.items()}


def rng_layout(device):
    """The backend/device arrangement whose RNG states belong to this session."""
    import torch
    from compute_backend import backend_module
    kind = str(device).split(":",1)[0]
    api = backend_module(device)
    return {"kind":kind,"runtime":"hip" if kind == "cuda" and torch.version.hip else kind,
            "device_count":api.device_count() if api is not None else 0,
            "device_index":(torch.device(device).index or 0) if api is not None else None}


def validate_checkpoint_backend(state, device):
    """Reject a backend migration before any generator/optimizer/RNG mutation."""
    expected = rng_layout(device)
    saved = state.get("rng_layout")
    if saved is not None:
        if saved != expected:
            raise ValueError("Devam dosyasının donanım backend'i veya GPU/RNG düzeni seçilen cihazla eşleşmiyor. Aynı donanım düzenini seçin veya yeni eğitim oturumu başlatın.")
    else:
        # Legacy CPU state is unambiguous. Old Windows GPU checkpoints came
        # from CUDA (HIP training was blocked); their all-device RNG list is
        # usable on CUDA device 0 with the same device count. Missing metadata
        # must never turn CPU<->GPU or CUDA<->HIP into a silent migration.
        backend = state.get("rng_backend") or ("cuda" if state.get("cuda_rng") else "cpu")
        if backend != expected["kind"] or (backend == "cuda" and expected["runtime"] != "cuda"):
            raise ValueError("Eski devam dosyasının RNG backend'i seçilen cihazla eşleşmiyor. CPU/GPU veya CUDA/ROCm değişimi aynen devam olarak desteklenmiyor.")
        if backend != "cpu" and expected["device_index"] != 0:
            raise ValueError("Eski devam dosyasında seçili GPU kimliği kayıtlı değil; GPU 0 dışında aynen devam doğrulanamaz.")
    states = state.get("device_rng",state.get("cuda_rng",[]))
    if len(states) != expected["device_count"]:
        raise ValueError("Devam dosyasındaki GPU RNG sayısı kurulu ortamla eşleşmiyor; aynı donanım düzenini seçin veya yeni oturum başlatın.")
    return expected
