"""Train-only exact retrieval index: all vectors, no quantization or clustering."""
from pathlib import Path
import os
import numpy as np
from training.dataset import check_cancel


def build_index(job, dataset, threads, emit):
    import faiss
    faiss.omp_set_num_threads(threads)
    paths = [p["features"] for p in dataset["pieces"] if p["split"] == "train"]
    train_paths = {str(Path(p).resolve()) for p in paths}
    evaluation_paths = {str(Path(p['features']).resolve()) for p in dataset['pieces'] if p['split']!='train'}
    if train_paths & evaluation_paths:
        raise ValueError("Aynı özellik dosyası eğitim ve değerlendirmede kullanılıyor; index oluşturulmadı.")
    if len(train_paths)!=len(paths):
        raise ValueError("Index girdilerinde yinelenen eğitim özelliği var.")
    count = sum(len(np.load(p, mmap_mode="r", allow_pickle=False)) for p in paths)
    if count < 1:
        raise ValueError("Index için eğitim özellikleri bulunamadı.")
    # Quality-first: exact nearest neighbors. Flat avoids IVF recall tradeoffs,
    # training-sample selection, KMeans reduction and quantization entirely.
    index = faiss.IndexFlatL2(768)
    added = 0
    for path in paths:
        data = np.load(path,mmap_mode="r",allow_pickle=False)
        for start in range(0,len(data),4096):
            check_cancel(job)
            block = np.ascontiguousarray(data[start:start+4096],dtype="float32")
            if not np.isfinite(block).all():
                raise ValueError("Index özellikleri geçersiz.")
            index.add(block)
            added += len(block)
            emit("index",message=f"Index: {added}/{count} özellik",percent=100*added/count)
    path = Path(job)/"voice.index"
    temporary = str(path)+".part"
    try:
        faiss.write_index(index,temporary)
        check_cancel(job)
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return str(path), count
