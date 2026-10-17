"""Optional A2SB inference in the native audio worker; no network access."""
import gc
import os
from pathlib import Path
import tempfile

from . import MODEL_ID, MODEL_SHA256
from .audio import RATE, candidate_intervals, splice_patch, attenuation_limit


def build_model():
    from .vendor.networks import AttnUNetF
    return AttnUNetF(n_updown_levels=5, in_channels=3,
        hidden_channels=[128,256,512,768,1024,2048], out_channels=3,
        emb_channels=128, rotary_dims=16, band_embedding_dim=16,
        n_attn_heads=8, attention_levels=[3,4], use_attn_input_norm=True, num_res_blocks=2)


def model_weights(checkpoint):
    weights = checkpoint.get('state_dict') if isinstance(checkpoint, dict) else None
    if not isinstance(weights, dict):
        raise ValueError('A2SB ağırlıkları geçersiz.')
    return {key.removeprefix('vf_model.'):value for key,value in weights.items()
            if isinstance(key,str) and key.startswith('vf_model.')}


class A2SBRepair:
    def __init__(self, model_dir, device, cancelled=None):
        import torch
        from model_manager import file_digest
        from training.resources import memory_status
        from .vendor.sampling import BridgeSampler
        self.device, self.cancelled = device, cancelled
        weight = Path(model_dir)/MODEL_ID
        if file_digest(weight, cancelled) != MODEL_SHA256:
            raise ValueError('Vokal onarım modeli doğrulanamadı; Ayarlar’dan kontrol edin.')
        available = memory_status().get('available_ram_mb')
        if available and available < 2800:
            raise MemoryError('Vokal onarım modeli için en az 2,8 GB boş RAM gerekiyor. Diğer programları kapatıp yeniden deneyin.')
        checkpoint = torch.load(weight, map_location='cpu', weights_only=True, mmap=True)
        self.model = build_model()
        self.model.load_state_dict(model_weights(checkpoint), strict=True)
        del checkpoint
        self.model.to(device).eval()
        self.sampler = BridgeSampler(self.model, device, cancelled)

    def synthesize(self, cleaned, interval, seed):
        import numpy as np
        import torch
        from .vendor.transforms import (ComplexSpectrogram, ComplexToMagInstPhase,
            SpectrogramDropDCTerm, PowerScaleSpectrogram, SpectrogramAddDCTerm,
            SVDFixMagInstPhase, MagInstPhaseToComplex, InverseComplexSpectrogram)
        a,b = interval
        # Every gap has an independent context from the unchanged cleaned input.
        left = max(0, int((a-2)*RATE))
        right = min(len(cleaned), int((b+2)*RATE))
        local = cleaned[left:right].astype('float32')
        if len(local) < 2048:
            raise ValueError('Vokal onarımı için ses bağlamı çok kısa.')
        # The upstream sampler expects at least one 256-frame window. Very
        # short recordings need reflected context, not a truncated window.
        padding = max((-len(local)) % 512, 256*512-len(local))
        padded = np.pad(local, (0,padding), mode='reflect')
        stft = ComplexSpectrogram(n_fft=2048,win_length=2048,hop_length=512)
        spec = SpectrogramDropDCTerm()(ComplexToMagInstPhase()(stft(torch.from_numpy(padded))))
        powered = PowerScaleSpectrogram(power=.25, channels=[0])(spec)
        times = np.arange(spec.shape[-1])*512/RATE+left/RATE
        mask = torch.zeros_like(powered)
        mask[:, :, (times>=a)&(times<b)] = 1
        if not mask.any():
            raise ValueError('Onarım aralığı model çözünürlüğünden kısa.')
        # fork_rng prevents this optional feature from altering other jobs' RNG.
        devices = [torch.device(self.device).index or 0] if self.device.startswith('cuda') else []
        with torch.random.fork_rng(devices=devices), torch.inference_mode():
            torch.manual_seed(seed)
            corrupted = powered*(1-mask)+torch.randn_like(powered)*.5*mask
            steps = torch.linspace(1,.05,33).unsqueeze(0).to(self.device)
            result = self.sampler.fast_inpaint_ddpm_sample(corrupted.unsqueeze(0).to(self.device),
                t_steps=steps, mask=mask.unsqueeze(0).to(self.device), mask_pred_x0=True,
                win_length=256, hop_length=128, batch_size=1)[-1][0].float().cpu()
        difference = float(torch.max(torch.abs((result-powered)*(1-mask))))
        if difference > 1e-5:
            raise RuntimeError('Model onarım maskesinin dışında beklenmeyen veri üretti.')
        for transform in (PowerScaleSpectrogram(power=4,channels=[0]), SpectrogramAddDCTerm(),
                          SVDFixMagInstPhase(), MagInstPhaseToComplex(),
                          InverseComplexSpectrogram(n_fft=2048,win_length=2048,hop_length=512)):
            result = transform(result)
        waveform = result.numpy()[:len(local)].astype('float64')
        if len(waveform)!=len(local) or not np.isfinite(waveform).all():
            raise ValueError('Model geçersiz onarım sesi üretti.')
        return waveform, left

    def close(self):
        import torch
        self.sampler = self.model = None
        gc.collect()
        if self.device.startswith('cuda'):
            torch.cuda.empty_cache()


