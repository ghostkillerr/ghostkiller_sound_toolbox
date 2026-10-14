"""Explicit model installation, offline integrity checks and atomic repair."""
import gc
import hashlib
import json
import os
import zipfile
from copy import deepcopy
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from app_runtime import app_directory, model_directory, download_model, copy_model, same_path, configure_runtime_cache


ASSET_COMMIT = "b81f9708367b124b29a47788e4c89b721166234f"
BASE_URL = f"https://huggingface.co/IAHispano/Applio/resolve/{ASSET_COMMIT}/Resources"
PUBLISHED_ASSET_HASHES = {
    "embedders/contentvec/config.json": "2ddde063b795d38d9051a7215a092fecf4cfe148b54251e38de51d88d356898b",
    "embedders/contentvec/pytorch_model.bin": "d8dd400e054ddf4e6be75dab5a2549db748cc99e756a097c496c099f65a4854e",
    "predictors/rmvpe.pt": "6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193",
}
SCHEMA_VERSION = 2
# Reviewed bytes from the official HTTPS release (GitHub provides no digest
# for these older assets). Provenance is recorded separately in docs/.
REVIEWED_SEPARATOR_HASHES = {
    'UVR-DeEcho-DeReverb.pth':'e644028ec82865dc0fe082bc6fea85a43f7c71cfe375caee2da2d154aa661ee7',
    'UVR-DeNoise.pth':'5addf43ece5bddd18da9f575a02d7ffdb32342414e6ad7ac8d1dd7a04138a628',
}
ROFORMER_CONFIGS = {
    'model_bs_roformer_ep_317_sdr_12.9755.ckpt':'model_bs_roformer_ep_317_sdr_12.9755.yaml',
    'melband_roformer_inst_v2.ckpt':'config_melbandroformer_inst_v2.yaml',
    'mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt':'mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956_config.yaml',
}
RVC_ASSETS = {
    "contentvec": ("AI Cover: ses özellikleri (ContentVec)", (
        ("embedders/contentvec/config.json", f"{BASE_URL}/embedders/contentvec/config.json"),
        ("embedders/contentvec/pytorch_model.bin", f"{BASE_URL}/embedders/contentvec/pytorch_model.bin"),
    )),
    "rmvpe": ("AI Cover: nota algılama (RMVPE)", (
        ("predictors/rmvpe.pt", f"{BASE_URL}/predictors/rmvpe.pt"),
    )),
}

# Training weights are prepared only in Settings; training never downloads them.
for _rate in (32, 40, 48):
    RVC_ASSETS[f"training_v2_{_rate}k"] = (
        f"Model eğitimi: RVC V2 {_rate} kHz başlangıç G/D ağırlıkları",
        tuple((f"pretrained/v2/f0{kind}{_rate}k.pth",
               f"https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/e6d0c1a17da07c33557852f9dfa2bd44cc75737d/pretrained_v2/f0{kind}{_rate}k.pth")
              for kind in ("G", "D")),
    )

