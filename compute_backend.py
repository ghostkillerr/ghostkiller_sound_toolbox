"""Device operations shared by native CPU, CUDA/ROCm and Intel XPU workers.

This selects only an installed backend. It never installs a runtime or silently
changes the user's chosen device, precision or model profile.
"""
from contextlib import nullcontext


def is_gpu_device(device):
    return str(device).split(":", 1)[0] in ("cuda", "xpu")


def backend_module(device):
    import torch
    kind = str(device).split(":", 1)[0]
    if kind == "cpu":
        return None
    if kind == "cuda":
        return torch.cuda
    if kind == "xpu" and hasattr(torch, "xpu"):
        return torch.xpu
    raise ValueError(f"Desteklenmeyen işlem cihazı: {device}")


def device_context(device):
    api = backend_module(device)
    return api.device(device) if api is not None else nullcontext()


def synchronize(device):
    api = backend_module(device)
    if api is not None:
        api.synchronize(device)


def clear_cache(device):
    api = backend_module(device)
    if api is not None and api.is_available():
        with device_context(device):
            api.empty_cache()


def memory_info(device):
    """Return measured free/total bytes; None when the backend cannot report it."""
    api = backend_module(device)
    if api is None or not hasattr(api, "mem_get_info"):
        return None
    try:
        free, total = api.mem_get_info(device)
        return (int(free), int(total)) if total > 0 else None
    except (RuntimeError, NotImplementedError, AttributeError):
        return None


def device_stats(device):
    api = backend_module(device)
    if api is None:
        return {}
    values = {}
    for method, key in (("memory_allocated", "vram_allocated_mb"),
                        ("memory_reserved", "vram_reserved_mb"),
                        ("max_memory_allocated", "vram_peak_mb")):
        if hasattr(api, method):
            values[key] = getattr(api, method)(device)/1024**2
    info = memory_info(device)
    if info:
        values.update(vram_free_mb=info[0]/1024**2, vram_total_mb=info[1]/1024**2)
    else:
        properties = api.get_device_properties(device)
        total = getattr(properties, "total_memory", 0)
        if total:
            values["vram_total_mb"] = total/1024**2
    return values


def get_rng_states(device):
    api = backend_module(device)
    return api.get_rng_state_all() if api is not None else []


def set_rng_states(device, states):
    api = backend_module(device)
    if api is not None and states:
        if len(states) != api.device_count():
            raise ValueError("Devam dosyasındaki GPU sayısı kurulu ortamla eşleşmiyor; yeni bir eğitim oturumu başlatın.")
        api.set_rng_state_all([state.cpu() for state in states])


def trim_cache(device):
    """Trim idle GPU blocks only under measured pressure."""
    api = backend_module(device)
    info = memory_info(device)
    if api is None or info is None:
        return
    reserved, allocated = api.memory_reserved(device), api.memory_allocated(device)
    free, total = info
    if reserved-allocated > 512*1024**2 and (free < total*.15 or reserved > total*.7):
        clear_cache(device)