def restore_file(reference_file, cleaned_file, output_file, model_dir, device='cpu',
                 cancelled=None, progress=None, repair_factory=A2SBRepair):
    import numpy as np
    import soundfile as sf
    import soxr
    from separation_audio import finite_audio
    from app_runtime import same_path
    target = Path(output_file)
    if any(same_path(target,path) for path in (reference_file,cleaned_file)):
        raise ValueError('Onarım çıktısı giriş dosyasının üzerine yazamaz.')
    if target.exists():
        raise FileExistsError('Onarım çıktısı zaten var; yeni bir iş klasörü kullanın.')
    def check_cancelled():
        if cancelled and cancelled():
            raise InterruptedError('Vokal onarımı iptal edildi.')
    # Duration is unrestricted. Budget the resampled working arrays before
    # decoding either input, including detector/filter and mono-copy temporaries.
    check_cancelled()
    infos = [sf.info(path) for path in (reference_file, cleaned_file)]
    if any(info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0 for info in infos):
        raise ValueError('Onarım için ses dosyası boş veya geçersiz.')
    lengths = [round(info.frames * RATE / info.samplerate) for info in infos]
    if abs(lengths[0]-lengths[1]) > 1:
        raise ValueError('Temizleme öncesi ve sonrası süreler eşleşmiyor.')
    from training.resources import memory_status
    available = memory_status().get('available_ram_mb')
    estimate_mb = (max(lengths)*8*24 + max(info.channels for info in infos)*65536*8)/1024**2
    if available and estimate_mb > available*.6:
        raise MemoryError(f'Vokal onarımı için tahmini RAM {estimate_mb:.0f} MiB; '
                          f'kullanılabilir RAM {available:.0f} MiB. Diğer programları kapatıp yeniden deneyin.')
    def read(path):
        check_cancelled()
        chunks = []
        with sf.SoundFile(path) as stream:
            resampler = (soxr.ResampleStream(stream.samplerate,RATE,1,dtype='float64',quality='VHQ')
                         if stream.samplerate != RATE else None)
            for data in stream.blocks(blocksize=65536,dtype='float64',always_2d=True):
                check_cancelled()
                finite_audio(data)
                mono = data.mean(axis=1)
                if resampler is not None:
                    mono = resampler.resample_chunk(mono,last=stream.tell()==stream.frames)
                chunks.append(mono)
        check_cancelled()
        return np.concatenate(chunks)
    reference, cleaned = read(reference_file), read(cleaned_file)
    if abs(len(reference)-len(cleaned)) > 1:
        raise ValueError('Temizleme öncesi ve sonrası süreler eşleşmiyor.')
    if len(reference)!=len(cleaned):
        reference = np.pad(reference,(0,max(0,len(cleaned)-len(reference))),mode='edge')[:len(cleaned)]
    intervals, skipped = candidate_intervals(reference,cleaned)
    result = cleaned.copy()
    repair = None
    try:
        if intervals:
            if progress: progress(f'Vokal onarım modeli hazırlanıyor; {len(intervals)} kısa aralık.')
            repair = repair_factory(model_dir,device,cancelled)
            for index,(a,b) in enumerate(intervals):
                check_cancelled()
                if progress: progress(f'Kısa vokal kaybı onarılıyor: {index+1}/{len(intervals)}')
                generated,left = repair.synthesize(cleaned,(a,b),1234+index)
                l,r = round(a*RATE)-left,round(b*RATE)-left
                gain = attenuation_limit(reference[left+l:left+r],generated[l:r])
                local_result,span = splice_patch(result[left:left+len(generated)],generated*gain,
                    a-left/RATE,b-left/RATE)
                result[left:left+len(generated)] = local_result
        check_cancelled()
        finite_audio(result)
        if float(np.abs(result).max()) >= 1:
            raise ValueError('Onarım ses düzeyi sınırını aştı; standart çıktı korunuyor.')
        target.parent.mkdir(parents=True,exist_ok=True)
        fd,temporary = tempfile.mkstemp(prefix='restore_',suffix='.flac',dir=target.parent)
        os.close(fd)
        try:
            sf.write(temporary,result,RATE,subtype='PCM_24',format='FLAC')
            check_cancelled()
            os.replace(temporary,target)
        finally:
            if os.path.exists(temporary): os.remove(temporary)
    finally:
        if repair is not None: repair.close()
    return {'output':str(target),'repaired_intervals':len(intervals),
            'skipped_long_intervals':skipped,'channels':1,'sample_rate':RATE,
            'frames':len(result)}
