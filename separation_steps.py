"""Separation catalog without optional engine imports."""

SEPARATION_STEPS = (
    ("melband_roformer_inst_v2.ckpt", "Enstrümantal Çıkarma", "(Instrumental)", "_Ghostkiller_Enstrumantal.flac"),
    ("model_bs_roformer_ep_317_sdr_12.9755.ckpt", "Ana Vokal Ayrıştırma", "(Vocals)", "_Ghostkiller_1_Ayrilmis_Vokal.flac"),
    ("mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", "Arka Vokal Temizliği", "(Vocals)", "_Ghostkiller_2_ArkaSes_Silinmis.flac"),
    ("UVR-DeEcho-DeReverb.pth", "Yankı Temizliği", "(No Reverb)", "_Ghostkiller_3_Yankisiz_Vokal.flac"),
    ("UVR-DeNoise.pth", "Gürültü Temizliği", "(No Noise)", "_Ghostkiller_4_Gurultusuz_Vokal.flac"),
)
