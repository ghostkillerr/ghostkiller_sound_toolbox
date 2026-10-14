"""FP32 single-device GAN trainer using the application's inference architecture."""
import gc
import json
import math
from pathlib import Path
import random
import time
import numpy as np
import torch
from compute_backend import (backend_module, is_gpu_device, clear_cache, synchronize,
                             memory_info, get_rng_states, set_rng_states, trim_cache)
from training.config import architecture, inference_config, BACKEND_COMMIT, TrainingOptions
from training.storage import (atomic_torch_save, map_legacy_weights, update_manifest,
                              rng_layout,validate_checkpoint_backend)
from training.dataset import check_cancel
from training.resources import ResourceMonitor
from training.vendor.data_utils import TextAudioLoaderMultiNSFsid, TextAudioCollateMultiNSFsid
from training.vendor.utils import HParams
from training.vendor.discriminators import MultiPeriodDiscriminator
from training.vendor.losses import discriminator_loss, generator_loss, feature_loss, kl_loss
from training.vendor.mel_processing import mel_spectrogram_torch
from rvc.lib.algorithm.synthesizers import Synthesizer
from rvc.lib.algorithm.commons import slice_segments


def model_pair(config, checkpointing=False):
    net_g = Synthesizer(*inference_config(config), use_f0=True, text_enc_hidden_dim=768,
                        vocoder="HiFi-GAN", checkpointing=checkpointing)
    net_d = MultiPeriodDiscriminator(use_spectral_norm=config["model"]["use_spectral_norm"],
                                     version="v2", checkpointing=checkpointing)
    return net_g, net_d


def load_pretrained(model, path, single_speaker=False):
    state = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    state = map_legacy_weights(state.get("model", state.get("weight", state)))
    if single_speaker:
        if "emb_g.weight" not in state or state["emb_g.weight"].ndim != 2:
            raise ValueError("Pretrained G konuşmacı ağırlığı eksik.")
        state["emb_g.weight"] = state["emb_g.weight"][:1].clone()
    # Never silently initialize missing layers: quality depends on real pretrained coverage.
    model.load_state_dict(state, strict=True)


def mel(audio, config):
    data = config["data"]
    return mel_spectrogram_torch(audio.float().squeeze(1), data["filter_length"], data["n_mel_channels"],
                                data["sample_rate"], data["hop_length"], data["win_length"],
                                data["mel_fmin"], data["mel_fmax"])


def train_step(info, net_g, net_d, opt_g, opt_d, config):
    phone, lengths, pitch, pitchf, spec, spec_lengths, wave, _, sid = info
    output, ids, _, z_mask, (_, z_p, m_p, logs_p, _, logs_q) = net_g(
        phone, lengths, pitch, pitchf, spec, spec_lengths, sid)
    wave = slice_segments(wave, ids*config["data"]["hop_length"], config["train"]["segment_size"], dim=3)
    opt_d.zero_grad(set_to_none=True)
    discriminator_output = net_d(wave, output.detach())
    loss_d, _, _ = discriminator_loss(discriminator_output[0], discriminator_output[1])
    # D feature maps are unnecessary for D loss. Holding them until G forward
    # needlessly doubles multi-period discriminator activation memory.
    del discriminator_output
    if not torch.isfinite(loss_d):
        raise FloatingPointError("Discriminator kaybı geçersiz; son sağlam checkpoint korunuyor.")
    loss_d.backward()
    check_gradients(net_d)
    opt_d.step()
    opt_d.zero_grad(set_to_none=True)
    trim_cuda_cache(output.device)
    net_d.requires_grad_(False)
    try:
        _, fake, fmap_real, fmap_fake = net_d(wave, output)
        loss_mel = torch.nn.functional.l1_loss(mel(wave,config),mel(output,config))*config["train"]["c_mel"]
        loss_kl = kl_loss(z_p,logs_q,m_p,logs_p,z_mask)*config["train"]["c_kl"]
        loss_fm = feature_loss(fmap_real,fmap_fake)
        loss_adv, _ = generator_loss(fake)
        loss_g = loss_mel+loss_kl+loss_fm+loss_adv
        if not torch.isfinite(loss_g):
            raise FloatingPointError("Generator kaybı geçersiz; son sağlam checkpoint korunuyor.")
        opt_g.zero_grad(set_to_none=True)
        loss_g.backward()
        check_gradients(net_g)
        opt_g.step()
        return {"loss_g": float(loss_g.detach()), "loss_d": float(loss_d.detach()),
                "loss_mel": float(loss_mel.detach()), "loss_kl": float(loss_kl.detach())}
    finally:
        net_d.requires_grad_(True)
        opt_g.zero_grad(set_to_none=True)


