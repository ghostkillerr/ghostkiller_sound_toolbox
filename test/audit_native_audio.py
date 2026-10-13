"""Actual native audio-worker smoke with synthetic audio and existing models."""
from pathlib import Path
import json
import argparse
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import validate_audio_file
from audio_service import NativeAudioSession
import numpy as np
import soundfile as sf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device",default="cpu")
    args = parser.parse_args()
    device = args.device
    results = []
    with tempfile.TemporaryDirectory(prefix='native_audio_check_',dir=ROOT) as folder:
        root = Path(folder)
        source = root/('Şarkı_日本語_'*12+'.wav')
        t = np.arange(44100*4)/44100
        signal = .15*np.sin(2*np.pi*180*t)+.05*np.sin(2*np.pi*720*t)
        sf.write(source,np.stack([signal,signal],axis=1),44100)
        with NativeAudioSession(directory=root) as session:
            ping = session.execute('ping',{'device':device})
            for name in ('model_bs_roformer_ep_317_sdr_12.9755.ckpt','UVR-DeEcho-DeReverb.pth'):
                output = root/name.replace('.','_')
                output.mkdir()
                start = time.monotonic()
                try:
                    files = session.execute('separate',{'device':device,'input_file':str(source),
                        'output_dir':str(output),'model_dir':str(ROOT/'models'),'model_name':name})
                    for path in files:
                        validate_audio_file(path)
                        assert sf.info(path).frames==round(sf.info(source).duration*sf.info(path).samplerate)
                        assert sf.info(path).subtype=='PCM_24'
                    record = {'model':name,'status':'passed','outputs':[{'name':Path(path).name,
                        'duration':sf.info(path).duration,'sample_rate':sf.info(path).samplerate} for path in files]}
                except Exception as error:
                    record = {'model':name,'status':'failed','error':str(error)}
                record.update(seconds=round(time.monotonic()-start,3),worker_pid=ping['pid'])
                results.append(record)
                print(json.dumps(record,ensure_ascii=False),flush=True)
            for name in ('latest.pth','best_validation.pth'):
                start = time.monotonic()
                target = root/(name+'.wav')
                try:
                    session.execute('cover',{'device':device,'options':{'audio_input_path':str(source),
                        'audio_output_path':str(target),'model_path':str(ROOT/'models'/'voices'/'Deneme_RVC_200'/name),
                        'index_path':str(ROOT/'models'/'voices'/'Deneme_RVC_200'/'voice.index'),
                        'pitch':0,'index_rate':.75,'f0_method':'rmvpe','embedder_model':'contentvec'}},
                        progress=lambda message:print(message,flush=True))
                    validate_audio_file(target)
                    info = sf.info(target)
                    assert info.frames==round(sf.info(source).duration*info.samplerate)
                    health = session.execute('ping',{'device':device})
                    assert health['helper_cache_entries']==2
                    record = {'model':name,'kind':'cover','status':'passed','frames':info.frames,
                        'duration':info.duration,'sample_rate':info.samplerate,'helper_cache_entries':health['helper_cache_entries']}
                except Exception as error:
                    record = {'model':name,'kind':'cover','status':'failed','error':str(error)}
                record.update(seconds=round(time.monotonic()-start,3),worker_pid=ping['pid'])
                results.append(record)
                print(json.dumps(record,ensure_ascii=False),flush=True)
            assert session.execute('ping',{'device':device})['pid'] == ping['pid']
    evidence = {'date':'2026-10-13','parent_pid':__import__('os').getpid(),'backend':device,
                'synthetic_seconds':4,'personal_files_modified':False,'results':results,
                'note':'Process integration/finite output check; cold timings, no quality or full device certification.'}
    evidence_file = 'NATIVE_AUDIO_REAL_CHECK.json' if device=='cpu' else 'NATIVE_AUDIO_'+device.replace(':','_').upper()+'_REAL_CHECK.json'
    (ROOT/'docs'/evidence_file).write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return int(any(result['status']!='passed' for result in results))


if __name__=='__main__': raise SystemExit(main())
