# Güncel durum — 18 Ekim 2026

| Konu | Doğrulanmış durum |
| --- | --- |
| Yayın | **2.1.0**, 18 Ekim 2026; `version.json`: `published`, CPU/CUDA hash ve URL kayıtları |
| Kurulumlar | CPU **373.825.544 bayt**, NVIDIA CUDA **2.136.828.435 bayt** |
| Kaynak testleri | Yerel CPU/CUDA ortamlarında ayrı ayrı **363 test**; GitHub CPU/CUDA/XPU kaynak CI başarılı |
| Frozen testleri | İki gerçek EXE geçti; CUDA'da fiziksel NVIDIA Torch backward ve ONNX CUDA oturumu da geçti |
| Windows kurulumu | İki setup için ilk kurulum, aynı paketle yeniden kurulum, açılış ve kaldırma geçti; örnek kullanıcı dosyaları korundu |
| İmza | Kurulumlar dijital yayıncı sertifikasıyla imzalı değil; SHA-256 ve derleme receipt'leri yayımlandı |

[2.1.0 kurulumları](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0) · [Program sitesi](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/).
Projeye giriş [oku.md](../oku.md), yeni yayın reçetesi [RELEASE_BUILD.md](RELEASE_BUILD.md).

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

## Doğrulama kanıtları

- [CPU kurulum kabulü](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/39149347756) ve [CUDA kurulum kabulü](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/39151347703):
  GitHub Windows 2022 makineleri, Python/CUDA/codec PATH girdileri kapalı.
  Bu CI etkileşimli UAC veya başka fiziksel GPU modeli kabulü değildir.
- [Yayın kaynak ağacının CPU/CUDA/XPU CI sonucu](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/39148030784).
- Yerel tam testler: `build/setup_audit_20261018/tests_cpu.log`, `tests_cuda.log`.
- Yeni EXE/ISCC günlükleri, gerçek GPU frozen raporları, build-info ve CI
  sonuçları: `build/release_20261018/`; setup/receipt'ler: `Setup/`.
- Her native test MP3/WAV/FLAC/OGG × mevcut/mono/stereo × mono/stereo girdi
  için 24 dönüşümü, kayıpsız hassasiyeti ve önceki çıktının korunmasını sınar.

Yerel raporlar temiz klonda bulunmak zorunda değildir. Kişisel kayıt/ayar/modeller,
çalışma ortamları, lisans/kaynak materyali ve Git kurtarma yedekleri korunur.
Derleme ara dosyaları yeniden üretilebilir; setup ve derleme kayıtları saklanır.

## Sürdürülen kullanıcı kabulü

1. Gerçek sesle dört/altı kanal sonuçları, standart/onarılmış vokal ve cover'ı
   dinlemek; uzun eğitim, durdur/devam ve çıkan modelin dönüşümünü denemek.
2. Bütün ekranlarda klavye, NVDA/JAWS anonsları ve odak sırasını değerlendirmek.
   Enstrüman düğmelerinin açık/kapalı okuması kullanıcı tarafından kabul edildi;
   bu kabul bütün arayüze genellenmez.
3. Etkileşimli UAC kabul/iptal, gerçek önceki sürümden güncelleme, otomatik/elle
   denetim ve geçici setup temizliğini kullanıcı ortamında sınamak. CI aynı
   paketle yeniden kurulum yapar; iki farklı yayın arasında güncelleme iddiası yoktur.
4. Diğer fiziksel GPU modelleri ve Windows kullanıcı profilleriyle denemek;
   sonraki yayın için dijital yayıncı sertifikası edinip imzayı doğrulamak.

Kaynak ve kurulum testleri ses kalitesi veya canlı ekran okuyucu kabulünün
yerine geçmez. Deneme adımları [KULLANICI_KABULU.md](KULLANICI_KABULU.md).
