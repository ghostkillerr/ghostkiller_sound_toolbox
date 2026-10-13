"""Bounded reader for the data-only FAISS formats used by RVC.

Never pass a user file to FAISS's generic native deserializer. The accepted
little-endian x64 layouts are FlatL2 and IVFFlatL2 with a FlatL2 quantizer and
ArrayInvertedLists. Unknown layouts fail closed. See docs/INFERENCE_RELEASE_FIXES.md.
"""
from dataclasses import dataclass
import os
import struct

import numpy as np


MAX_INDEX_BYTES = 2 * 1024**3
MAX_VECTORS = 10_000_000
MAX_LISTS = 65536
BLOCK_VECTORS = 1024


def available_memory():
    """Native memory sampling without another runtime dependency."""
    if os.name == "nt":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.available
    else:
        try:
            return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, AttributeError):
            pass
    # Failure to sample memory reduces the limit instead of allowing 2 GiB.
    return 512 * 1024**2


@dataclass(frozen=True)
class IndexInfo:
    kind: str
    dimension: int
    vectors: int
    nlist: int = 0
    nprobe: int = 0


class _Reader:
    def __init__(self, stream, limit):
        self.stream = stream
        self.size = os.fstat(stream.fileno()).st_size
        if not 45 <= self.size <= limit:
            raise ValueError("Index dosyası boyut sınırını aşıyor veya başlığı eksik.")

    def read(self, length):
        if length < 0 or length > self.size - self.stream.tell():
            raise ValueError("Index dosyası kesilmiş veya uzunluk alanı geçersiz.")
        result = self.stream.read(length)
        if len(result) != length:
            raise ValueError("Index dosyası işlem sırasında değişti veya kesildi.")
        return result

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.read(struct.calcsize("<" + fmt)))[0]

    def skip(self, length):
        if length < 0 or length > self.size - self.stream.tell():
            raise ValueError("Index dosyası kesilmiş veya uzunluk alanı geçersiz.")
        self.stream.seek(length, os.SEEK_CUR)

    def header(self, expected_dimension):
        dimension = self.number("i")
        total = self.number("q")
        self.read(16)  # historical dummy fields, not allocation counts
        trained = self.number("B")
        metric = self.number("i")
        if metric != 1:
            raise ValueError("FAISS indeksi L2 uzaklık metriği kullanmalıdır.")
        if trained != 1 or not 0 <= total <= MAX_VECTORS:
            raise ValueError("Index eğitilmemiş veya vektör sayısı sınırı geçersiz.")
        if not 1 <= dimension <= 4096:
            raise ValueError("Index özellik boyutu geçersiz.")
        if expected_dimension is None and dimension not in (256, 768):
            raise ValueError("RVC index özellik boyutu 256 veya 768 olmalıdır.")
        if expected_dimension is not None and dimension != expected_dimension:
            raise ValueError("FAISS indeksi seçilen ses modeliyle uyumlu değil.")
        if total * dimension * 4 > MAX_INDEX_BYTES:
            raise ValueError("Index vektörleri bellek sınırını aşıyor.")
        return dimension, total

    def floats(self, rows, dimension):
        block = np.frombuffer(self.read(rows * dimension * 4), dtype="<f4").reshape(rows, dimension)
        if not np.isfinite(block).all() or (np.abs(block) > 1e10).any():
            raise ValueError("Index vektörleri sonlu değil veya güvenli sayısal sınırı aşıyor.")
        return block

    def flat(self, expected_dimension, expected_total=None):
        tag = self.read(4)
        if tag not in (b"IxF2", b"IxFI", b"IxFl"):
            raise ValueError("Yalnız FlatL2 quantizer destekleniyor.")
        dimension, total = self.header(expected_dimension)
        if expected_total is not None and total != expected_total:
            raise ValueError("IVF merkez sayısı liste sayısıyla eşleşmiyor.")
        if tag != b"IxF2":
            raise ValueError("Yalnız FlatL2 index uzaklık türü destekleniyor.")
        if self.number("Q") != total * dimension:
            raise ValueError("FlatL2 vektör sayısı ile veri uzunluğu farklı.")
        start = self.stream.tell()
        for offset in range(0, total, BLOCK_VECTORS):
            self.floats(min(BLOCK_VECTORS, total - offset), dimension)
        return dimension, total, start


