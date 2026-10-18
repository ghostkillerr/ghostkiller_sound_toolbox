# Güncel durum — 19 Ekim 2026

| Konu | Doğrulanmış durum |
| --- | --- |
| Yayın | **2.1.0**, 18 Ekim 2026; `version.json`: `published`, CPU/CUDA hash ve URL kayıtları |
| Kurulumlar | CPU **373.825.544 bayt**, NVIDIA CUDA **2.136.828.435 bayt** |
| 2.1.0 yayın kaynağı | Yerel CPU/CUDA ortamlarında ayrı ayrı **363 test**; GitHub CPU/CUDA/XPU kaynak CI başarılı |
| Güncel yerel kaynak | 19 Ekim yenileme kaynağında CPU/CUDA ortamlarında ayrı ayrı **436 test** geçti. Fiziksel donanımla preflight ve pip check başarılı; bağımlılık kilitleri değişmedi |
| 2.1.0 frozen testleri | İki gerçek EXE geçti; CUDA'da fiziksel NVIDIA Torch backward ve ONNX CUDA oturumu da geçti |
| 2.1.0 Windows kurulumu | İki setup için ilk kurulum, aynı paketle yeniden kurulum, açılış ve kaldırma geçti; örnek kullanıcı dosyaları korundu |
| İmza | Kurulumlar dijital yayıncı sertifikasıyla imzalı değil; SHA-256 ve derleme receipt'leri yayımlandı |

[2.1.0 kurulumları](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0) · [Program sitesi](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/).
Projeye giriş [oku.md](../oku.md), yeni yayın reçetesi [RELEASE_BUILD.md](RELEASE_BUILD.md).

## Yayımlanmamış kaynak geliştirmesi

- RVC ara WAV'ı float hassasiyetinde tutulur. AI Cover ve eğitim dinleme
  örneklerinin 24 bit WAV/FLAC export'tan önce 16 bite düşmesi giderildi;
  gerçek `convert_audio` yazma yolundan geçen hassasiyet regresyonu eklendi.
- **4. Canlı AI Cover** sekmesi eklendi; **Ayarlar 5. sekmeye** taşındı.
  Kayıtlı RVC modeli, mikrofon/kulaklık, perde/benzerlik/dinleme düzeyi ve
  parça süresi seçimi; bellekte dönüşüm, sınırlı kuyruk ve başlat/durdur akışı
  uygulandı. Detaylar: [Canlı AI Cover](CANLI_AI_COVER.md).
- Canlı ses eşiği varsayılan -45 dB; dinleme sürerken değişebilir. Eşik altı
  tam bloklarda RVC çağrısı atlanır; konuşmalı blokların sessiz aralıklarında
  dönüştürülmüş dip sesi de susturulur. Günlük yalnız **Mikrofon açıldı.**
  satırını bir kez yazar; ilerleme durum alanındadır.
- **Otomatik ayarla (10 saniye sessizlik)** model/çıkış açmadan yalnız mikrofonu
  ölçer; mikrofon kapanmadan **Ayarlandı** duyurulmaz. 10 ms RMS ölçümlerinin
  yüzde 95 seviyesi +10 dB açılma, bunun 6 dB altı kapanma eşiğidir. 5 ms açılma,
  150 ms bekleme ve 120 ms kosinüs kapanma zarfı kullanılır. İptal, bağlantı
  hatası veya geçersiz ölçüm önceki ayarı korur; mikrofon değişince tekrar ölçülür.
  Kalibrasyon sesi saklanmaz; otomatik ölçüm sürekli arka planda sürmez.
  Kullanıcı 10 saniyelik otomatik ölçümün çalıştığını doğruladı. Sonraki kaynak
  düzenlemesinde -80 dB alt sınırı kaldırıldı; eşik doğrudan yazılıyor. Başarılı
  ölçüm, mikrofon/worker kapandıktan sonra **Dinleme tamamlandı** penceresi açar.
- Ses aygıtları native öğe verisiyle seçilir; açılan aygıtın numarası/adı
  doğrulanır ve ses yolu gösterilir. Line 2 için sessiz çıkış açılışında
  istenen/açılan kimlik eşleşti; mikrofon açılmadı, ses gönderilmedi. Eksik
  veya farklı aygıtta varsayılan çıkışa geçilmez.
- Doğrudan `main.py` açılışı kayıtlı GPU tercihi için hazır CUDA ortamını
  kullanır. RTX 5060 Ti yerel CUDA hesaplama testini geçti. Kişisel ayarlar
  yeniden yazılmadı; kurulu EXE ve worker/self-test açılışları yönlendirilmez.
- Yeni testler gerçek mikrofon açmadan native tampon sahipliği, model/index
  ömrü, yavaş dönüşümde eski sesin atlanması, durdurma/hata temizliği,
  beş sekme ve ortak işlem kilidi davranışlarını sınar. Windows aygıt
  listeleme ve format sorgusu mikrofon açmadan yerelde doğrulandı.
- Gerçek yerel RVC modeliyle sentetik ses; CPU ve NVIDIA CUDA'da sonlu,
  beklenen uzunlukta çıktı üretti. Model/index hash'leri korundu; mikrofon
  açılmadı. 500 ms parçanın işlemesi CPU'da 1,50–1,64 s, CUDA'da
  0,36–0,55 s sürdü. Bu ölçüm akustik gecikme veya dinleme kabulü değildir.
- Yerel günlükler: `build/live_cover_checks/`. Bu kaynak için yeni installer,
  frozen kabulü veya uzak CI yayını yapılmadı. Yayımlanan 2.1.0 paketleri
  bu değişiklikleri içermez. Gerçek mikrofonla ses kalitesi ve gecikme,
  aygıt çıkarma/yeniden bağlama ve canlı NVDA/JAWS kabulü açıktır.
  Ses eşiği/yönlendirme/açılış düzeltmelerinin son test ve preflight günlükleri
  `build/live_cover_fixes/` içindedir.
  Otomatik gate ölçümünün son CPU/CUDA testleri, preflight ve pip check
  günlükleri `build/auto_gate_checks/` içindedir. Mikrofon açılmadan sentetik
  sinyaller ve taklit aygıtlarla sınandı; gerçek mikrofon kabulü henüz yapılmadı.
  Son eşik alt sınırı/sonuç penceresi regresyonları `build/gate_threshold_checks/`
  altında; CPU/CUDA'da ayrı ayrı 77 ilgili test geçti. Testlerde fiziksel
  mikrofon açılmadı, sonuç pencereleri taklit edildi.
  Sürüm numarası kullanıcının talimatıyla **2.1.0** korunarak CPU/CUDA
  kurulumları yeniden hazırlanıyor. Güncel tam test/derleme kanıtları
  `build/release_20261019_live/` altında; paket içi self-test canlı gate ve
  sentetik 10 saniye ölçümünü fiziksel mikrofon açmadan da sınar.

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
