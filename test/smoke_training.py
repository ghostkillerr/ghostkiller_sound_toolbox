"""Explicit full-pipeline smoke fixture. Synthetic tones test format, NOT voice quality.

Run: python test/smoke_training.py --device cuda:0 --batch 1
Artifacts remain under ignored training_runs/ for inspection. No registry update.
"""
import argparse
from pathlib import Path
import sys
import json
import uuid
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import configure_runtime_cache
configure_runtime_cache()
from training.config import TrainingOptions
from training.service import create_job,TrainingProcess
from app_settings import AppSettings
from hardware import DeviceSupport,HardwareReport,probe_operations


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--batch',type=int,default=1)
    parser.add_argument('--epochs',type=int,default=1)
    parser.add_argument('--cancel-after-step',type=int,default=0)
    args=parser.parse_args()
    import torch
    torch.set_num_threads(2)
    probe_operations(args.device)
    inputs=ROOT/'training_runs'/('fixture_'+uuid.uuid4().hex[:8])
    inputs.mkdir(parents=True)
    sources=[]
    for i in range(2):
        time=np.arange(40000*6,dtype='float64')/40000
        fundamental=160+i*35+20*np.sin(2*np.pi*.7*time)
        phase=2*np.pi*np.cumsum(fundamental)/40000
        audio=sum(.12/h*np.sin(phase*h) for h in range(1,6))
        audio*=.6+.4*np.sin(2*np.pi*1.2*time)**2
        path=inputs/f'synthetic_{i}.wav'
        sf.write(path,audio,40000,subtype='FLOAT')
        sources.append(str(path))
    settings=AppSettings()
    cpu=DeviceSupport('cpu','CPU',True)
    gpus=[DeviceSupport(args.device,'test GPU',True)] if args.device.startswith('cuda') else []
    settings.report=HardwareReport(cpu,gpus)
    settings.preference='gpu' if gpus else 'cpu'  # In-memory test preference; never persisted.
    options=TrainingOptions('Synthetic compatibility test',tuple(sources),epochs=args.epochs,save_every=1,
                            batch_size=args.batch,segment_seconds=1.2,overlap_seconds=.3,cpu_threads=2)
    job=create_job(options,settings)
    print('JOB '+job,flush=True)
    last=None
    runner=TrainingProcess()
    cancelled=False
    def progress(event):
        nonlocal last,cancelled
        stage=event['stage']
        if stage != last or stage in ('resources','train','checkpoint','evaluate','failed','completed'):
            print(json.dumps(event,ensure_ascii=False),flush=True)
        last=stage
        if args.cancel_after_step and not cancelled and event.get('step',0)>=args.cancel_after_step:
            runner.cancel()
            cancelled=True
    try:
        result=runner.run(job,progress)
    except InterruptedError:
        print('CANCELLED; checking resume checkpoint',flush=True)
        state=torch.load(Path(job)/'resume.pth',map_location='cpu',weights_only=True,mmap=True)
        print('CURSOR '+json.dumps({k:state[k] for k in ('epoch','next_batch','step','batch')}),flush=True)
        del state
        result=TrainingProcess().run(job,progress,resume=True)
    print('RESULT '+json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
