"""Probe the installed PyTorch backend instead of trusting GPU brand names."""
from dataclasses import dataclass, field
import os
import platform
import subprocess
import json
import re
from compute_backend import backend_module, clear_cache, synchronize, is_gpu_device


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

    def summary(self, preference='cpu'):
        lines = [f"İşlemci: {self.cpu.name}",
                 "İşlemci kontrolü başarılı." if self.cpu.available else
                 "İşlemci kontrolü tamamlanamadı. Teknik ayrıntılarda hata bilgisi bulunur."]
        usable = [gpu for gpu in self.gpus if gpu.available]
        if usable:
            gpu = max(usable, key=lambda item: item.memory_gb)
            lines.extend([f"Ekran kartı: {gpu.name}", "Ekran kartı kontrolü başarılı."])
        else:
            lines.append("Bu programda kullanılabilecek bir ekran kartı bulunamadı. İşlemciyi seçin.")
        selected = 'İşlemci' if preference == 'cpu' else 'Ekran kartı'
        lines.append(f"Seçiminiz: {selected}.")
        if preference == 'gpu' and not usable:
            lines.append("Kayıtlı ekran kartı seçiminiz kullanılamıyor; devam etmek için İşlemciyi seçin.")
        lines.append("Bu seçim ses işlemleri ve eğitim için kullanılır. Eğitim başlarken ayrıca kontrol yapılır.")
        return '\n'.join(lines)

    def describe(self):
        lines = [f"İşlemci: {self.cpu.name} — " + ("hesaplama testi başarılı" if self.cpu.available else self.cpu.reason)]
        for gpu in self.gpus:
            state = "hesaplama testi başarılı" if gpu.available else gpu.reason
            lines.append(f"Ekran kartı: {gpu.name} ({gpu.backend}, {gpu.memory_gb:.1f} GB) — {state}")
        if self.detected_cards:
            lines.append("Windows'un gördüğü kartlar: " + ", ".join(self.detected_cards))
        lines.extend([
            f"Çalışma ortamı: {self.runtime}",
            "NVIDIA: CUDA. AMD ROCm: işletim sistemi ve resmi destek matrisi ayrıca kontrol edilmelidir.",
            "Intel Arc ve uyumlu Core Ultra: ayrı native PyTorch XPU paketi gerekir. Eski Intel iGPU'lar bu destekten otomatik yararlanmaz.",
            "Windows ROCm eğitiminde runtime sürümü ve gerçek backward testi kontrol edilir. Forward testi bütün modellerin eğitim desteğini garanti etmez.",
            "Bu programın RVC ve RoFormer zinciri için DirectML etkinleştirilmez.",
            "CPU ve GPU aynı model dosyalarını kullanır. Sürücüler bu ekrandan kurulmaz.",
            "Hesaplama testi, tüm modellerin belleğe sığacağını garanti etmez.",
        ])
        return "\n".join(lines)


def ensure_training_backend(device):
    import torch
    if backend_module(device) is None:
        return
    if os.name == "nt" and str(device).startswith("cuda") and torch.version.hip:
        def version(value):
            return tuple(int(x) for x in re.findall(r"\d+", str(value).split("+")[0])[:3])
        if version(torch.__version__) < (2,12) or version(torch.version.hip) < (7,14):
            raise RuntimeError("Bu eski Windows ROCm/PyTorch sürümünde resmi eğitim desteği doğrulanmamış. Native ROCm 7.14+ / PyTorch 2.12+ paketini kullanın veya Ayarlar'dan İşlemci seçin.")
    probe_training_operations(device)


def probe_training_operations(device):
    """Exercise FP32 backward kernels; not a full model compatibility guarantee."""
    import torch
    import torch.nn.functional as F
    devices = [torch.device(device).index or 0] if is_gpu_device(device) else []
    kind = str(device).split(":")[0] if is_gpu_device(device) else "cuda"
    with torch.enable_grad(), torch.random.fork_rng(devices=devices,device_type=kind):
        data = torch.linspace(-1,1,1024,device=device).reshape(1,1,-1).requires_grad_()
        weight = torch.ones(2,1,5,device=device,requires_grad=True)
        conv = F.conv1d(data,weight)
        recurrent = torch.nn.LSTM(2,4,batch_first=True).to(device)
        sequence,_ = recurrent(conv[:,:,:16].transpose(1,2))
        spectrum = torch.stft(data.flatten(),128,32,window=torch.hann_window(128,device=device),return_complex=True)
        attention = F.scaled_dot_product_attention(conv[:,:,:32],conv[:,:,:32],conv[:,:,:32])
        loss = sequence.square().mean()+spectrum.abs().square().mean()+attention.square().mean()
        loss.backward()
        gradients = [data.grad,weight.grad]+[p.grad for p in recurrent.parameters()]
        if not torch.isfinite(loss).item() or any(g is None or not torch.isfinite(g).all().item() for g in gradients):
            raise RuntimeError("Seçilen GPU geçerli FP32 backward sonucu üretmedi; eğitim başlatılmadı.")
    synchronize(device)


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
    synchronize(device)


def detect_hardware():
    import torch
    try:
        probe_operations("cpu")
        cpu = DeviceSupport("cpu", cpu_name(), True)
    except Exception as error:
        cpu = DeviceSupport("cpu", cpu_name(), False, f"İşlemci testi başarısız: {error}")
    backend = "ROCm" if torch.version.hip else "CUDA"
    report = HardwareReport(cpu, detected_cards=windows_cards(), runtime=f"PyTorch {torch.__version__}")
    for kind, api, label in (("cuda",torch.cuda,backend),("xpu",getattr(torch,"xpu",None),"Intel XPU")):
        if api is None:
            continue
        try:
            count = api.device_count() if api.is_available() else 0
            for index in range(count):
                device = f"{kind}:{index}"
                name, memory = device, 0
                try:
                    name = api.get_device_name(index)
                    memory = api.get_device_properties(index).total_memory / 1024**3
                    probe_operations(device)
                    report.gpus.append(DeviceSupport(device,name,True,memory_gb=memory,backend=label))
                except Exception as error:
                    report.gpus.append(DeviceSupport(device,name,False,f"GPU testi başarısız: {error}",memory,label))
                finally:
                    try:
                        clear_cache(device)
                    except Exception:
                        pass
        except Exception as error:
            report.gpus.append(DeviceSupport(f"{kind}:0","GPU",False,f"GPU sorgusu başarısız: {error}",backend=label))
    if not report.gpus:
        report.gpus.append(DeviceSupport("cuda:0",", ".join(report.detected_cards) or "GPU",False,
                                        "Kurulu PyTorch paketi ve sürücüyle GPU kullanılamıyor. Cihazınıza uygun CPU/CUDA/ROCm/XPU dağıtımını kullanın.",backend=backend))
    return report


def configure_runtime(device):
    """Avoid CPU thread oversubscription and retain FP32 model compatibility."""
    import torch
    # GPU jobs also perform preprocessing and retrieval on the host CPU.
    threads = max(1,min(8,(os.cpu_count() or 2)//2))
    torch.set_num_threads(threads)
    try:
        import faiss
        faiss.omp_set_num_threads(threads)
    except ImportError:
        pass
    api = backend_module(device)
    if api is not None:
        api.set_device(device)
