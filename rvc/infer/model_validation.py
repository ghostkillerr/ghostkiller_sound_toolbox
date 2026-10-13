"""Architecture limits before constructing networks from imported checkpoints."""
import math
import os
import struct
import zipfile

import torch


MAX_MODEL_PARAMETERS = 200_000_000


def _zip_directory_budget(stream, size, maximum_members):
    """Count central headers before ZipFile can allocate an unbounded list."""
    length = min(size, 65557)
    stream.seek(size - length)
    tail = stream.read(length)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError("PTH ZIP bitiş kaydı eksik.")
    _, disk, central_disk, disk_count, count, central_size, central_offset, comment = struct.unpack(
        "<4s4H2IH", tail[offset:offset + 22])
    if offset + 22 + comment != len(tail) or disk or central_disk or disk_count != count:
        raise ValueError("Çok diskli veya ek verili PTH ZIP desteklenmiyor.")
    eocd_offset = size - length + offset
    if eocd_offset >= 20:
        stream.seek(eocd_offset - 20)
        locator = stream.read(20)
        if locator[:4] == b"PK\x06\x07":
            _, zip_disk, zip_offset, disks = struct.unpack("<4sIQI", locator)
            if zip_disk or disks != 1 or not 0 <= zip_offset <= eocd_offset - 76:
                raise ValueError("PTH ZIP64 konumu geçersiz.")
            stream.seek(zip_offset)
            record = stream.read(56)
            if len(record) != 56 or record[:4] != b"PK\x06\x06":
                raise ValueError("PTH ZIP64 bitiş kaydı geçersiz.")
            _, record_size, _, _, disk, central_disk, disk_count, count, central_size, central_offset = struct.unpack("<4sQ2H2I4Q", record)
            if not 44 <= record_size <= 4096 or disk or central_disk or disk_count != count:
                raise ValueError("PTH ZIP64 sayaçları geçersiz.")
    if not 1 <= count <= maximum_members or central_size > 32 * 1024**2:
        raise ValueError("PTH ZIP üye/metadata sayısı sınırı aşıyor.")
    if central_offset < 0 or central_offset + central_size > eocd_offset:
        raise ValueError("PTH ZIP merkezi dizin sınırı geçersiz.")
    stream.seek(central_offset)
    end, actual = central_offset + central_size, 0
    while stream.tell() < end:
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ValueError("PTH ZIP merkezi dizin başlığı geçersiz.")
        name, extra, comment = struct.unpack_from("<3H", header, 28)
        if not 1 <= name <= 1024 or extra > 4096 or comment > 1024:
            raise ValueError("PTH ZIP üye metadata boyutu sınırı aşıyor.")
        length = name + extra + comment
        if length > end - stream.tell():
            raise ValueError("PTH ZIP merkezi dizini kesilmiş.")
        stream.seek(length, os.SEEK_CUR)
        actual += 1
        if actual > maximum_members:
            raise ValueError("PTH ZIP gerçek üye sayısı sınırı aşıyor.")
    if actual != count:
        raise ValueError("PTH ZIP üye sayacı ile merkezi dizin eşleşmiyor.")


def checkpoint_archive_precheck(path, max_file_bytes=2 * 1024**3,
                                max_expanded_bytes=4 * 1024**3,
                                available_ram=None, allow_legacy=False):
    """Bound checkpoint IO before torch.load; return mmap eligibility.

    User RVC accepts new PyTorch stored ZIP only. A managed asset loader may
    opt into an already publisher-verified legacy asset separately; this
    function cannot bound legacy pickle's declared storage allocations.
    """
    from rvc.infer.safe_index import available_memory
    free = available_memory() if available_ram is None else available_ram
    with open(path, "rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if not 1 <= size <= min(max_file_bytes, int(free * .4)):
            raise ValueError("PTH dosyası boyut veya kullanılabilir RAM sınırını aşıyor.")
        if stream.read(4) != b"PK\x03\x04":
            if allow_legacy:
                return False
            raise ValueError("Eski ZIP olmayan PTH desteklenmiyor. Modeli güvenilen ortamda güncel torch.save ile RVC olarak dışa aktarın.")
        _zip_directory_budget(stream, size, 20000)
        stream.seek(0)
        try:
            with zipfile.ZipFile(stream) as archive:
                expanded, seen, pickles = 0, set(), 0
                for member in archive.infolist():
                    name = member.filename
                    if name in seen or member.flag_bits & 1 or member.compress_type != zipfile.ZIP_STORED:
                        raise ValueError("PTH ZIP yinelenen, şifreli veya sıkıştırılmış üye içeriyor; standart torch.save ZIP gereklidir.")
                    seen.add(name)
                    expanded += member.file_size
                    if expanded > min(max_expanded_bytes, int(free * .6)):
                        raise ValueError("PTH ZIP açılmış veri boyutu RAM sınırını aşıyor.")
                    if name.endswith("/data.pkl") or name == "data.pkl":
                        pickles += 1
                        if member.file_size > 16 * 1024**2:
                            raise ValueError("PTH tensor metadata boyutu sınırı aşıyor.")
                if pickles != 1:
                    raise ValueError("PTH ZIP tensor metadata kaydı eksik veya yinelenmiş.")
        except zipfile.BadZipFile as error:
            raise ValueError("PTH ZIP arşivi bozuk.") from error
    return True


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"RVC model {name} alanı {low}..{high} sınırında tamsayı olmalıdır.")


