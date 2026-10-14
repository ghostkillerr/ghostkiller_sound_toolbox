"""Stream high quality decoded audio to disk, split BEFORE overlapping segments."""
from pathlib import Path
import json
import math
import os
import random
import shutil
import subprocess
from app_settings import write_json_atomic
from model_manager import file_digest
from app_runtime import ffmpeg_executable


def check_cancel(job):
    if (Path(job) / "cancel.request").exists():
        raise InterruptedError("Eğitim iptal edildi; son tutarlı kontrol noktası korunuyor.")


def decode(source, target, rate, job):
    """FFmpeg performs bounded streaming decode; no entire recording in memory."""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    command = [ffmpeg_executable(), "-nostdin", "-v", "error", "-y", "-i", str(source),
               "-vn", "-ac", "1", "-af", f"aresample={rate}:resampler=soxr:precision=28",
               "-c:a", "pcm_f32le", str(target)]
    log_path = Path(job) / "decode.log"
    with log_path.open("w", encoding="utf-8") as errors:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors,
                                   creationflags=creationflags)
        try:
            while process.poll() is None:
                check_cancel(job)
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            if process.returncode:
                raise RuntimeError("Ses çözümlenemedi: " + log_path.read_text(encoding="utf-8", errors="replace")[-2000:])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def source_splits(sources, fraction, seed, cancelled=None, groups=()):
    """Group identical recordings by SHA256 to prevent duplicate holdout leakage."""
    if groups and len(groups)!=len(sources):
        raise ValueError("Kayıt grupları dosyalarla eşleşmiyor.")
    unique, group_members = {}, {}
    for index, source in enumerate(sources):
        digest = file_digest(source, cancelled)
        unique.setdefault(digest, str(Path(source).resolve()))
        group = groups[index].strip() if groups else ""
        # Untagged distinct files are separate groups; exact copies link manual groups.
        key = ("manual",group) if group else ("hash",digest)
        group_members.setdefault(key,set()).add(digest)
    clusters = []
    for members in group_members.values():
        linked = [cluster for cluster in clusters if cluster & members]
        merged = set(members)
        for cluster in linked:
            merged.update(cluster)
            clusters.remove(cluster)
        clusters.append(merged)
    random.Random(seed).shuffle(clusters)
    count = max(1, round(len(clusters) * fraction)) if len(clusters) > 1 else 0
    rows = [{"path":unique[digest],"sha256":digest,"group_id":str(i)}
            for i,cluster in enumerate(clusters) for digest in sorted(cluster)]
    for i, row in enumerate(rows):
        row["split"] = "holdout" if int(row["group_id"]) < count else "train"
    return rows


