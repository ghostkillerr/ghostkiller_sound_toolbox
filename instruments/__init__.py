"""Instrument profiles; importing the catalog never loads a neural network."""
DEMUCS_TERMS_URL = 'https://github.com/facebookresearch/demucs/issues/327'
DEMUCS_USAGE_NOTICE = (
    'İsteğe bağlı altı kanallı HTDemucs modelinin ağırlıkları, üreticinin '
    'açıklamasına göre yalnız bilimsel amaçlarla sunulmaktadır. Demucs kaynak '
    'kodunun MIT lisansı bu ağırlıklara ticari kullanım hakkı vermez. '
    'İndirmeden veya kullanmadan önce üreticinin açıklamasını inceleyin ve '
    'yalnız izin verilen bilimsel amaçlarla devam edin. Gitar ve özellikle '
    'piyano çıktıları deneyseldir. Dört kanallı SCNet ayrı bir modeldir.'
)
STEM_LABELS = {'bass':'Bas', 'drums':'Davul', 'guitar':'Gitar', 'piano':'Piyano',
               'vocals':'Vokal', 'other':'Diğer enstrümanlar'}
PROFILES = {
    'scnet': {'label':'Dengeli — 4 kanal (SCNet)', 'asset':'instruments/scnet_base.th',
              'stems':('drums','bass','other','vocals'),
              'url':'https://drive.usercontent.google.com/download?id=1CdEIIqsoRfHn1SJ7rccPfyYioW3BlXcW&export=download&confirm=t',
              'sha256':'f8aff3bc8dd816aad392800d9d69519add719a2fbd22550af6f8cb2138d25ff5',
              'size':42434545},
    'demucs6': {'label':'Ayrıntılı — 6 kanal (deneysel; bilimsel kullanım)',
                'asset':'instruments/htdemucs_6s.th',
                'stems':('drums','bass','other','vocals','guitar','piano'),
                'url':'https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/5c90dfd2-34c22ccb.th',
                'sha256':'34c22ccb381c6f9fdbf324f04e1e2fe21aaaf293f5ded163a162697ff9a02ddd',
                'size':54996327},
}


def profile_for(key):
    if key not in PROFILES:
        raise ValueError('Enstrüman ayırma modeli geçersiz.')
    return PROFILES[key]
