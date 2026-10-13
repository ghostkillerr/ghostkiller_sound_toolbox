import torch
import json
import os
from compute_backend import backend_module, is_gpu_device

version_config_paths = [
    os.path.join("48000.json"),
    os.path.join("40000.json"),
    os.path.join("32000.json"),
    os.path.join("24000.json"),
]


class Config:
    def __init__(self, device=None):
        self.device = device or ("cuda:0" if torch.cuda.is_available() else
                                 "xpu:0" if hasattr(torch, "xpu") and torch.xpu.is_available() else "cpu")
        if self.device in ("cuda", "xpu"):
            self.device += ":0"
        try:
            selected = torch.device(self.device)
        except (RuntimeError, ValueError, TypeError) as error:
            raise ValueError("Geçersiz işlem cihazı.") from error
        if selected.type not in ('cpu', 'cuda', 'xpu'):
            raise ValueError("Bu uygulama CPU, CUDA/HIP veya Intel XPU destekler.")
        if selected.type == 'cpu':
            self.device = 'cpu'
        else:
            self.device = f"{selected.type}:{selected.index if selected.index is not None else 0}"
            selected = torch.device(self.device)
        api = backend_module(self.device)
        if api is not None:
            if not api.is_available():
                raise RuntimeError(f"{selected.type.upper()} kullanılamıyor. CPU seçerek tekrar deneyin.")
            if selected.index is None or not 0 <= selected.index < api.device_count():
                raise ValueError("Seçilen GPU numarası kullanılamıyor.")
        self.gpu_name = (
            api.get_device_name(selected.index)
            if api is not None
            else None
        )
        self.json_config = self.load_config_json()
        self.gpu_mem = None
        self.x_pad, self.x_query, self.x_center, self.x_max = self.device_config()

    def load_config_json(self):
        configs = {}
        for config_file in version_config_paths:
            config_path = os.path.join(os.path.dirname(__file__), config_file)
            with open(config_path, "r", encoding="utf-8") as f:
                configs[config_file] = json.load(f)
        return configs

    def device_config(self):
        if is_gpu_device(self.device):
            self.set_gpu_config()

        # Configuration for 6GB GPU memory
        x_pad, x_query, x_center, x_max = (1, 6, 38, 41)
        if self.gpu_mem is not None and self.gpu_mem <= 4:
            # Configuration for 5GB GPU memory
            x_pad, x_query, x_center, x_max = (1, 5, 30, 32)

        return x_pad, x_query, x_center, x_max

    def set_gpu_config(self):
        i_device = int(self.device.split(":")[-1])
        api = backend_module(self.device)
        self.gpu_name = api.get_device_name(i_device)
        self.gpu_mem = api.get_device_properties(i_device).total_memory // (
            1024**3
        )
