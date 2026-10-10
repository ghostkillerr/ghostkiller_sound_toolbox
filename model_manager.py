"""Explicit model installation, offline integrity checks and atomic repair."""
import gc
import hashlib
import json
import os
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from app_runtime import app_directory, model_directory, download_model, copy_model, same_path, configure_runtime_cache


BASE_URL = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources"
RVC_ASSETS = {
    "contentvec": ("AI Cover: ses özellikleri (ContentVec)", (
        ("embedders/contentvec/config.json", f"{BASE_URL}/embedders/contentvec/config.json"),
        ("embedders/contentvec/pytorch_model.bin", f"{BASE_URL}/embedders/contentvec/pytorch_model.bin"),
    )),
    "rmvpe": ("AI Cover: nota algılama (RMVPE)", (
        ("predictors/rmvpe.pt", f"{BASE_URL}/predictors/rmvpe.pt"),
    )),
}


def model_catalog():
    from separation_steps import SEPARATION_STEPS
    return {**{step[0]: step[1] for step in SEPARATION_STEPS},
            **{key: value[0] for key, value in RVC_ASSETS.items()}}


def file_digest(path, cancelled=None):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            if cancelled and cancelled():
                raise InterruptedError("Dosya kontrolü iptal edildi.")
            digest.update(chunk)
    return digest.hexdigest()


def validate_metadata(value, relative):
    """Validate the fields consumed by managed model architectures."""
    name = relative.replace('\\', '/').split('/')[-1]
    def positive(number):
        return type(number) is int and number > 0
    if relative.replace('\\', '/') == 'embedders/contentvec/config.json':
        fields = ('hidden_size', 'intermediate_size', 'num_hidden_layers',
                  'num_attention_heads', 'classifier_proj_size')
        if value.get('model_type') != 'hubert' or any(not positive(value.get(key)) for key in fields):
            raise ValueError('ContentVec yapılandırmasında zorunlu HuBERT alanları eksik veya geçersiz.')
        arrays = [value.get(key) for key in ('conv_dim', 'conv_kernel', 'conv_stride')]
        if (any(not isinstance(items, (list, tuple)) or not items or
                any(not positive(item) for item in items) for items in arrays) or
                len({len(items) for items in arrays}) != 1 or
                value['hidden_size'] % value['num_attention_heads']):
            raise ValueError('ContentVec konvolüsyon/attention boyutları geçersiz.')
    elif name.endswith(('.yaml', '.yml')):
        for section in ('audio', 'model', 'training', 'inference'):
            if not isinstance(value.get(section), dict) or not value[section]:
                raise ValueError(f'Ayrıştırma yapılandırmasında {section} alanı eksik.')
        for section, keys in (('audio', ('chunk_size', 'sample_rate', 'num_channels')),
                              ('model', ('dim', 'depth', 'heads', 'stft_n_fft', 'stft_hop_length')),
                              ('inference', ('batch_size', 'num_overlap'))):
            if any(not positive(value[section].get(key)) for key in keys):
                raise ValueError(f'Ayrıştırma yapılandırmasında {section} boyutları geçersiz.')
        instruments = value['training'].get('instruments')
        target = value['training'].get('target_instrument')
        if (not isinstance(instruments, list) or not instruments or
                any(not isinstance(item, str) or not item for item in instruments) or
                target not in instruments):
            raise ValueError('Ayrıştırma yapılandırmasında hedef ses kanalı geçersiz.')
    elif name in ('vr_model_data.json', 'mdx_model_data.json'):
        if any(not isinstance(entry, dict) or not entry for entry in value.values()):
            raise ValueError('Ayrıştırma model metadata kayıtları geçersiz.')


