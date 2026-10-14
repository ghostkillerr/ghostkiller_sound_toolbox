"""Explicit real-model integration. Synthetic inputs test operation, not voice quality."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',default='cuda:0')
    args=parser.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    from app_runtime import configure_runtime_cache
    configure_runtime_cache()
    from app_settings import AppSettings,write_json_atomic
    from model_manager import ModelManager,file_digest
    from hardware import probe_operations
    from smoke_training import configure_fixture_device
    from training.config import TrainingOptions
    from training.service import create_job,TrainingProcess
    from training.experiments import request_extension,snapshot_records
    import training.service as service

    root=ROOT/'build'/('training_experiments_'+uuid.uuid4().hex[:10])
    root.mkdir()
    print('AUDIT '+str(root),flush=True)
    manager=ModelManager()
    protected=[ROOT/'settings.json',ROOT/'models.json',Path(manager.manifest_path)]
    for key in ('contentvec','rmvpe','training_v2_40k'):
        protected.extend(Path(manager.path(name)) for name in manager.primary_files(key))
    before={str(p):file_digest(p) for p in protected if p.is_file()}
    manager.manifest_path=str(root/'verified-assets.json')
    errors=manager.process(('contentvec','rmvpe','training_v2_40k'),'verify',log=lambda m:print(m,flush=True))
    if errors:raise RuntimeError(errors)
    settings=AppSettings(manager=manager)
    configure_fixture_device(settings,args.device)
    probe_operations(args.device)
    sources=[]
    for number in range(2):
        time=np.arange(40000*6)/40000
        wave=.15*np.sin(2*np.pi*(170+number*50)*time)+.05*np.sin(2*np.pi*(340+number*100)*time)
        path=root/f'synthetic_{number}.wav'
        sf.write(path,wave,40000,subtype='FLOAT')
        sources.append(str(path))
    options=TrainingOptions('Experiment integration',tuple(sources),epochs=1,save_every=1,batch_size=1,
                            segment_seconds=1.2,overlap_seconds=.3,cpu_threads=2)
    events=[]
    def emit(value):
        events.append(value)
        if value['stage'] in ('prepare','evaluate','checkpoint','failed','completed'):
            print(json.dumps(value,ensure_ascii=False),flush=True)
    # All sessions, registries and cache references stay in the owned audit directory.
    with patch.object(service,'data_directory',return_value=str(root)):
        job=create_job(options,settings)
        first=TrainingProcess().run(job,emit)
        extended=request_extension(job,3)
        second=TrainingProcess().run(job,emit,resume=True)
        if len(snapshot_records(job))!=3:raise AssertionError('Three epoch snapshots not retained')
        if second['steps']<=first['steps']:raise AssertionError('Extension made no progress')
        fine=create_job(replace(options,name='Fine-tune integration'),settings,parent_job=job)
        third=TrainingProcess().run(fine,emit)
    after={str(p):file_digest(p) for p in protected if p.is_file()}
    if before!=after:raise AssertionError('Protected model/settings files changed')
    reused=any('doğrulanmış hazırlığı kopyalandı' in r.get('message','') for r in events)
    if not reused:raise AssertionError('Compatible fine-tune did not reuse prepared data')
    report={'ok':True,'device':args.device,'torch':str(torch.__version__),'first_steps':first['steps'],
            'extended_steps':second['steps'],'fine_tune_steps':third['steps'],
            'snapshots':len(snapshot_records(job)),'candidates':len(second['models']),
            'comparison_inputs':len(second['comparison_inputs']),'preparation_reused':reused,
            'protected_unchanged':before==after,'sessions':[job,fine],
            'scope':'Synthetic format/runtime test; no listening or real-song quality claim.'}
    write_json_atomic(str(root/'result.json'),report)
    print('RESULT '+json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