def segment_extent(frames, segment, step, minimum):
    """Count precisely what prepare() keeps, without enumerating tiny strides."""
    if step <= 0:
        raise ValueError("Örtüşme sonrası ilerleme en az bir ses örneği olmalı.")
    count = max(0, (frames-minimum)//step+1)
    full = min(count, max(0, (frames-segment)//step+1))
    tail = count-full
    saved_frames = full*segment + tail*frames-step*(full+count-1)*tail//2
    return count, saved_frames


def estimate_storage(frames, options, single_source=False, checkpoint_bytes=2*1024**3):
    """Audio, all features/pitch, exact indexes and atomic checkpoint reserve."""
    segment = round(options.segment_seconds*options.sample_rate)
    step = segment-round(options.overlap_seconds*options.sample_rate)
    ranges = [frames]
    if single_source:
        boundary = int(frames*(1-options.holdout_fraction))
        ranges = [boundary, frames-boundary]
    extents = [segment_extent(length,segment,step,options.sample_rate) for length in ranges]
    count = sum(value[0] for value in extents)
    saved = sum(value[1] for value in extents)
    # ContentVec has ~50 frames/sec. Two per-piece padding positions make this
    # conservative. Include the train index and its persistent registered copy.
    features = math.ceil(saved*50/options.sample_rate)+2*count
    pitch = math.ceil(saved*100/options.sample_rate)+2*count
    needed = saved*4+features*768*4*3+pitch*12+count*512+checkpoint_bytes
    return {"pieces":count,"saved_frames":saved,"bytes":needed}


def checkpoint_reserve(job, options):
    """Reserve both old/new full Adam checkpoints and candidate exports."""
    reserve = 2*1024**3
    checkpoint = Path(job)/"resume.pth"
    if checkpoint.is_file():
        reserve = max(reserve,2*checkpoint.stat().st_size)
    manifest = Path(job)/"manifest.json"
    if manifest.is_file():
        value = json.loads(manifest.read_text(encoding="utf-8"))
        root = Path(value.get("model_root", ""))/"pretrained"/"v2"
        generator = root/f"f0G{options.sample_rate//1000}k.pth"
        discriminator = root/f"f0D{options.sample_rate//1000}k.pth"
        if generator.is_file() and discriminator.is_file():
            # The pinned pretrained tensors are FP16, whereas training weights
            # and both Adam slots are FP32. Account for that 2x expansion, two
            # atomic checkpoint generations, two exports and their registered
            # copy. Counting only file bytes underestimated the real 40k
            # checkpoint (about 1.21 GiB) and its temporary second generation.
            reserve = max(reserve,12*(generator.stat().st_size+discriminator.stat().st_size)
                          +6*generator.stat().st_size+16*1024**2)
    return reserve


def prepare(job, options, emit):
    import numpy as np
    import soundfile as sf
    job = Path(job)
    options.validate(check_sources=False)
    rows = source_splits(options.sources, options.holdout_fraction, options.seed,
                         lambda: (job/"cancel.request").exists(),options.source_groups)
    group_count = len({row["group_id"] for row in rows})
    if group_count == 1 and len(rows)>1:
        raise ValueError("Tüm kayıtlar aynı şarkı/oturum grubunda. Bağımsız değerlendirme için başka bir grup ekleyin.")
    if len(rows)==1:
        emit("quality",message="Tek kayıt zaman aralıklarına bölünecek. Bu, farklı şarkıda genelleme testi değildir; ayrı bir şarkı/oturum eklemek daha güçlü değerlendirme sağlar.")
    pieces, stats = [], []
    (job / "audio").mkdir(exist_ok=True)
    (job / "decoded").mkdir(exist_ok=True)
    segment = round(options.segment_seconds * options.sample_rate)
    step = segment - round(options.overlap_seconds * options.sample_rate)
    estimates = []
    for row in rows:
        check_cancel(job)
        probe = subprocess.run([ffmpeg_executable('ffprobe'), "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=noprint_wrappers=1:nokey=1", row["path"]],
                               capture_output=True, timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            seconds = float(probe.stdout.decode().strip())
        except (ValueError, UnicodeError):
            raise ValueError("Kayıt süresi okunamadı.")
        if probe.returncode or not np.isfinite(seconds) or seconds < 2:
            raise ValueError("Kayıt en az iki saniye ve geçerli sürede olmalı.")
        from training.experiments import selected_range
        start, end = selected_range(options, row['path'], seconds)
        frames = math.ceil(seconds*options.sample_rate)
        estimates.append((frames,estimate_storage(math.ceil((end-start)*options.sample_rate),options,len(rows)==1,0)))
    needed = (max(frames*4+4096 for frames,_ in estimates)
              +sum(estimate["bytes"] for _,estimate in estimates)+checkpoint_reserve(job,options)
              +(options.snapshot_budget_mb*1024**2 if options.snapshot_limit else 0))
    if shutil.disk_usage(job).free < needed:
        raise RuntimeError(f"Eğitim verisi, index ve atomik kontrol noktaları için en az {needed/1024**3:.2f} GB boş disk alanı gerekli.")
    emit("prepare",message=f"Hazırlama tahmini: {sum(value['pieces'] for _,value in estimates)} parça; en az {needed/1024**3:.2f} GB boş disk alanı.")
    for i, row in enumerate(rows):
        check_cancel(job)
        emit("prepare", message=f"Kayıt hazırlanıyor: {i+1}/{len(rows)}", percent=100*i/len(rows))
        target = job / "decoded" / f"source_{i}.wav"
        decode(row["path"], target, options.sample_rate, job)
        if file_digest(row["path"], lambda: (job/"cancel.request").exists()) != row["sha256"]:
            raise ValueError("Kaynak kayıt veri hazırlama sırasında değişti; eğitim başlatılmadı.")
        peak, clipped, energy, frames = 0., 0, 0., 0
        with sf.SoundFile(target) as stream:
            from training.experiments import selected_range
            selected_start, selected_end = selected_range(options, row['path'], stream.frames/options.sample_rate)
            first, last = round(selected_start*options.sample_rate), round(selected_end*options.sample_rate)
            stream.seek(first)
            remaining=last-first
            while remaining:
                check_cancel(job)
                block=stream.read(min(65536,remaining),dtype='float32')
                if not len(block):
                    raise ValueError('Seçilen ses bölümü eksik okundu.')
                remaining-=len(block)
                if not np.isfinite(block).all():
                    raise ValueError("Kayıtta NaN veya sonsuz ses örnekleri var.")
                peak = max(peak, float(np.max(np.abs(block))))
                clipped += int(np.sum(np.abs(block) >= 0.999))
                energy += float(np.sum(block.astype("float64")**2))
                frames += len(block)
            if not frames or peak < 1e-5:
                raise ValueError("Kayıt boş veya tamamen sessiz.")
            gain = min(1.0, .95 / peak)  # Never amplify noise or perform destructive denoise.
            if len(rows) == 1:
                boundary = first+int((last-first) * (1-options.holdout_fraction))
                ranges = [("train", first, boundary), ("holdout", boundary, last)]
            else:
                ranges = [(row["split"], first, last)]
            for split, start, end in ranges:
                for pos in range(start, end, step):
                    check_cancel(job)
                    length = min(segment, end-pos)
                    if length < options.sample_rate:
                        continue
                    stream.seek(pos)
                    audio = stream.read(length, dtype="float32") * gain
                    if np.sqrt(np.mean(audio.astype("float64")**2)) < 1e-5:
                        continue
                    name = f"{split}_{i}_{pos}"
                    path = job / "audio" / f"{name}.wav"
                    sf.write(path, audio, options.sample_rate, subtype="FLOAT")
                    pieces.append({"name": name, "audio": str(path.resolve()), "split": split,
                                   "source_sha256": row["sha256"], "start": pos, "frames": length})
        stats.append({**row, "seconds": frames/options.sample_rate, "peak": peak,
                      "rms": (energy/frames)**.5, "clipped_fraction": clipped/frames, "gain": gain})
        target.unlink()  # Recover long-recording decode disk; segments are retained.
    if sum(p["split"] == "train" for p in pieces) < 3 or not any(p["split"] == "holdout" for p in pieces):
        raise ValueError("Eğitim ve değerlendirme için yeterli ses yok. Daha uzun temiz kayıtlar seçin.")
    value = {"sources": stats, "pieces": pieces,
             "split_method": "source_group_hash" if options.source_groups else ("source_hash" if len(rows)>1 else "single_recording_disjoint_time")}
    write_json_atomic(str(job / "dataset.json"), value)
    seconds = sum(s["seconds"] for s in stats)
    if seconds < 600:
        emit("quality", message=f"Toplam kayıt {seconds/60:.1f} dakika. 10–30 dakika temiz, çeşitli ses aralıklarını içeren kayıt önerilir; bu bir kalite garantisi değildir.")
    for stat in stats:
        if stat["clipped_fraction"] > .01:
            emit("quality", message=f"{Path(stat['path']).name}: örneklerin %{100*stat['clipped_fraction']:.2f}'si clipping sınırında. Kaynak distorsiyonu eğitimle onarılamaz.")
        if stat["rms"] < .001:
            emit("quality", message=f"{Path(stat['path']).name}: ses seviyesi çok düşük; kaydı kontrol edin.")
    emit("prepare", message="Veri hazır; değerlendirme parçaları eğitime ve index'e girmeyecek.", percent=100)
    return value


def extract(job, options, device, emit):
    import gc
    import numpy as np
    import soundfile as sf
    import soxr
    import torch
    from rvc.lib.utils import load_embedding
    from rvc.lib.predictors.f0 import RMVPE, CREPE
    job = Path(job)
    dataset = json.loads((job/"dataset.json").read_text(encoding="utf-8"))
    pieces = dataset["pieces"]
    (job/"features").mkdir(exist_ok=True)
    def audio16(piece):
        audio, rate = sf.read(piece["audio"], dtype="float32")
        return soxr.resample(audio, rate, 16000, quality="VHQ")
    # Separate passes release large ContentVec and RMVPE networks before GAN training.
    model = load_embedding("contentvec", allow_download=False).to(device).float().eval()
    with torch.inference_mode():
        for i, piece in enumerate(pieces):
            check_cancel(job)
            audio = audio16(piece)
            feats = model(torch.from_numpy(audio).to(device).unsqueeze(0))["last_hidden_state"]
            features = feats[0].float().cpu().numpy()
            if features.ndim != 2 or features.shape[1] != 768 or not np.isfinite(features).all():
                raise ValueError("ContentVec geçersiz özellik üretti.")
            path = job / "features" / f"{piece['name']}.npy"
            np.save(path, features, allow_pickle=False)
            piece["features"] = str(path.resolve())
            emit("features", message=f"ContentVec: {i+1}/{len(pieces)}", percent=100*(i+1)/len(pieces))
    del model, feats
    gc.collect()
    from compute_backend import clear_cache
    clear_cache(device)
    predictor = RMVPE(device) if options.f0_method == "rmvpe" else CREPE(device)
    mel_min, mel_max = 1127*np.log1p(50/700), 1127*np.log1p(1100/700)
    from training.pitch_quality import PitchSummary
    pitch_summaries = {split:PitchSummary() for split in ("train","holdout")}
    for i, piece in enumerate(pieces):
        check_cancel(job)
        audio = audio16(piece)
        if options.f0_method == "rmvpe":
            f0 = predictor.get_f0(audio)
        else:
            f0 = predictor.get_f0(audio, model="tiny" if options.f0_method == "crepe-tiny" else "full")
        frames = len(audio)//160
        # Predictors can differ by one framing position; use explicit zero tail padding.
        f0 = np.asarray(f0, dtype="float32")[:frames]
        f0 = np.pad(f0, (0, max(0, frames-len(f0))))
        if not np.isfinite(f0).all() or np.any(f0 < 0):
            raise ValueError("Nota çıkarımı geçersiz değer üretti.")
        pitch_summaries[piece["split"]].add(f0)
        coarse = np.rint(np.clip((1127*np.log1p(f0/700)-mel_min)*254/(mel_max-mel_min)+1, 1, 255)).astype("int64")
        for key, value in (("pitch", coarse), ("pitchf", f0)):
            path = job / "features" / f"{piece['name']}_{key}.npy"
            np.save(path, value, allow_pickle=False)
            piece[key] = str(path.resolve())
        emit("pitch", message=f"Nota çıkarımı: {i+1}/{len(pieces)}", percent=100*(i+1)/len(pieces))
    write_json_atomic(str(job/"dataset.json"), dataset)
    pitch_report = {split:summary.result() for split,summary in pitch_summaries.items()}
    write_json_atomic(str(job/"pitch_report.json"),pitch_report)
    for split,summary in pitch_report.items():
        label = "Eğitim" if split=="train" else "Değerlendirme"
        emit("quality",message=f"{label}: sesli perde çerçevesi %{summary['voiced_fraction']*100:.1f}; medyan F0 {summary['median_hz'] or 0:.1f} Hz; sınır dışı %{summary['out_of_range_fraction']*100:.2f}. Örtüşen parçalardaki süre benzersiz kayıt süresi değildir.")
        if summary['out_of_range_fraction']>.01:
            emit("quality",message=f"{label}: sesli perdelerin bir kısmı 50–1100 Hz nicemleme sınırının dışında; kayıt ve nota çıkarımını kontrol edin.")
    for split in ("train", "holdout"):
        lines = ["|".join([p["audio"],p["features"],p["pitch"],p["pitchf"],"0"])
                 for p in pieces if p["split"] == split]
        (job/f"{split}.txt").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return dataset