def validate_weight_schema(weights, relative, config=None):
    """Check helper network keys/shapes without allocating model weights."""
    configure_runtime_cache()
    import torch
    relative = relative.replace('\\', '/')
    if relative == 'predictors/rmvpe.pt':
        from rvc.lib.predictors.RMVPE import E2E
        with torch.device('meta'):
            expected = E2E(4, 1, (2, 2)).state_dict()
    elif relative == 'embedders/contentvec/pytorch_model.bin':
        from transformers import HubertConfig
        from rvc.lib.utils import HubertModelWithFinalProj
        validate_metadata(config, 'embedders/contentvec/config.json')
        with torch.device('meta'):
            expected = HubertModelWithFinalProj(HubertConfig(**config)).state_dict()
        # Older checkpoints predate PyTorch's weight_norm parametrization names.
        weights = dict(weights)
        prefix = 'encoder.pos_conv_embed.conv.'
        for old, new in (('weight_g', 'parametrizations.weight.original0'),
                         ('weight_v', 'parametrizations.weight.original1')):
            if prefix + old in weights and prefix + new in expected:
                weights[prefix + new] = weights.pop(prefix + old)
    else:
        # Managed separator checkpoints must contain their architecture's layers.
        name = os.path.basename(relative)
        if name.endswith('.ckpt'):
            prefixes = ('layers.', 'band_split.', 'mask_estimators.')
        elif name in ('UVR-DeEcho-DeReverb.pth', 'UVR-DeNoise.pth'):
            prefixes = ('stg1_low_band_net.', 'stg1_high_band_net.',
                        'stg2_low_band_net.', 'stg2_high_band_net.',
                        'stg3_full_band_net.', 'out.', 'aux_out.')
        else:
            return
        if any(not any(isinstance(key, str) and key.startswith(prefix) and
                       torch.is_tensor(tensor) and tensor.numel()
                       for key, tensor in weights.items()) for prefix in prefixes):
            raise ValueError('Ayrıştırma modelinin zorunlu ağ katmanları eksik.')
        return
    for key, tensor in expected.items():
        actual = weights.get(key)
        if not torch.is_tensor(actual) or actual.shape != tensor.shape:
            raise ValueError(f'Model ağırlığı eksik veya boyutu uyumsuz: {key}')


def validate_file(path, relative, cancelled=None, config=None):
    """Reject HTML responses, malformed metadata, and damaged checkpoint archives."""
    if not os.path.isfile(path) or not os.path.getsize(path):
        raise ValueError("Dosya boş veya bulunamadı.")
    extension = os.path.splitext(relative)[1].lower()
    if extension in (".json", ".yaml", ".yml"):
        with open(path, encoding="utf-8") as stream:
            if extension == ".json":
                value = json.load(stream)
            else:
                import yaml
                class ModelLoader(yaml.SafeLoader):
                    pass
                # Official RoFormer configs contain tuples, but require no Python objects.
                ModelLoader.add_constructor("tag:yaml.org,2002:python/tuple", lambda loader, node: tuple(loader.construct_sequence(node)))
                value = yaml.load(stream, Loader=ModelLoader)
        if not isinstance(value, dict) or not value:
            raise ValueError("Model yapılandırması boş veya geçersiz.")
        validate_metadata(value, relative)
    elif extension in (".pt", ".pth", ".ckpt", ".bin"):
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    with archive.open(member) as stream:
                        while stream.read(1024 * 1024):
                            if cancelled and cancelled():
                                raise InterruptedError("Dosya kontrolü iptal edildi.")
        import torch
        try:
            value = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
        except RuntimeError as error:
            if "mmap" not in str(error).lower():
                raise
            value = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(value, dict) or not value:
            raise ValueError("Model ağırlıkları geçersiz.")
        weights = value.get("state_dict")
        if not isinstance(weights, dict):
            weights = value.get("weight")
        if not isinstance(weights, dict):
            weights = value
        if not isinstance(weights, dict) or not any(torch.is_tensor(tensor) and tensor.numel() for tensor in weights.values()):
            raise ValueError("Model dosyasında kullanılabilir ağırlık bulunamadı.")
        if relative.replace('\\', '/') == 'embedders/contentvec/pytorch_model.bin' and config is None:
            with open(os.path.join(os.path.dirname(path), 'config.json'), encoding='utf-8') as stream:
                config = json.load(stream)
        validate_weight_schema(weights, relative, config)
        del value, weights
        gc.collect()
    else:
        raise ValueError(f"Desteklenmeyen model dosyası: {relative}")


