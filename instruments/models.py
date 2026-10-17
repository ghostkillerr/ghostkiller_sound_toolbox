"""Only fixed publisher weights, weights-only loading and known constructors."""
from pathlib import Path
from . import profile_for


def load_model(profile, model_root, device='cpu', cancelled=None):
    import torch
    from model_manager import file_digest
    from rvc.infer.model_validation import checkpoint_archive_precheck
    spec = profile_for(profile)
    path = Path(model_root)/spec['asset']
    if not path.is_file() or path.stat().st_size != spec['size'] or file_digest(path,cancelled) != spec['sha256']:
        raise ValueError('Enstrüman modeli doğrulanamadı. Ayarlar’dan seçilen modeli indirin veya onarın.')
    checkpoint_archive_precheck(path)
    if profile == 'scnet':
        from .vendor.SCNet import SCNet
        state = torch.load(path,map_location='cpu',weights_only=True)
        model = SCNet()
        weights = {key.removeprefix('module.'):value for key,value in state['best_state'].items()}
    else:
        from fractions import Fraction
        from audio_separator.separator.uvr_lib_v5.demucs.htdemucs import HTDemucs
        # The official checkpoint stores its class by the original module name.
        # No sys.path aliasing and no unrestricted pickle execution are needed.
        with torch.serialization.safe_globals([(HTDemucs,'demucs.htdemucs.HTDemucs'),Fraction]):
            state = torch.load(path,map_location='cpu',weights_only=True)
        if state['klass'] is not HTDemucs or state['args'] or tuple(state['kwargs']['sources']) != spec['stems']:
            raise ValueError('Altı kanallı modelin mimarisi beklenen modelle eşleşmiyor.')
        model = HTDemucs(**state['kwargs'])
        weights = state['state']
    model.load_state_dict(weights,strict=True)
    if tuple(model.sources) != spec['stems']:
        raise ValueError('Modelin çıkış kanalları desteklenen profile uymuyor.')
    return model.to(device).float().eval()
