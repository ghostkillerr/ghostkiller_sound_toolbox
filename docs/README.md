# Belgeler

Projeye başlayacak ajan ve geliştiriciler önce [oku.md](../oku.md) dosyasını
okumalıdır. Güncel doğrulama ve sıradaki işler [Son durum](SON_DURUM.md) içindedir.
Bu dizin kullanım ve teknik kararları içerir; günlük çalışma geçmişi burada tutulmaz.

| İhtiyaç | Belge |
| --- | --- |
| Projeyi geliştirmek ve yayımlamak | [oku.md](../oku.md) |
| Kod incelemesi, düzeltmeler ve disk temizliği | [22 Ekim ayrıntılı inceleme](KOD_INCELEMESI_2026-10-22.md) |
| İlk denemeyi yapmak | [Kullanıcı kabulü](KULLANICI_KABULU.md) |
| Enstrümanları ayrı kaydetmek | [Enstrüman ayırma](ENSTRUMAN_AYIRMA.md) |
| Kısa vokal kayıplarını onarmak | [Vokal onarımı](VOKAL_ONARIMI.md) |
| Mikrofonu ses modeliyle dinlemek (deneysel kaynak) | [Canlı AI Cover](CANLI_AI_COVER.md) |
| Ses modeli eğitmek | [Model eğitimi](MODEL_EGITIMI.md) |
| Donanım ve modelleri hazırlamak | [Donanım ve model yönetimi](DONANIM_VE_MODEL_YONETIMI.md) |
| CPU/CUDA kurulumlarını üretmek | [Yayın derlemesi](RELEASE_BUILD.md) |

Motorun teknik sınırları [RVC çıkarımı](INFERENCE_RELEASE_FIXES.md),
[eğitim](TRAINING_RELEASE_FIXES.md) ve [araştırma kararlarında](RAPOR_UYGULAMA.md)
açıklanır. [Vokal onarımı araştırması](VOKAL_ONARIMI_ARASTIRMASI_2026-10-16.md)
model seçiminin gerekçesini saklar. Kişisel yol ve ayar bilgisi içerebilen
yerel ölçüm raporları Git dışındaki `build/local_reports/` klasöründedir.
`REVIEWED_UVR_SOURCE_HASHES.json` yalnız kamuya açık üretici modellerinin
kaynak ve dosya kimliklerini içerir.