class ModelManager:
    def __init__(self, app_dir=None):
        self.app_dir = app_dir or app_directory()
        self.root = model_directory(self.app_dir)
        self.manifest_path = os.path.join(self.root, ".integrity.json")
        self.records = {}
        self.warning = ""
        try:
            with open(self.manifest_path, encoding="utf-8") as stream:
                value = json.load(stream)
            if value.get("version") != 1 or not isinstance(value.get("models"), dict):
                raise ValueError("Geçersiz kontrol kaydı")
            for record in value["models"].values():
                if not isinstance(record, dict) or not isinstance(record.get("files"), dict):
                    raise ValueError("Geçersiz model kontrol kaydı")
                for relative, information in record["files"].items():
                    self.path(relative)
                    if (not isinstance(information, dict) or
                            not isinstance(information.get("sha256"), str) or
                            len(information["sha256"]) != 64 or
                            any(character not in "0123456789abcdef" for character in information["sha256"]) or
                            not isinstance(information.get("size"), int) or information["size"] <= 0 or
                            not isinstance(information.get("mtime_ns"), int)):
                        raise ValueError("Geçersiz dosya kontrol kaydı")
            self.records = value["models"]
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as error:
            self.warning = f"Bütünlük kaydı okunamadı; dosyaları yeniden kontrol edin. {error}"

    def path(self, relative):
        path = os.path.realpath(os.path.join(self.root, relative))
        root = os.path.realpath(self.root)
        if os.path.normcase(os.path.commonpath([root, path])) != os.path.normcase(root):
            raise ValueError("Model yolu models klasörünün dışına çıkamaz.")
        return path

    def primary_files(self, model_id):
        return [asset[0] for asset in RVC_ASSETS[model_id][1]] if model_id in RVC_ASSETS else [model_id]

    def status(self, model_id):
        try:
            if any(not os.path.isfile(self.path(relative)) or not os.path.getsize(self.path(relative)) for relative in self.primary_files(model_id)):
                return "Eksik"
            record = self.records.get(model_id, {})
            if record.get("error"):
                return "Bozuk veya eksik yardımcı dosya: " + record["error"]
            if record.get('schema_version') != 1:
                return "Dosya kontrolü gerekli; model şeması doğrulanmamış"
            files = record.get("files", {})
            if not files or not set(self.primary_files(model_id)).issubset(files):
                return "İndirildi; dosya kontrolü gerekli"
            for relative, information in files.items():
                stat = os.stat(self.path(relative))
                if stat.st_size != information["size"] or stat.st_mtime_ns != information["mtime_ns"]:
                    return "Dosya değişmiş; kontrol gerekli"
            return "Hazır"
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return "Dosya kontrolü gerekli"

    def require_ready(self, model_ids):
        problems = [f"{model_catalog()[model_id]}: {self.status(model_id)}" for model_id in model_ids if self.status(model_id) != "Hazır"]
        if problems:
            raise RuntimeError("Ayarlar sekmesinden modelleri indirin, kontrol edin veya onarın.\n" + "\n".join(problems))

    def save(self):
        from app_settings import write_json_atomic
        write_json_atomic(self.manifest_path, {"version": 1, "models": self.records})

    def legacy_sources(self, relative):
        if relative.startswith(("predictors/", "embedders/")):
            return [os.path.join(self.app_dir, "rvc", "models", relative),
                    os.path.join(os.path.expanduser("~"), ".cache", "rvc", "models", relative)]
        from ui_separator import model_cache_directories
        return [os.path.join(directory, relative) for directory in model_cache_directories(self.app_dir)]

    def process(self, model_ids, action, cancelled=None, progress=None, log=None):
        """Verify is offline. Install downloads missing files; repair replaces damaged ones."""
        if action not in ("verify", "install", "repair"):
            raise ValueError("Geçersiz model işlemi.")
        catalog = model_catalog()
        failures = {}
        for model_id in model_ids:
            if model_id not in catalog:
                raise ValueError(f"Bilinmeyen model: {model_id}")
            if cancelled and cancelled():
                raise InterruptedError("Model işlemi iptal edildi.")
            previous = self.records.get(model_id, {}).get("files", {})
            checked = {}
            if log:
                log(f"{catalog[model_id]}: {action}")

            def asset_handler(url, path):
                if cancelled and cancelled():
                    raise InterruptedError("Model işlemi iptal edildi.")
                relative = os.path.relpath(path, self.root).replace(os.sep, "/")
                self.path(relative)
                if relative in checked:
                    return
                config = None
                if relative == 'embedders/contentvec/pytorch_model.bin':
                    with open(self.path('embedders/contentvec/config.json'), encoding='utf-8') as stream:
                        config = json.load(stream)

                def inspect(candidate):
                    if progress:
                        progress(f"Kontrol: {relative}", 0, 0)
                    validate_file(candidate, relative, cancelled, config=config)
                    digest = file_digest(candidate, cancelled)
                    expected = previous.get(relative, {}).get("sha256")
                    if expected and digest != expected:
                        raise ValueError("SHA-256 özeti önceki sağlam kopyayla eşleşmiyor.")
                    return digest

                valid = False
                if not os.path.isfile(path):
                    for source in self.legacy_sources(relative):
                        if os.path.isfile(source) and not same_path(source, path):
                            try:
                                inspect(source)
                                os.makedirs(os.path.dirname(path), exist_ok=True)
                                copy_model(source, path)
                                if log:
                                    log(f"Eski yerel model kopyalandı: {relative}")
                                break
                            except InterruptedError:
                                raise
                            except Exception as error:
                                if log:
                                    log(f"Eski model kullanılamadı: {relative}: {error}")
                try:
                    digest = inspect(path)
                    valid = True
                except InterruptedError:
                    raise
                except Exception as error:
                    if os.path.isfile(path) and action != "repair":
                        raise ValueError(f"{relative}: {error}. Onar düğmesini kullanın.") from error
                    if action == "verify":
                        raise FileNotFoundError(f"{relative}: dosya eksik.") from error
                if not valid:
                    parsed = urlparse(url)
                    if parsed.scheme != "https" or parsed.hostname not in ("huggingface.co", "github.com", "raw.githubusercontent.com", "dl.fbaipublicfiles.com"):
                        raise ValueError("Model kaynağı desteklenmiyor.")
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if log:
                        log(f"İndiriliyor: {relative}")
                    try:
                        # Check structure/CRC before the previous file is replaced.
                        downloaded_digest = []
                        def validate_download(temporary):
                            validate_file(temporary, relative, cancelled, config=config)
                            digest = file_digest(temporary, cancelled)
                            expected = previous.get(relative, {}).get("sha256")
                            if expected and os.path.splitext(relative)[1].lower() in (".pt", ".pth", ".ckpt", ".bin") and digest != expected:
                                raise ValueError("İndirilen ağırlığın SHA-256 özeti sağlam kopyayla eşleşmiyor; mevcut dosya korundu.")
                            downloaded_digest.append(digest)
                        download_model(url, path, cancelled=cancelled,
                                       progress=lambda done, total: progress(relative, done, total) if progress else None,
                                       validate=validate_download)
                    except (HTTPError, URLError) as error:
                        raise RuntimeError(f"İndirme başarısız: {error}") from error
                    digest = downloaded_digest[0]
                stat = os.stat(path)
                checked[relative] = {"sha256": digest, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}

            try:
                if model_id in RVC_ASSETS:
                    for relative, url in RVC_ASSETS[model_id][1]:
                        asset_handler(url, self.path(relative))
                else:
                    from separator_backend import LocalSeparator
                    separator = LocalSeparator(model_file_dir=self.root, info_only=True, asset_handler=asset_handler)
                    separator.download_model_and_data(model_id)
                    del separator
                self.records[model_id] = {"files": checked, "schema_version": 1}
                self.save()
                if log:
                    log(f"Hazır: {catalog[model_id]}")
            except InterruptedError:
                raise
            except Exception as error:
                failures[model_id] = str(error)
                self.records[model_id] = {"files": {**previous, **checked}, "error": str(error)}
                self.save()
                if log:
                    log(f"HATA: {catalog[model_id]}: {error}")
        return failures