def _list(value, low, high, length, name, odd=False):
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= length:
        raise ValueError(f"RVC model {name} liste boyutu geçersiz.")
    for item in value:
        _integer(item, low, high, name)
        if odd and item % 2 != 1:
            raise ValueError(f"RVC model {name} tek sayı olmalıdır.")


def validate_architecture(config, weights):
    """Return a safe copy, keeping standard v1/v2 and vocoder architectures.

    Generous structural bounds limit Python/meta construction work. A second
    exact parameter-count limit is enforced on a meta model before real tensors
    are allocated; no architecture is silently reduced to fit the machine.
    """
    if not isinstance(config, (list, tuple)) or len(config) != 18:
        raise ValueError("Geçersiz RVC model yapılandırması.")
    if not isinstance(weights, dict) or not 1 <= len(weights) <= 10000:
        raise ValueError("RVC model ağırlık tablosu geçersiz veya sınırı aşıyor.")
    embedding = weights.get("emb_g.weight")
    if not isinstance(embedding, torch.Tensor) or embedding.layout != torch.strided or embedding.ndim != 2:
        raise ValueError("RVC model konuşmacı ağırlığı eksik veya şekli geçersiz.")
    config = list(config)
    config[15] = embedding.shape[0]
    for position, low, high, name in (
        (0, 1, 4097, "spec_channels"), (1, 1, 16384, "segment_size"),
        (2, 2, 1024, "inter_channels"), (3, 2, 1024, "hidden_channels"),
        (4, 2, 4096, "filter_channels"), (5, 1, 32, "n_heads"),
        (6, 1, 24, "n_layers"), (7, 1, 31, "kernel_size"),
        (13, 16, 2048, "upsample_initial_channel"),
        (15, 1, 4096, "speaker_count"), (16, 1, 1024, "gin_channels"),
        (17, 16000, 96000, "sample_rate"),
    ):
        _integer(config[position], low, high, name)
    if config[2] % 2 or config[3] % config[5] or config[7] % 2 != 1:
        raise ValueError("RVC kanal, attention head veya kernel boyutları uyumsuz.")
    if config[17] % 100:
        raise ValueError("RVC model örnekleme hızı 100 fps sözleşmesiyle uyumsuz.")
    if embedding.shape[1] != config[16]:
        raise ValueError("RVC konuşmacı ve gin_channels boyutları eşleşmiyor.")
    if type(config[8]) not in (int, float) or not math.isfinite(config[8]) or not 0 <= config[8] < 1:
        raise ValueError("RVC dropout alanı geçersiz.")
    if config[9] not in ("1", "2"):
        raise ValueError("RVC resblock alanı desteklenmiyor.")
    _list(config[10], 1, 31, 8, "resblock_kernel_sizes", odd=True)
    if not isinstance(config[11], (list, tuple)) or len(config[11]) != len(config[10]):
        raise ValueError("RVC residual kernel/dilation liste sayıları eşleşmiyor.")
    for dilations in config[11]:
        _list(dilations, 1, 128, 8, "resblock_dilation_sizes")
    _list(config[12], 1, 32, 8, "upsample_rates")
    _list(config[14], 1, 128, 8, "upsample_kernel_sizes")
    if len(config[12]) != len(config[14]) or math.prod(config[12]) != config[17] // 100:
        raise ValueError("RVC upsample listeleri veya toplam oranı örnekleme hızıyla eşleşmiyor.")
    if config[13] // (2 ** len(config[12])) < 1:
        raise ValueError("RVC upsample katmanları için kanal sayısı yetersiz.")
    for rate, kernel in zip(config[12], config[14]):
        if kernel < rate or (kernel - rate) % 2:
            raise ValueError("RVC upsample kernel ve oranı uyumsuz.")
    for name, value in weights.items():
        if not isinstance(name, str) or not isinstance(value, torch.Tensor) or value.layout != torch.strided:
            raise ValueError("RVC ağırlıkları yoğun tensorlerden oluşmalıdır.")
        if value.numel() > MAX_MODEL_PARAMETERS or value.ndim > 6:
            raise ValueError("RVC ağırlık tensorü boyut sınırını aşıyor.")
    return config


def validate_meta_network(network):
    count = sum(value.numel() for value in network.parameters())
    if count > MAX_MODEL_PARAMETERS:
        raise ValueError("RVC ağı parametre bellek sınırını aşıyor; bu model desteklenmiyor.")
    return count * 4


def validate_weights(network, weights):
    """Match shapes on meta tensors and scan finite values in bounded blocks."""
    normalized = {}
    for name, value in weights.items():
        key = name
        if name.endswith(".weight_g"):
            key = name[:-len("weight_g")] + "parametrizations.weight.original0"
        elif name.endswith(".weight_v"):
            key = name[:-len("weight_v")] + "parametrizations.weight.original1"
        if key in normalized:
            raise ValueError("RVC ağırlık adları aynı parametreye birden fazla kez bağlanıyor.")
        normalized[key] = value
        if not value.is_contiguous():
            raise ValueError("RVC ağırlık tensorleri bitişik bellek düzeninde olmalıdır.")
        flat = value.view(-1)
        for offset in range(0, flat.numel(), 65536):
            if not torch.isfinite(flat[offset:offset + 65536]).all().item():
                raise ValueError(f"RVC ağırlığı sonlu değil: {name}")
    for name, value in network.state_dict().items():
        supplied = normalized.get(name)
        if supplied is None:
            raise ValueError(f"RVC model ağırlıkları eksik: {name}")
        if tuple(supplied.shape) != tuple(value.shape):
            raise ValueError(f"RVC model ağırlığı şekli uyumsuz: {name}")
