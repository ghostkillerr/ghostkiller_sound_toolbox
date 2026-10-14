"""Bounded recording inspection; measurements never modify source audio."""
from pathlib import Path
import math
import os
import shutil
import subprocess
import tempfile
import json
from model_manager import file_digest
from app_runtime import ffmpeg_executable


def _cancel(cancelled):
    if cancelled():
        raise InterruptedError("Kayıt analizi durduruldu; özgün sesler değiştirilmedi.")


def _command(command, folder, cancelled):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (folder / "decode.log").open("w", encoding="utf-8") as errors:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors, creationflags=flags)
        try:
            while process.poll() is None:
                _cancel(cancelled)
                try:
                    process.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    pass
            _cancel(cancelled)
            if process.returncode:
                raise ValueError("Kayıt okunamadı: " + (folder / "decode.log").read_text(encoding="utf-8", errors="replace")[-1500:])
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def inspect_audio(path, cancelled=lambda: False):
    """Inspect 100ms windows, retaining channels and native amplitude."""
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(path) as stream:
        rate, channels = stream.samplerate, stream.channels
        if not 1 <= channels <= 32 or not stream.frames:
            raise ValueError("Kayıt boş veya kanal sayısı desteklenmiyor.")
        frames = clipped = quiet = 0
        peak = energy = dc = mono_energy = 0.
        for block in stream.blocks(blocksize=max(1, rate // 10), dtype="float32", always_2d=True):
            _cancel(cancelled)
            if not np.isfinite(block).all():
                raise ValueError("Kayıtta NaN veya sonsuz ses örnekleri var.")
            values = block.astype("float64")
            block_energy = float(np.sum(values * values))
            peak = max(peak, float(np.max(np.abs(values))))
            energy += block_energy
            dc += float(np.sum(values))
            clipped += int(np.count_nonzero(np.abs(values) >= .999))
            mono_energy += float(np.sum(np.mean(values, axis=1) ** 2))
            if math.sqrt(block_energy / values.size) < .001:
                quiet += len(block)
            frames += len(block)
        if peak < 1e-5:
            raise ValueError("Kayıt tamamen sessiz veya kullanılabilecek seviyenin altında.")
        rms = math.sqrt(energy / (frames * channels))
        ratio = math.sqrt(mono_energy / frames) / rms
        return dict(seconds=frames / rate, sample_rate=rate, channels=channels,
                    peak=peak, rms=rms, rms_dbfs=20 * math.log10(rms),
                    clipping_fraction=clipped / (frames * channels),
                    quiet_fraction=quiet / frames, dc_offset=dc / (frames * channels),
                    mono_rms_ratio=ratio)


def analyze_sources(sources, sample_rate, cancelled=lambda: False, emit=lambda *a, **k: None):
    """Streaming decode, exact duplicate detection and explicit heuristic warnings."""
    if not sources:
        raise ValueError("Analiz için en az bir kayıt seçin.")
    records, seen = [], {}
    with tempfile.TemporaryDirectory(prefix="ghost_training_analysis_") as temporary:
        folder = Path(temporary)
        for index, source in enumerate(sources):
            _cancel(cancelled)
            path = Path(source).resolve()
            digest = file_digest(path, cancelled)
            if digest in seen:
                records.append(dict(path=str(path), sha256=digest, duplicate_of=seen[digest], warnings=["Aynı dosya içeriği; eğitime ikinci kez alınmayacak."]))
                continue
            seen[digest] = str(path)
            emit("analysis", message=f"Kayıt analizi: {index + 1}/{len(sources)} — {path.name}", percent=100 * index / len(sources))
            probe = subprocess.run([ffmpeg_executable('ffprobe'), "-v", "error", "-show_entries", "stream=sample_rate,channels:format=duration", "-of", "json", str(path)],
                                   capture_output=True, timeout=15, check=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            metadata = json.loads(probe.stdout)
            seconds = float(metadata["format"]["duration"])
            if not math.isfinite(seconds) or seconds < 2:
                raise ValueError(f"{path.name}: kayıt en az iki saniye olmalı.")
            channels = max(int(s.get("channels", 0)) for s in metadata["streams"])
            if not 1 <= channels <= 32:
                raise ValueError("Kanal sayısı desteklenmiyor.")
            if shutil.disk_usage(folder).free < seconds * sample_rate * channels * 4 + 256 * 1024**2:
                raise ValueError("Kayıt analizi için geçici diskte yeterli boş alan yok.")
            decoded = folder / "decoded.wav"
            _command([ffmpeg_executable(), "-nostdin", "-v", "error", "-y", "-i", str(path), "-vn", "-ar", str(sample_rate), "-c:a", "pcm_f32le", str(decoded)], folder, cancelled)
            values = inspect_audio(decoded, cancelled)
            if file_digest(path, cancelled) != digest:
                raise ValueError("Kayıt analiz sırasında değişti; sonucu kullanmayın.")
            warnings = []
            if values["clipping_fraction"] > .001:
                warnings.append("Tepe sınırında örnekler var; kayıtta distorsiyon olup olmadığını dinleyin.")
            if values["quiet_fraction"] > .3:
                warnings.append("Düşük seviyeli bölümler fazla; sessizlik ve kayıt seviyesini kontrol edin.")
            if values["rms_dbfs"] < -50:
                warnings.append("Kayıt seviyesi çok düşük.")
            if values["channels"] > 1 and values["mono_rms_ratio"] < .25:
                warnings.append("Mono birleştirmede belirgin enerji kaybı; kanallar arasında faz iptali olabilir.")
            records.append(dict(path=str(path), sha256=digest, **values, warnings=warnings))
            decoded.unlink()
    total = sum(r.get("seconds", 0) for r in records)
    emit("analysis", message="Kayıt analizi tamamlandı.", percent=100)
    return dict(schema_version=1, sources=records, total_seconds=total,
                unique_recordings=len(seen), duplicate_recordings=len(records)-len(seen),
                note="Ölçümler kalite garantisi değildir. Düşük seviye eşiği −60 dBFS, pencere 100 ms; gürültü, yankı ve ses kimliği otomatik doğrulanmaz.")


def report_text(report):
    lines = [f"Toplam benzersiz kayıt: {report['unique_recordings']}; süre: {report['total_seconds']/60:.1f} dakika; tekrar: {report['duplicate_recordings']}."]
    if 'split_review' in report:
        split = report['split_review']
        total = split['train_seconds']+split['holdout_seconds']
        percent = 100*split['holdout_seconds']/total if total else 0
        lines.append(f"Seçilen bölümler: eğitim {split['train_seconds']/60:.2f} dakika; kontrol {split['holdout_seconds']/60:.2f} dakika (%{percent:.1f}); {split['independent_groups']} bağımsız grup.")
        if split['timeline_split']:
            lines.append('Tek kayıt zaman içinde ayrıldı; farklı şarkıya genelleme ölçülmüyor.')
        elif not split['holdout_seconds']:
            lines.append('Bağımsız kontrol grubu kalmadı. Başka bir şarkı/oturum ekleyin.')
    for record in report["sources"]:
        lines.append("\n" + Path(record["path"]).name)
        if "duplicate_of" not in record:
            lines.append(f"{record['seconds']:.1f} saniye; {record['channels']} kanal; RMS {record['rms_dbfs']:.1f} dBFS; tepe {record['peak']:.3f}; sınırdaki örnek %{record['clipping_fraction']*100:.2f}; düşük seviyeli süre %{record['quiet_fraction']*100:.1f}.")
        lines.extend(record["warnings"] or ["Bu ölçümlerde uyarı yok; temizliği ve ses çeşitliliğini dinleyerek kontrol edin."])
    lines.append("\n" + report["note"])
    return "\n".join(lines)
