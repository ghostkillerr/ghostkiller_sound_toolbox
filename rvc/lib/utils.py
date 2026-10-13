import os
import librosa
import soundfile as sf
import numpy as np
from torch import nn

import logging
from transformers import HubertModel

logging.getLogger("fairseq").setLevel(logging.ERROR)
logging.getLogger("faiss.loader").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("torch").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

from app_runtime import model_directory, app_directory, download_model, copy_model
EMBEDDER_REVISION = "b81f9708367b124b29a47788e4c89b721166234f"
class HubertModelWithFinalProj(HubertModel):
    def __init__(self, config):
        super().__init__(config)
        self.final_proj = nn.Linear(config.hidden_size, config.classifier_proj_size)


def load_audio_infer(
    file,
    sample_rate,
    **kwargs,
):
    formant_shifting = kwargs.get("formant_shifting", False)
    try:
        file = file.strip(" ").strip('"').strip("\n").strip('"').strip(" ")
        if not os.path.isfile(file):
            raise FileNotFoundError(f"File not found: {file}")
        validate_audio_memory(file, sample_rate, kwargs.get("memory_output_rate", 48000))
        audio, sr = sf.read(file)
        if len(audio.shape) > 1:
            audio = librosa.to_mono(audio.T)
        if sr != sample_rate:
            audio = librosa.resample(
                audio, orig_sr=sr, target_sr=sample_rate, res_type="soxr_vhq"
            )
        if formant_shifting:
            formant_qfrency = kwargs.get("formant_qfrency", 0.8)
            formant_timbre = kwargs.get("formant_timbre", 0.8)

            from stftpitchshift import StftPitchShift

            pitchshifter = StftPitchShift(1024, 32, sample_rate)
            audio = pitchshifter.shiftpitch(
                audio,
                factors=1,
                quefrency=formant_qfrency * 1e-3,
                distortion=formant_timbre,
            )
    except Exception as error:
        raise RuntimeError(f"An error occurred loading the audio: {error}")
    return np.array(audio).flatten()


def validate_audio_memory(path, input_rate=16000, output_rate=48000):
    """Conservative whole-waveform CPU budget before allocating decoded audio.

    Source decode/mono, resampling/filter buffers, and synthesized chunks may
    overlap. This application still assembles the waveform in RAM; long files
    require sufficient memory even though pitch windows are bounded on GPU.
    """
    from rvc.infer.safe_index import available_memory
    info = sf.info(path)
    if info.frames < 1 or info.channels < 1 or info.samplerate < 1:
        raise ValueError("Ses dosyası başlığı boş veya geçersiz.")
    duration = info.frames / info.samplerate
    estimate = int(128 * 1024**2 + duration * 8 * (
        info.samplerate * (info.channels + 1) + input_rate * 4 + output_rate * 3))
    free = available_memory()
    if estimate > free * .6:
        raise ValueError(
            f"Ses dönüşümü için tahmini RAM ihtiyacı {estimate / 1024**3:.2f} GiB; "
            f"kullanılabilir RAM {free / 1024**3:.2f} GiB. Daha kısa bir kayıt seçin "
            "veya RAM kullanan diğer uygulamaları kapatın.")
    return estimate