def trim_cuda_cache(device):
    """Release only idle cached blocks under measured pressure, never live tensors."""
    trim_cache(device)


def check_gradients(model):
    # A single reduction/sync instead of thousands of per-parameter GPU synchronizations.
    valid = [torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None]
    if not valid or not torch.stack(valid).all():
        raise FloatingPointError("Gradyanlarda geçersiz değer bulundu; eğitim durduruldu.")


def export_model(net_g, config, options, job, filename, epoch, step):
    path = Path(job)/filename
    value = {"weight": {k:v.detach().cpu().float() for k,v in net_g.state_dict().items()
                        if not k.startswith("enc_q.")},
             "config": inference_config(config), "f0": 1, "version": "v2",
             "sr": options.sample_rate, "vocoder": "HiFi-GAN", "embedder_model": "contentvec",
             "speakers_id": 1, "model_name": options.name, "epoch": epoch, "step": step,
             "backend_commit": BACKEND_COMMIT}
    atomic_torch_save(value,path)
    return str(path)


def evaluate(net_g, dataset, config, device, job):
    collate = TextAudioCollateMultiNSFsid()
    values = []
    net_g.eval()
    devices = [torch.device(device).index or 0] if is_gpu_device(device) else []
    rng_backend = str(device).split(":",1)[0] if devices else "cuda"
    try:
        # Mel/STFT constants cached here are reused in the next backward pass.
        # inference_mode would create tensors forbidden in autograd after resume.
        with torch.no_grad(), torch.random.fork_rng(devices=devices,device_type=rng_backend):
            torch.manual_seed(1234)
            for i in range(len(dataset)):
                check_cancel(job)
                info = [x.to(device) for x in collate([dataset[i]])]
                phone,lengths,pitch,pitchf,_,_,wave,_,sid = info
                generated, *_ = net_g.infer(phone,lengths,pitch,pitchf,sid)
                n = min(generated.shape[-1],wave.shape[-1])
                loss = torch.nn.functional.l1_loss(mel(generated[:,:,:n],config),mel(wave[:,:,:n],config))
                if not torch.isfinite(loss):
                    raise FloatingPointError("Değerlendirme sesi geçersiz.")
                values.append(float(loss))
    finally:
        net_g.train()
    return sum(values)/len(values)


