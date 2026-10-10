"""Probe the installed PyTorch backend instead of trusting GPU brand names."""
from dataclasses import dataclass, field
import os
import platform
import subprocess
import json


@dataclass(frozen=True)
class DeviceSupport:
    device: str
    name: str
    available: bool
    reason: str = ""
    memory_gb: float = 0
    backend: str = "CPU"


@dataclass
class HardwareReport:
    cpu: DeviceSupport
    gpus: list = field(default_factory=list)
    detected_cards: list = field(default_factory=list)
    runtime: str = ""

    def selected(self, preference):
        if preference == "cpu":
            result = self.cpu
        elif preference == "gpu":
            usable = [gpu for gpu in self.gpus if gpu.available]
            if not usable:
                reasons = "; ".join(gpu.reason for gpu in self.gpus) or "Uyumlu GPU çalışma ortamı bulunamadı."
                raise RuntimeError(f"Ekran kartı kullanılamıyor: {reasons} Ayarlar'dan İşlemci seçin.")
            result = max(usable, key=lambda gpu: gpu.memory_gb)
        else:
            raise ValueError("İşlemci veya ekran kartı seçin.")
        if not result.available:
            raise RuntimeError(result.reason)
        return result

    def describe(self):
        lines = [f"İşlemci: {self.cpu.name} — " + ("hesaplama testi başarılı" if self.cpu.available else self.cpu.reason)]
        for gpu in self.gpus:
            state = "hesaplama testi başarılı" if gpu.available else gpu.reason
            lines.append(f"Ekran kartı: {gpu.name} ({gpu.backend}, {gpu.memory_gb:.1f} GB) — {state}")
        if self.detected_cards:
            lines.append("Windows'un gördüğü kartlar: " + ", ".join(self.detected_cards))
        lines.extend([
            f"Çalışma ortamı: {self.runtime}",
            "NVIDIA: CUDA; AMD: uyumlu ROCm/PyTorch kurulumu ve başarılı hesaplama testi gerekir.",
            "Bu programın RVC ve RoFormer zinciri için DirectML etkinleştirilmez.",
            "CPU ve GPU aynı model dosyalarını kullanır. Sürücüler bu ekrandan kurulmaz.",
            "Hesaplama testi, tüm modellerin belleğe sığacağını garanti etmez.",
        ])
        return "\n".join(lines)


def windows_cards():
    if os.name != "nt":
        return []
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) | ConvertTo-Json -Compress"],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        names = json.loads(completed.stdout.decode("utf-8-sig"))
        return [names] if isinstance(names, str) else list(names or [])
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def cpu_name():
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or "İşlemci"


def probe_operations(device):
    """Exercise FP32, convolution, FFT and recurrent layers used by both engines."""
    import torch
    import torch.nn.functional as F
    with torch.inference_mode():
        data = torch.linspace(-1, 1, 1024, device=device).reshape(1, 1, -1)
        conv = F.conv1d(data, torch.ones(2, 1, 5, device=device))
        spectrum = torch.stft(data.flatten(), 128, 32, window=torch.hann_window(128, device=device), return_complex=True)
        attention = F.scaled_dot_product_attention(conv[:, :, :32], conv[:, :, :32], conv[:, :, :32])
        recurrent = torch.nn.LSTM(2, 4, batch_first=True).to(device)
        sequence, _ = recurrent(conv[:, :, :16].transpose(1, 2))
        for output in (spectrum.abs(), attention, sequence):
            if not torch.isfinite(output).all().item():
                raise RuntimeError("Hesaplama testi geçersiz değer üretti.")
    if str(device).startswith("cuda"):
        torch.cuda.synchronize(device)


def detect_hardware():
    import torch
    try:
        probe_operations("cpu")
        cpu = DeviceSupport("cpu", cpu_name(), True)
    except Exception as error:
        cpu = DeviceSupport("cpu", cpu_name(), False, f"İşlemci testi başarısız: {error}")
    backend = "ROCm" if torch.version.hip else "CUDA"
    report = HardwareReport(cpu, detected_cards=windows_cards(), runtime=f"PyTorch {torch.__version__}")
    try:
        count = torch.cuda.device_count() if torch.cuda.is_available() else 0
        for index in range(count):
            device = f"cuda:{index}"
            name, memory = device, 0
            try:
                name = torch.cuda.get_device_name(index)
                memory = torch.cuda.get_device_properties(index).total_memory / 1024 ** 3
                probe_operations(device)
                report.gpus.append(DeviceSupport(device, name, True, memory_gb=memory, backend=backend))
            except Exception as error:
                report.gpus.append(DeviceSupport(device, name, False, f"GPU testi başarısız: {error}", memory, backend))
            finally:
                with torch.cuda.device(index):
                    torch.cuda.empty_cache()
        if not count:
            report.gpus.append(DeviceSupport("cuda:0", ", ".join(report.detected_cards) or "GPU", False,
                                            "Kurulu PyTorch ve sürücüyle GPU kullanılamıyor.", backend=backend))
    except Exception as error:
        report.gpus.append(DeviceSupport("cuda:0", "GPU", False, f"GPU sorgusu başarısız: {error}", backend=backend))
    return report


def configure_runtime(device):
    """Avoid CPU thread oversubscription and retain FP32 model compatibility."""
    import torch
    # GPU jobs also perform preprocessing and retrieval on the host CPU.
    torch.set_num_threads(max(1, min(8, (os.cpu_count() or 2) // 2)))
    if str(device).startswith("cuda"):
        torch.cuda.set_device(device)