def load_embedding(embedder_model, custom_embedder=None, allow_download=True, rvc_version=None):
    embedder_root = os.path.join(model_directory(), "embedders")
    embedding_list = {
        "contentvec": os.path.join(embedder_root, "contentvec"),
        "spin": os.path.join(embedder_root, "spin"),
        "spin-v2": os.path.join(embedder_root, "spin-v2"),
        "chinese-hubert-base": os.path.join(embedder_root, "chinese_hubert_base"),
        "japanese-hubert-base": os.path.join(embedder_root, "japanese_hubert_base"),
        "korean-hubert-base": os.path.join(embedder_root, "korean_hubert_base"),
    }

    online_embedders = {
        "contentvec": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/pytorch_model.bin",
        "spin": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/spin/pytorch_model.bin",
        "spin-v2": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/spin-v2/pytorch_model.bin",
        "chinese-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/chinese_hubert_base/pytorch_model.bin",
        "japanese-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/japanese_hubert_base/pytorch_model.bin",
        "korean-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/korean_hubert_base/pytorch_model.bin",
    }

    config_files = {
        "contentvec": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/config.json",
        "spin": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/spin/config.json",
        "spin-v2": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/spin-v2/config.json",
        "chinese-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/chinese_hubert_base/config.json",
        "japanese-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/japanese_hubert_base/config.json",
        "korean-hubert-base": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/korean_hubert_base/config.json",
    }

    online_embedders = {key: url.replace("/resolve/main/", f"/resolve/{EMBEDDER_REVISION}/") for key, url in online_embedders.items()}
    config_files = {key: url.replace("/resolve/main/", f"/resolve/{EMBEDDER_REVISION}/") for key, url in config_files.items()}

    if embedder_model == "custom":
        if custom_embedder and os.path.isdir(custom_embedder):
            model_path = custom_embedder
            validate_embedding_architecture(model_path, rvc_version)
            return HubertModelWithFinalProj.from_pretrained(model_path, local_files_only=not allow_download)
        else:
            logger.warning("Custom embedder not found: %r; using contentvec", custom_embedder)
            embedder_model = 'contentvec'
    if embedder_model not in embedding_list:
        raise ValueError(f"Desteklenmeyen embedder: {embedder_model}")
    model_path = embedding_list[embedder_model]
    os.makedirs(model_path, exist_ok=True)
    # Config must exist and be trusted before inspecting the weight schema.
    for filename, urls in (("config.json", config_files), ("pytorch_model.bin", online_embedders)):
        target = os.path.join(model_path, filename)
        def validate_asset(candidate):
            if embedder_model != "contentvec":
                return
            import json
            from model_manager import PUBLISHED_ASSET_HASHES, file_digest, validate_file
            relative = f"embedders/contentvec/{filename}"
            if file_digest(candidate) != PUBLISHED_ASSET_HASHES[relative]:
                raise ValueError("ContentVec dosyası yayıncının sabit SHA-256 özetiyle eşleşmiyor.")
            config = None
            if filename == "pytorch_model.bin":
                with open(os.path.join(model_path, "config.json"), encoding="utf-8") as stream:
                    config = json.load(stream)
            validate_file(candidate, relative, config=config)
        if not os.path.isfile(target) or not os.path.getsize(target):
            if not allow_download:
                raise FileNotFoundError(f"Eksik embedder dosyası: {filename}. Ayarlar sekmesinden indirin veya onarın.")
            legacy = os.path.join(app_directory(), 'rvc', 'models', 'embedders', os.path.basename(model_path), filename)
            if os.path.isfile(legacy) and os.path.getsize(legacy):
                validate_asset(legacy)
                copy_model(legacy, target)
                continue
            url = urls[embedder_model]
            logger.info("Downloading %s to %r", url, model_path)
            download_model(url, target, validate=validate_asset)
        elif allow_download:
            # This standalone API also verifies existing helper assets. The GUI
            # already uses ModelManager.require_ready plus a bounded job cache.
            validate_asset(target)

    validate_embedding_architecture(model_path, rvc_version)
    models = HubertModelWithFinalProj.from_pretrained(model_path, local_files_only=not allow_download)
    return models


def validate_embedding_architecture(folder, rvc_version=None):
    """Bound helper allocation and enforce the RVC 50-fps encoder contract."""
    import json
    import math
    import torch
    from transformers import HubertConfig
    from model_manager import validate_metadata
    from rvc.infer.model_validation import validate_meta_network, checkpoint_archive_precheck
    from rvc.infer.safe_index import available_memory
    config_path = os.path.join(folder, "config.json")
    if not 1 <= os.path.getsize(config_path) <= 1024**2:
        raise ValueError("Embedder config.json boyut sınırını aşıyor veya boş.")
    with open(config_path, encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("Embedder yapılandırması JSON nesnesi olmalıdır.")
    validate_metadata(config, "embedders/contentvec/config.json")
    if ((rvc_version == "v2" and config["hidden_size"] != 768) or
            (rvc_version == "v1" and config["classifier_proj_size"] != 256)):
        raise ValueError("Embedder özellik boyutu seçilen RVC sürümüyle uyumlu değil.")
    if math.prod(config["conv_stride"]) != 320:
        raise ValueError("Embedder 16 kHz girdide 50 fps özellik üretmelidir.")
    with torch.device("meta"):
        network = HubertModelWithFinalProj(HubertConfig(**config))
        required = validate_meta_network(network)
    del network
    free = available_memory()
    if required * 2 > free * .6:
        raise ValueError("Embedder ağını oluşturmak için kullanılabilir RAM yetersiz.")
    binary = os.path.join(folder, "pytorch_model.bin")
    safe = os.path.join(folder, "model.safetensors")
    if os.path.isfile(safe):
        if not 1 <= os.path.getsize(safe) <= min(2 * 1024**3, free * .4):
            raise ValueError("Embedder safetensors boyutu RAM sınırını aşıyor.")
    elif os.path.isfile(binary):
        checkpoint_archive_precheck(binary, available_ram=free)
    else:
        raise ValueError("Embedder için tek pytorch_model.bin veya model.safetensors ağırlığı gerekir; parçalı ağırlıklar desteklenmiyor.")
    return config
