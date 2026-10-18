# Güncel durum — 18 Ekim 2026

| Konu | Doğrulanmış durum |
| --- | --- |
| Kaynak sürümü | `version.json`: **2.1.0**, `unpublished`, `packages: {}` |
| Kaynak testleri | CPU ve NVIDIA CUDA ortamlarının her birinde **361 test geçti** |
| Yayın paketi | Güncel kaynakla iki yeni installer üretilecek; hazır Release yok |
| Sonraki adım | Gerçek ses/kullanım kabulü ve CPU/CUDA installer doğrulaması |

Kaynak gönderimi kurulu uygulamaları güncellemez. Eski paket/sandbox raporları
güncel yayın kabulü sayılmaz. Projeye giriş ve kod haritası [oku.md](../oku.md),
derleme adımları [RELEASE_BUILD.md](RELEASE_BUILD.md) içindedir.

## Kaynakta tamamlananlar

- Vokal temizleme, dört/altı kanal enstrüman ayırma, RVC ses değiştirme ve
  kayıt inceleme/durdur-devam/karşılaştırma/oturum/sıra içeren model eğitimi.
- Ortak ve kalıcı MP3/WAV/FLAC/OGG, mevcut kanal düzeni/mono/stereo tercihleri.
  Zincir içi ses kayıpsız kalır; kullanıcı çıktısına `separation.json` yazılmaz.
- Ses adlarında program eki yoktur; çakışan dosya ve klasörler numaralanır.
  Önceki sonuçlar korunur; sonuç mesajı kapatılınca çıktı klasörü açılır.
- Biçim/kanal/donanım özeti odaklanabilir. Model hazırlama düğmesi yalnız
  seçili işlemin modelleri hazır değilse görünür ve yalnız bu eksikleri hazırlar.
- Model bütünlük/onarım kontrolleri, boyut sorgusu, disk alanı kontrolü ve
  sunucu destekliyorsa doğrulanmış yarım indirmeyi sürdürme.
- Türkçe ondalık girişi ve çözüm öneren yaygın hata mesajları.
- Açılışta geliştirici mesajından önce güncelleme denetimi; yalnız yeni sürüm
  varsa indirme onayı. Evet ile güncelleme; Hayır/iptal/hata ile normal açılış.
- İsteğe bağlı A2SB kısa vokal onarımı ve deneysel HTDemucs koşullarının
  indirme/kullanım öncesinde gösterilmesi. Standart ve onarılmış sonuç ayrıdır.

## Doğrulama ve yerel dosyalar

Son tam kaynak testleri: `build/usability_20261018/cpu_verified.log` ve
`cuda_final.log`. Son eğitim ayarı/preset değişikliği CPU'da ayrıca **29 testle**
doğrulandı: `training_preferences.log`. Testler gerçek ses codec'lerini,
numaralandırmada yarış durumunu, eski sonuçların korunmasını, koşullu model
hazırlığını, güncelleme/iptal akışlarını ve kısmi indirme doğrulamasını kapsar.

Test günlükleri ve temizlik denetimleri Git dışındaki `build/` altında tutulur.
Eski geçici test raporları ve yeniden üretilebilir önbellekler temizlenir;
kişisel kayıt/ayar/modeller, ortamlar, dağıtım/lisans materyali ve Git kurtarma
yedekleri korunur. Yerel kanıt dosyaları temiz klonda bulunmak zorunda değildir.

## Yayından önce açık işler

1. Gerçek sesle dört/altı kanal sonuçları, standart/onarılmış vokal ve cover'ı
   dinlemek; uzun eğitim, durdur/devam ve çıkan modelin kısa dönüşümünü denemek.
2. Bütün ekranlarda klavye, NVDA/JAWS anonsları ve odak sırasını değerlendirmek.
   Enstrüman düğmelerinin açık/kapalı okuması kullanıcı tarafından kabul edildi;
   bu kabul bütün arayüze genellenmez.
3. Aynı güncel kaynak/sürümden CPU ve NVIDIA CUDA installer'larını üretmek;
   frozen, temiz Windows ve uygun fiziksel donanım kontrollerini tamamlamak.
4. Eski kurulumdan aynı backend yükseltmesi, model/ayar koruma, UAC kabul/iptal,
   otomatik denetim açık/kapalı, elle denetleme ve geçici setup temizliğini sınamak.
5. İki gerçek installer'ın receipt/hash/boyutu doğrulandıktan sonra Release ve
   güncelleme manifestini yayımlamak. Yayın tarihi veya indirme bağlantısı uydurulmaz.

Kaynak testleri ses kalitesi, canlı ekran okuyucu veya yeni installer kabulünün
yerine geçmez. Kullanıcıdan beklenen denemeler [KULLANICI_KABULU.md](KULLANICI_KABULU.md).