PUBLISHED_TRAINING_HASHES = {
    "pretrained/v2/f0D32k.pth": "bd7134e7793674c85474d5145d2d982e3c5d8124fc7bb6c20f710ed65808fa8a",
    "pretrained/v2/f0D40k.pth": "6b6ab091e70801b28e3f41f335f2fc5f3f35c75b39ae2628d419644ec2b0fa09",
    "pretrained/v2/f0D48k.pth": "2269b73c7a4cf34da09aea99274dabf99b2ddb8a42cbfb065fb3c0aa9a2fc748",
    "pretrained/v2/f0G32k.pth": "2332611297b8d88c7436de8f17ef5f07a2119353e962cd93cda5806d59a1133d",
    "pretrained/v2/f0G40k.pth": "3b2c44035e782c4b14ddc0bede9e2f4a724d025cd073f736d4f43708453adfcb",
    "pretrained/v2/f0G48k.pth": "b5d51f589cc3632d4eae36a315b4179397695042edc01d15312e1bddc2b764a4",
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


def validate_separator_model_config(fields):
    if not isinstance(fields,dict):
        raise ValueError('Ayrıştırma ağ yapılandırması geçersiz.')
    limits = {'dim':4096,'depth':128,'heads':128,'dim_head':4096,
              'stft_n_fft':65536,'stft_hop_length':65536,'stft_win_length':65536,
              'num_bands':2048,'num_stems':16,'mask_estimator_depth':128,
              'time_transformer_depth':128,'freq_transformer_depth':128,
              'linear_transformer_depth':128,'num_residual_streams':16}
    for key,limit in limits.items():
        if key in fields:
            lower = 0 if key=='linear_transformer_depth' else 1
            if type(fields[key]) is not int or not lower <= fields[key] <= limit:
                raise ValueError(f'Ayrıştırma ağ boyutu destek sınırını aşıyor: {key}')
    bands = fields.get('freqs_per_bands',())
    if (not isinstance(bands,(list,tuple)) or len(bands)>2048 or
            any(type(item) is not int or not 1 <= item <= 65536 for item in bands)):
        raise ValueError('Ayrıştırma frekans bantları geçersiz.')
    transforms = sum(fields.get(key,default) for key,default in
                     (('time_transformer_depth',1),('freq_transformer_depth',1),('linear_transformer_depth',0)))
    masks = fields.get('num_bands',len(bands) or 1)*fields.get('num_stems',1)*fields.get('mask_estimator_depth',2)
    if fields.get('depth',1)*max(1,transforms)>512 or masks>8192:
        raise ValueError('Ayrıştırma ağının birleşik katman/bant sayısı destek sınırını aşıyor.')
    for key in ('mask_estimator_expansion_factor','mlp_expansion_factor'):
        if key in fields and (type(fields[key]) not in (int,float) or not 1 <= fields[key] <= 16):
            raise ValueError(f'Ayrıştırma genişletme katsayısı geçersiz: {key}')
    resolutions = fields.get('multi_stft_resolutions_window_sizes',())
    if (not isinstance(resolutions,(list,tuple)) or len(resolutions)>16 or
            any(type(item) is not int or not 1 <= item <= 131072 for item in resolutions)):
        raise ValueError('Ayrıştırma STFT çözünürlük listesi destek sınırını aşıyor.')


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
        limits = {'hidden_size':4096,'intermediate_size':65536,'num_hidden_layers':96,
                  'num_attention_heads':128,'classifier_proj_size':4096}
        if any(value[key] > limit for key,limit in limits.items()) or any(
                len(items)>16 or any(item>4096 for item in items) for items in arrays):
            raise ValueError('ContentVec yapılandırması desteklenen ağ boyutu sınırlarını aşıyor.')
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
        validate_separator_model_config(value['model'])
        if (value['audio']['chunk_size']>24_000_000 or value['audio']['num_channels']>8 or
                not 8000 <= value['audio']['sample_rate'] <= 192000 or
                value['inference']['batch_size']>64 or value['inference']['num_overlap']>128):
            raise ValueError('Ayrıştırma ses/çıkarım boyutları destek sınırlarını aşıyor.')
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
    elif relative.startswith('pretrained/v2/f0'):
        from training.config import architecture
        from training.engine import model_pair
        name = os.path.basename(relative)
        rate = int(name[3:-5]) * 1000
        with torch.device('meta'):
            generator, discriminator = model_pair(architecture(rate))
        expected = (generator if name.startswith('f0G') else discriminator).state_dict()
        from training.storage import map_legacy_weights
        weights = map_legacy_weights(weights)
        if name.startswith('f0G') and torch.is_tensor(weights.get('emb_g.weight')):
            weights['emb_g.weight'] = weights['emb_g.weight'][:1]
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
        if name.endswith('.ckpt') and config is not None:
            fields = config.get('model',config)
            validate_separator_model_config(fields)
            if 'num_bands' in fields:
                from audio_separator.separator.uvr_lib_v5.roformer.mel_band_roformer import MelBandRoformer as Network
            elif 'freqs_per_bands' in fields:
                from audio_separator.separator.uvr_lib_v5.roformer.bs_roformer import BSRoformer as Network
            else:
                raise ValueError('RoFormer yapılandırması ağ türünü belirtmiyor.')
            with torch.device('meta'):
                expected = Network(**fields).state_dict()
            if sum(tensor.numel() for tensor in expected.values())>500_000_000:
                raise ValueError('Ayrıştırma ağının toplam parametre sayısı destek sınırını aşıyor.')
        elif name in ('UVR-DeEcho-DeReverb.pth','UVR-DeNoise.pth'):
            from audio_separator.separator.uvr_lib_v5.vr_network.nets_new import CascadedNet
            out = weights.get('out.weight')
            dense = weights.get('stg3_full_band_net.lstm_dec2.dense.0.weight')
            if not torch.is_tensor(out) or out.ndim!=4 or not torch.is_tensor(dense) or dense.ndim!=2:
                raise ValueError('UVR ağ boyutlarını belirleyen ağırlıklar eksik veya uyumsuz.')
            channels, bins, recurrent = out.shape[1], dense.shape[0], dense.shape[1]
            # VR 5.1 metadata also uses 16-channel denoise and 48-channel models.
            if channels not in (16,32,48,64) or not 1 <= bins <= 2048 or recurrent not in (64,128):
                raise ValueError('UVR ağ boyutları desteklenmiyor.')
            with torch.device('meta'):
                expected = CascadedNet(bins*4,218409 if channels==64 else 56817,nout=channels,nout_lstm=recurrent).state_dict()
        else:
            raise ValueError('RoFormer tam ağırlık kontrolü için eşleşen yapılandırma gerekli.')
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
        from rvc.infer.model_validation import checkpoint_archive_precheck
        relative = relative.replace('\\','/')
        trusted_digest = (PUBLISHED_ASSET_HASHES.get(relative) or PUBLISHED_TRAINING_HASHES.get(relative)
                          or REVIEWED_SEPARATOR_HASHES.get(relative))
        if trusted_digest and file_digest(path,cancelled) != trusted_digest:
            raise ValueError('Model dosyası sabit SHA-256 kaynak kimliğiyle eşleşmiyor.')
        use_mmap = checkpoint_archive_precheck(path,allow_legacy=bool(trusted_digest))
        if use_mmap:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    with archive.open(member) as stream:
                        while stream.read(1024 * 1024):
                            if cancelled and cancelled():
                                raise InterruptedError("Dosya kontrolü iptal edildi.")
        import torch
        value = torch.load(path, map_location="cpu", weights_only=True, mmap=use_mmap)
        if not isinstance(value, dict) or not value:
            raise ValueError("Model ağırlıkları geçersiz.")
        weights = value.get("state_dict")
        if not isinstance(weights, dict):
            weights = value.get("weight")
        if not isinstance(weights, dict):
            weights = value.get("model")
        if not isinstance(weights, dict):
            weights = value
        if not isinstance(weights, dict) or not any(torch.is_tensor(tensor) and tensor.numel() for tensor in weights.values()):
            raise ValueError("Model dosyasında kullanılabilir ağırlık bulunamadı.")
        trusted_rmvpe = None
        for key,tensor in weights.items():
            if torch.is_tensor(tensor):
                if tensor.device.type=='meta':
                    raise ValueError('Model dosyasında gerçek ağırlık verisi bulunmuyor.')
                if tensor.is_floating_point() or tensor.is_complex():
                    flat = tensor.reshape(-1)
                    for start in range(0,tensor.numel(),65536):
                        if cancelled and cancelled():
                            raise InterruptedError('Dosya kontrolü iptal edildi.')
                        if not torch.isfinite(flat[start:start+65536]).all().item():
                            # The pinned publisher cast BN's unused evaluation counters
                            # to FP16, overflowing positive counts. Never exempt learned
                            # weights, running statistics, NaNs, or untrusted files.
                            if (relative.replace('\\', '/') == 'predictors/rmvpe.pt' and
                                    isinstance(key,str) and key.endswith('.num_batches_tracked') and
                                    tensor.ndim == 0 and tensor.is_floating_point() and
                                    torch.isposinf(tensor).item()):
                                if trusted_rmvpe is None:
                                    trusted_rmvpe = file_digest(path,cancelled) == PUBLISHED_ASSET_HASHES.get('predictors/rmvpe.pt')
                                if trusted_rmvpe:
                                    continue
                            raise ValueError(f'Model ağırlığında NaN veya sonsuz değer var: {key}')
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
        self._records_snapshot = deepcopy(self.records)

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
            if record.get('schema_version') != SCHEMA_VERSION:
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

    def save(self, model_id=None):
        from registry_store import registry_lock
        from app_settings import write_json_atomic
        with registry_lock(self.manifest_path):
            existing = {}
            try:
                with open(self.manifest_path,encoding='utf-8') as stream:
                    value = json.load(stream)
                if value.get('version')==1 and isinstance(value.get('models'),dict):
                    existing = value['models']
            except (OSError,ValueError,AttributeError):
                pass  # Reverification rebuilds this derived cache; model weights are untouched.
            if model_id is None:
                changes = {key:value for key,value in self.records.items() if self._records_snapshot.get(key)!=value}
                removed = set(self._records_snapshot)-set(self.records)
                for key in set(changes)|removed:
                    if existing.get(key)!=self._records_snapshot.get(key):
                        raise ValueError(f"{key}: bütünlük kaydı başka işlemde değişti; yeniden kontrol edin.")
                for key in removed:
                    existing.pop(key,None)
                existing.update(changes)
            else:
                existing[model_id] = self.records[model_id]
            write_json_atomic(self.manifest_path,{"version":1,"models":existing})
            self.records = existing
            self._records_snapshot = deepcopy(existing)

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
                if relative in ROFORMER_CONFIGS:
                    config_name = ROFORMER_CONFIGS[relative]
                    config_path = self.path(config_name)
                    try:
                        asset_handler(f'https://github.com/nomadkaraoke/python-audio-separator/releases/download/model-configs/{config_name}',config_path)
                    except RuntimeError:
                        asset_handler(f'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/mdx_model_data/mdx_c_configs/{config_name}',config_path)
                    import yaml
                    with open(config_path,encoding='utf-8') as stream:
                        config = yaml.load(stream,Loader=yaml.FullLoader)

                def inspect(candidate):
                    if progress:
                        progress(f"Kontrol: {relative}", 0, 0)
                    validate_file(candidate, relative, cancelled, config=config)
                    digest = file_digest(candidate, cancelled)
                    published = PUBLISHED_ASSET_HASHES.get(relative)
                    if published and digest != published:
                        raise ValueError('Yardımcı model yayıncının sabit SHA-256 özetiyle eşleşmiyor.')
                    if relative in PUBLISHED_TRAINING_HASHES and digest != PUBLISHED_TRAINING_HASHES[relative]:
                        raise ValueError("Eğitim ağırlığı yayıncının sabit SHA-256 özetiyle eşleşmiyor.")
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
                            published = PUBLISHED_ASSET_HASHES.get(relative)
                            if published and digest != published:
                                raise ValueError('İndirilen yardımcı model yayıncının SHA-256 özetiyle eşleşmiyor.')
                            if relative in PUBLISHED_TRAINING_HASHES and digest != PUBLISHED_TRAINING_HASHES[relative]:
                                raise ValueError("İndirilen eğitim ağırlığı yayıncının SHA-256 özetiyle eşleşmiyor.")
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
                self.records[model_id] = {"files": checked, "schema_version": SCHEMA_VERSION}
                self.save(model_id)
                if log:
                    log(f"Hazır: {catalog[model_id]}")
            except InterruptedError:
                raise
            except (Exception, SystemExit) as error:
                failures[model_id] = str(error)
                self.records[model_id] = {"files": {**previous, **checked}, "error": str(error)}
                self.save(model_id)
                if log:
                    log(f"HATA: {catalog[model_id]}: {error}")
        return failures