def _parse(stream, limit, expected_dimension):
    reader = _Reader(stream, limit)
    tag = reader.read(4)
    stream.seek(0)
    if tag in (b"IxF2", b"IxFI", b"IxFl"):
        dimension, total, start = reader.flat(expected_dimension)
        layout = (start,)
        info = IndexInfo("FlatL2", dimension, total)
    elif tag == b"IwFl":
        reader.read(4)
        dimension, total = reader.header(expected_dimension)
        nlist, nprobe = reader.number("Q"), reader.number("Q")
        if not 1 <= nlist <= MAX_LISTS or not 1 <= nprobe <= nlist:
            raise ValueError("IVF liste/probe sayısı geçersiz veya sınırı aşıyor.")
        _, quantizer_total, quantizer_start = reader.flat(dimension, nlist)
        map_kind, map_count = reader.number("B"), reader.number("Q")
        if map_kind not in (0, 1, 2) or map_count != (total if map_kind == 1 else 0):
            raise ValueError("Desteklenmeyen veya bozuk IVF direct-map alanı.")
        reader.skip(map_count * 8)
        if map_kind == 2:
            pair_count = reader.number("Q")
            if pair_count > total:
                raise ValueError("IVF direct-map boyutu geçersiz.")
            reader.skip(pair_count * 16)
        if reader.read(4) != b"ilar":
            raise ValueError("Yalnız veri içeren ArrayInvertedLists destekleniyor.")
        if reader.number("Q") != nlist or reader.number("Q") != dimension * 4:
            raise ValueError("IVF liste/vektör boyutu tutarsız.")
        mode, count = reader.read(4), reader.number("Q")
        sizes = [0] * nlist
        if mode == b"full" and count == nlist:
            sizes = [reader.number("Q") for _ in range(count)]
        elif mode == b"sprs" and count % 2 == 0 and count <= 2 * nlist:
            last = -1
            for _ in range(count // 2):
                list_id, size = reader.number("Q"), reader.number("Q")
                if not last < list_id < nlist or size == 0:
                    raise ValueError("IVF sparse listeleri yinelenmiş veya geçersiz.")
                sizes[list_id], last = size, list_id
        else:
            raise ValueError("IVF liste uzunluk tablosu desteklenmiyor veya bozuk.")
        if sum(sizes) != total:
            raise ValueError("IVF liste toplamı vektör sayısıyla eşleşmiyor.")
        seen = np.zeros(total, dtype=bool)
        lists = []
        for size in sizes:
            vector_start = stream.tell()
            for offset in range(0, size, BLOCK_VECTORS):
                reader.floats(min(BLOCK_VECTORS, size - offset), dimension)
            id_start = stream.tell()
            for offset in range(0, size, BLOCK_VECTORS):
                ids = np.frombuffer(reader.read(min(BLOCK_VECTORS, size - offset) * 8), dtype="<i8")
                if (ids < 0).any() or (ids >= total).any() or len(np.unique(ids)) != len(ids) or seen[ids].any():
                    raise ValueError("IVF vektör kimlikleri yinelenmiş veya RVC aralığı dışında.")
                seen[ids] = True
            lists.append((size, vector_start, id_start))
        layout = (quantizer_start, lists)
        info = IndexInfo("IVFFlatL2", dimension, total, nlist, nprobe)
    else:
        raise ValueError("Desteklenmeyen FAISS index türü. FlatL2 veya IVFFlatL2 seçin.")
    if stream.tell() != reader.size:
        raise ValueError("Index dosyasında beklenmeyen ek veri var.")
    return reader, info, layout


def inspect_index(path, expected_dimension=None, max_bytes=MAX_INDEX_BYTES):
    """Validate all lengths, values and IDs without calling native FAISS IO."""
    with open(path, "rb") as stream:
        return _parse(stream, min(MAX_INDEX_BYTES, max_bytes), expected_dimension)[1]


def load_index(path, expected_dimension=None, max_bytes=MAX_INDEX_BYTES):
    """Construct a native index from validated bounded data blocks.

    Re-reading blocks also validates their numeric values, so a file changed
    during validation is never forwarded to a native file parser.
    """
    import faiss
    available = available_memory()
    limit = min(MAX_INDEX_BYTES, max_bytes, max(0, int(available * .4)))
    with open(path, "rb") as stream:
        reader, info, layout = _parse(stream, limit, expected_dimension)
        dimension = info.dimension
        quantizer = faiss.IndexFlatL2(dimension)
        if info.kind == "FlatL2":
            stream.seek(layout[0])
            for offset in range(0, info.vectors, BLOCK_VECTORS):
                quantizer.add(reader.floats(min(BLOCK_VECTORS, info.vectors - offset), dimension))
            return quantizer
        stream.seek(layout[0])
        for offset in range(0, info.nlist, BLOCK_VECTORS):
            quantizer.add(reader.floats(min(BLOCK_VECTORS, info.nlist - offset), dimension))
        index = faiss.IndexIVFFlat(quantizer, dimension, info.nlist, faiss.METRIC_L2)
        seen = np.zeros(info.vectors, dtype=bool)
        for list_number, (size, vector_start, id_start) in enumerate(layout[1]):
            for offset in range(0, size, BLOCK_VECTORS):
                count = min(BLOCK_VECTORS, size - offset)
                stream.seek(vector_start + offset * dimension * 4)
                vectors = reader.floats(count, dimension)
                stream.seek(id_start + offset * 8)
                ids = np.frombuffer(reader.read(count * 8), dtype="<i8")
                if (ids < 0).any() or (ids >= info.vectors).any() or len(np.unique(ids)) != len(ids) or seen[ids].any():
                    raise ValueError("IVF vektör kimlikleri okuma sırasında değişti.")
                seen[ids] = True
                index.invlists.add_entries(list_number, count, faiss.swig_ptr(ids), faiss.swig_ptr(vectors.view(np.uint8)))
        index.is_trained = True
        index.ntotal = info.vectors
        index.nprobe = info.nprobe
        return index
