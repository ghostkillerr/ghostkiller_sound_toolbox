"""Validated training requests, independent of torch and wx."""
from dataclasses import dataclass, asdict
from pathlib import Path
import math

BACKEND_COMMIT = "55fe0b976a6990bb75261c32ccecf6bfca3198f1"
FORMAT_VERSION = 1
TRAINER_REVISION = "ghostkiller-rvc-v2-fp32-1"  # Bump when training math/resume semantics change.


@dataclass(frozen=True)
class TrainingOptions:
    name: str
    sources: tuple
    sample_rate: int = 40000
    epochs: int = 200
    batch_size: int = 0  # Auto: measured full GAN forward/backward, not VRAM guesswork.
    save_every: int = 10
    learning_rate: float = 0.0001
    segment_seconds: float = 3.0
    overlap_seconds: float = 0.3
    holdout_fraction: float = 0.1
    seed: int = 1234
    checkpointing: bool = True
    cpu_threads: int = 4
    f0_method: str = "rmvpe"
    source_groups: tuple = ()  # Same song/session/stem variants stay in one partition.
    source_ranges: tuple = ()  # Per-source (start, end) seconds; end=0 means EOF.
    snapshot_limit: int = 3
    snapshot_budget_mb: int = 2048
    reuse_preparation: bool = True
    comparison_sources: tuple = ()

    def validate(self, check_sources=True):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 100:
            raise ValueError("Model adı 1–100 karakter olmalı.")
        if self.sample_rate not in (32000, 40000, 48000):
            raise ValueError("Örnekleme hızı 32, 40 veya 48 kHz olmalı.")
        for key, lower, upper in (("epochs", 1, 10000), ("batch_size", 0, 64),
                                  ("save_every", 1, 1000), ("cpu_threads", 1, 64),
                                  ("seed", 0, 2**31 - 1), ("snapshot_limit", 0, 20),
                                  ("snapshot_budget_mb", 256, 16384)):
            value = getattr(self, key)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"Geçersiz eğitim ayarı: {key}")
        for key, lower, upper in (("learning_rate", 1e-6, 0.001),
                                  ("segment_seconds", 1.0, 6.0),
                                  ("overlap_seconds", 0.0, 1.0),
                                  ("holdout_fraction", 0.05, 0.3)):
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"Geçersiz eğitim ayarı: {key}")
        if self.overlap_seconds >= self.segment_seconds:
            raise ValueError("Örtüşme, parça süresinden küçük olmalı.")
        if round(self.segment_seconds*self.sample_rate) - round(self.overlap_seconds*self.sample_rate) <= 0:
            raise ValueError("Örtüşme sonrası ilerleme en az bir ses örneği olmalı.")
        if self.f0_method not in ("rmvpe", "crepe", "crepe-tiny") or type(self.checkpointing) is not bool:
            raise ValueError("Geçersiz F0 veya bellek ayarı.")
        if type(self.reuse_preparation) is not bool:
            raise ValueError("Hazırlık önbelleği tercihi geçersiz.")
        if not self.sources:
            raise ValueError("Aynı kişiye ait en az bir ses kaydı seçin.")
        if not isinstance(self.comparison_sources,tuple) or len(self.comparison_sources)>5 or any(not isinstance(p,str) for p in self.comparison_sources):
            raise ValueError('Karşılaştırma için en fazla beş ayrı kayıt seçilebilir.')
        if not isinstance(self.source_groups,tuple):
            raise ValueError("Kayıt grupları bir liste halinde tutulmalı.")
        if self.source_groups and (len(self.source_groups) != len(self.sources) or
                                  any(not isinstance(group,str) or len(group)>100 for group in self.source_groups)):
            raise ValueError("Kayıt grupları seçilen dosyalarla eşleşmeli; grup adı en fazla 100 karakter olmalı.")
        if not isinstance(self.source_ranges, tuple) or (self.source_ranges and len(self.source_ranges) != len(self.sources)):
            raise ValueError("Ses bölümleri seçilen dosyalarla eşleşmeli.")
        for interval in self.source_ranges:
            if (not isinstance(interval, tuple) or len(interval) != 2 or
                    any(type(x) not in (int, float) or not math.isfinite(x) for x in interval) or
                    interval[0] < 0 or interval[1] < 0 or (interval[1] and interval[1]-interval[0] < 2)):
                raise ValueError("Ses bölümü başlangıcı pozitif, süresi en az iki saniye olmalı; bitiş 0 ise dosyanın sonu kullanılır.")
        if check_sources:
            for source in self.sources+self.comparison_sources:
                if not Path(source).is_file() or "|" in str(source) or "\n" in str(source):
                    raise ValueError(f"Kayıt bulunamadı veya yolu geçersiz: {source}")
        return self

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["sources"] = tuple(value["sources"])
        if not isinstance(value.get("source_groups",()),(list,tuple)):
            raise ValueError("Kayıt grupları bir liste halinde tutulmalı.")
        value["source_groups"] = tuple(value.get("source_groups", ()))
        intervals = value.get("source_ranges", ())
        if not isinstance(intervals, (list, tuple)) or any(not isinstance(x, (list, tuple)) for x in intervals):
            raise ValueError("Ses bölümleri liste halinde tutulmalı.")
        value["source_ranges"] = tuple(tuple(x) for x in intervals)
        if not isinstance(value.get('comparison_sources',()),(list,tuple)):
            raise ValueError('Karşılaştırma kayıtları bir liste olmalı.')
        value['comparison_sources'] = tuple(value.get('comparison_sources',()))
        return cls(**value).validate(check_sources=False)


def architecture(rate):
    import json
    from app_runtime import resource_directory
    path = Path(resource_directory()) / "training" / "vendor" / f"config_{rate}.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["model"]["spk_embed_dim"] = 1
    return config


def inference_config(config):
    model, data = config["model"], config["data"]
    keys = ("inter_channels", "hidden_channels", "filter_channels", "n_heads", "n_layers",
            "kernel_size", "p_dropout", "resblock", "resblock_kernel_sizes",
            "resblock_dilation_sizes", "upsample_rates", "upsample_initial_channel",
            "upsample_kernel_sizes", "spk_embed_dim", "gin_channels")
    return [data["filter_length"] // 2 + 1, config["train"]["segment_size"] // data["hop_length"],
            *(model[key] for key in keys), data["sample_rate"]]