def run_training(job, options, device, model_root, emit, resume=False):
    job = Path(job)
    config = architecture(options.sample_rate)
    config["train"]["learning_rate"] = options.learning_rate
    torch.set_num_threads(options.cpu_threads)
    torch.manual_seed(options.seed)
    random.seed(options.seed)
    np.random.seed(options.seed)
    api = backend_module(device)
    if api is not None:
        api.set_device(device)
        info = memory_info(device)
        # Constrain allocator to physical VRAM with desktop/other-process headroom.
        # Windows can otherwise spill CUDA allocations into shared system RAM.
        if info and hasattr(api,"set_per_process_memory_fraction"):
            free, total = info
            fraction = min(.85, max(.05, free/total*.9))
            api.set_per_process_memory_fraction(fraction, device)
        if hasattr(api,"reset_peak_memory_stats"):
            api.reset_peak_memory_stats(device)
    # FP32; no TF32 or AMP approximation behind the user's quality settings.
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    monitor = ResourceMonitor(device,emit)
    monitor.sample(True)
    train_data = TextAudioLoaderMultiNSFsid(HParams(**config["data"],training_files=str(job/"train.txt")))
    valid_data = TextAudioLoaderMultiNSFsid(HParams(**config["data"],training_files=str(job/"holdout.txt")))
    collate = TextAudioCollateMultiNSFsid()
    net_g, net_d = model_pair(config,options.checkpointing)
    pretrain = Path(model_root)/"pretrained"/"v2"
    load_pretrained(net_g,pretrain/f"f0G{options.sample_rate//1000}k.pth",True)
    load_pretrained(net_d,pretrain/f"f0D{options.sample_rate//1000}k.pth")
    net_g, net_d = net_g.to(device).float().train(), net_d.to(device).float().train()
    def initial_weights():
        path = job/'initial_weights.pth'
        if path.is_file():
            from model_manager import file_digest
            manifest = json.loads((job/'manifest.json').read_text(encoding='utf-8'))
            if file_digest(path) != manifest['initial_weights_sha256']:
                raise ValueError('Yeni eğitimin başlangıç ağırlıkları değişmiş.')
            value = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
            net_g.load_state_dict(value['generator'], strict=True)
            net_d.load_state_dict(value['discriminator'], strict=True)
        else:
            load_pretrained(net_g,pretrain/f"f0G{options.sample_rate//1000}k.pth",True)
            load_pretrained(net_d,pretrain/f"f0D{options.sample_rate//1000}k.pth")
    if not resume:
        initial_weights()
    def optimizers():
        args = {"lr": options.learning_rate, "betas": tuple(config["train"]["betas"]), "eps": config["train"]["eps"]}
        return torch.optim.AdamW(net_g.parameters(),**args),torch.optim.AdamW(net_d.parameters(),**args)
    opt_g,opt_d = optimizers()
    sched_g = torch.optim.lr_scheduler.ExponentialLR(opt_g,gamma=config["train"]["lr_decay"])
    sched_d = torch.optim.lr_scheduler.ExponentialLR(opt_d,gamma=config["train"]["lr_decay"])
    epoch, next_batch, step, best = 1,0,0,float("inf")
    batch = options.batch_size or (4 if is_gpu_device(device) else 1)
    checkpoint = job/"resume.pth"
    if resume and checkpoint.is_file():
        # Keep the checkpoint tensors in file-backed CPU storage. Loading the whole
        # generator, discriminator and Adam states on the GPU duplicates the live
        # networks and can exhaust VRAM before the first resumed step.
        state = torch.load(checkpoint,map_location="cpu",weights_only=True,mmap=True)
        validate_checkpoint_backend(state,device)
        from training.experiments import resume_options_match
        if state["config"] != config or not resume_options_match(job, state['options'], options):
            raise ValueError("Devam ayarları checkpoint ile eşleşmiyor.")
        net_g.load_state_dict(state.pop("generator"))
        net_d.load_state_dict(state.pop("discriminator"))
        # AdamW loads each parameter's state onto its own device. Pop consumed
        # CPU mappings so they are released as soon as each stage is complete.
        opt_g.load_state_dict(state.pop("optimizer_g"))
        opt_d.load_state_dict(state.pop("optimizer_d"))
        sched_g.load_state_dict(state["scheduler_g"])
        sched_d.load_state_dict(state["scheduler_d"])
        epoch,next_batch,step,best,batch = [state[k] for k in ("epoch","next_batch","step","best","batch")]
        if step > 0:
            opt_g._opt_called = opt_d._opt_called = True
        torch.set_rng_state(state["torch_rng"].cpu())
        set_rng_states(device,state.get("device_rng",state.get("cuda_rng",[])))
        random.setstate(state["python_rng"])
        np.random.set_state((state["numpy_rng"][0],np.array(state["numpy_rng"][1],dtype="uint32"),
                             *state["numpy_rng"][2:]))
        del state
    elif resume:
        raise FileNotFoundError("Devam kontrol noktası bulunamadı.")
    elif not options.batch_size:
        # Probe actual GAN workload, then reload pristine weights and RNG.
        rng = torch.get_rng_state()
        device_rng = get_rng_states(device)
        ids = sorted(range(len(train_data)),key=lambda i: train_data.lengths[i],reverse=True)
        while True:
            check_cancel(job)
            info = None
            try:
                info = [x.to(device) for x in collate([train_data[i] for i in ids[:batch]])]
                train_step(info,net_g,net_d,opt_g,opt_d,config)
                del info
                if is_gpu_device(device):
                    synchronize(device)
                    info = memory_info(device)
                    if info and info[0] < max(256*1024**2,info[1]*.08):
                        raise torch.OutOfMemoryError("Bellek payı yetersiz.")
                break
            except torch.OutOfMemoryError:
                if batch == 1:
                    raise RuntimeError("Batch 1 için bile bellek yetersiz. Kalite ayarları düşürülmedi; Ayarlar'dan başka donanım seçin.")
                batch = max(1,batch//2)
                emit("train",message=f"Başlangıç bellek ölçümü: batch {batch} deneniyor.")
            finally:
                info = None
                # Clean gradients and optimizer slots from trial before retry/reset.
                net_g.zero_grad(set_to_none=True)
                net_d.zero_grad(set_to_none=True)
                opt_g.state.clear()
                opt_d.state.clear()
                initial_weights()
                torch.set_rng_state(rng)
                set_rng_states(device,device_rng)
                gc.collect()
                clear_cache(device)
    batch = min(batch,len(train_data))
    emit("train",message=f"FP32 eğitim; batch {batch}; CPU thread {options.cpu_threads}; veri GPU'da önbelleğe alınmıyor.",batch=batch)
    update_manifest(job,actual_batch=batch,architecture=config,precision="fp32",device=device)

    def save():
        numpy_rng = np.random.get_state()
        atomic_torch_save({"generator":net_g.state_dict(),"discriminator":net_d.state_dict(),
                          "optimizer_g":opt_g.state_dict(),"optimizer_d":opt_d.state_dict(),
                          "scheduler_g":sched_g.state_dict(),"scheduler_d":sched_d.state_dict(),
                          "epoch":epoch,"next_batch":next_batch,"step":step,"best":best,"batch":batch,
                          "config":config,"options":options.to_dict(),"torch_rng":torch.get_rng_state(),
                          "device_rng":get_rng_states(device),"rng_backend":str(device).split(":",1)[0],
                          "rng_layout":rng_layout(device),
                          "python_rng":random.getstate(),
                          "numpy_rng":(numpy_rng[0],numpy_rng[1].tolist(),*numpy_rng[2:])},checkpoint)
    # A failed first epoch still has a pristine restart point.
    if not checkpoint.is_file():
        save()
    try:
        session_started = last_save = time.monotonic()
        session_start_step = step
        metrics = {}
        while epoch <= options.epochs:
            generator = torch.Generator().manual_seed(options.seed+epoch)
            ids = torch.randperm(len(train_data),generator=generator).tolist()
            chunks = [ids[i:i+batch] for i in range(0,len(ids),batch)]
            for cursor in range(next_batch,len(chunks)):
                check_cancel(job)
                info = [x.to(device) for x in collate([train_data[i] for i in chunks[cursor]])]
                metrics = train_step(info,net_g,net_d,opt_g,opt_d,config)
                del info
                trim_cuda_cache(torch.device(device))
                step += 1
                next_batch = cursor+1
                if step%10 == 0 or cursor == len(chunks)-1:
                    elapsed = time.monotonic()-session_started
                    measured_steps = step-session_start_step
                    remaining_steps = (options.epochs-epoch)*len(chunks)+len(chunks)-next_batch
                    eta = elapsed/measured_steps*remaining_steps if measured_steps >= 20 else None
                    emit("train",message=f"Epoch {epoch}/{options.epochs}, adım {step}",epoch=epoch,step=step,
                         percent=100*((epoch-1)+(cursor+1)/len(chunks))/options.epochs,
                         eta_seconds=eta, session_seconds=elapsed, **metrics)
                # A terminal cursor is valid: resume skips completed batches and
                # performs evaluation/scheduler/epoch advancement exactly once.
                # This also covers epochs that fit in one batch.
                if time.monotonic()-last_save >= 300:
                    save()
                    last_save = time.monotonic()
                    update_manifest(job,last_checkpoint_step=step,last_checkpoint_epoch=epoch)
                    emit("checkpoint",message=f"Adım {step}: devam noktası kaydedildi; eğitim sürüyor.")
                monitor.sample()
            if epoch%options.save_every == 0 or epoch == options.epochs:
                validation = evaluate(net_g,valid_data,config,device,job)
                with (job/"metrics.jsonl").open("a",encoding="utf-8") as stream:
                    stream.write(json.dumps({"epoch":epoch,"step":step,"holdout_mel_l1":validation, **metrics})+"\n")
                emit("evaluate",message=f"Epoch {epoch}: değerlendirme mel hatası {validation:.4f}; dinleme testi yine gerekli.")
                export_model(net_g,config,options,job,"latest.pth",epoch,step)
                if validation < best:
                    best = validation
                    export_model(net_g,config,options,job,"best_validation.pth",epoch,step)
                from training.experiments import archive_snapshot
                archive_snapshot(job, options, epoch, step, validation)
            sched_g.step()
            sched_d.step()
            completed = epoch
            epoch += 1
            next_batch = 0
            if completed%options.save_every == 0 or completed == options.epochs:
                save()
                last_save = time.monotonic()
                update_manifest(job,last_checkpoint_step=step,last_checkpoint_epoch=completed)
                emit("checkpoint",message=f"Epoch {completed}: devam kontrol noktası atomik kaydedildi.")
    except InterruptedError:
        save()  # Only after a FULL D+G update; never save a half optimizer transaction.
        raise
    finally:
        monitor.sample(True)
    return {"epochs":options.epochs,"steps":step,"batch":batch,"holdout_mel_l1":best}
