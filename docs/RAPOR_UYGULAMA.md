# 13 Ekim 2026 araştırma raporu: uygulama kararları

Kullanıcının `Downloads/deep-research-report.md` raporu mevcut RVC eğitim
altyapısıyla karşılaştırıldı. Raporun önerileri uygulama talimatı yerine kanıt
ve mühendislik önerileri olarak ele alındı. Dahili `turn...` kaynak işaretleri
tek başına dışarıdan doğrulanabilir bağlantılar olmadığından kritik kararlar
yerel sabitlenmiş kod ve erişilebilir birincil belgelerle kontrol edildi.

## Uygulananlar

- Kaynak listesinde aynı şarkı/oturum/stem için grup atama. Gruplar kesimden
  önce eğitim/değerlendirmeye ayrılır. SHA-256 ile aynı olan kopyalar farklı
  etiketler verilmiş olsa bile grupları birleştirir. Gruplar arasında geçişli
  eşleşmeler de aynı bölümde kalır. Bu yaklaşım otomatik yakın kopya bulucu
  değildir; farklı master/temizlenmiş kopyalar kullanıcı tarafından etiketlenir.
- Tek kayıt için zaman sınırı korunur fakat farklı şarkıda genelleme testi
  olmadığı belirtilir. Birden çok ayrı dosyanın tamamı tek gruptaysa bağımsız
  değerlendirme kaydı istenir; grup içi varyantlar farklı bölümlere dağıtılmaz.
- F0 çıkarımında eğitim ve değerlendirme için ayrı `pitch_report.json`:
  sesli çerçeve oranı, yaklaşık %5/medyan/%95, min/max, 0.1 MIDI-notalık
  histogram ve 50–1100 Hz sınır dışı oranı. Sayaçların belleği sabittir.
  Sıfır F0 örnekleri silinmez; nefes/ünsüz veya sessizlik olabilir. Örtüşmeli
  parçalardaki işlenmiş süre benzersiz sesli dakika olarak sunulmaz.
- Her aday için kısa, ayrı `index_rate=0` ve `index_rate=0.75` cover uyumluluk
  testleri. Bunlar ses kalitesi/benzerlik skoru değildir; dinleme gereklidir.
  Mel hatası en düşük aday ve son aday ayrı tutulur; kullanıcı seçer.
  Aday ve index açık/kapalı seçilerek test sesi varsayılan oynatıcıda açılır.
- Index'e eğitim/değerlendirmede paylaşılan feature dosyası girerse işlem
  durur. Yalnız eğitim özellikleri kullanılır; yinelenen feature yolları da
  reddedilir.
- Hazırlama parçası ve GAN optimizasyon segmentinin farklı olduğu arayüzde
  belirtilir. Profil segmenti paketlenmiş config'ten hesaplanır; sample rate
  değiştiğinde gösterim güncellenir.
- Yerel Windows ROCm eğitimine hem başlatma/devam hem worker girişinde
  açık hata verilir. GPU forward testi eğitim desteği diye sunulmaz; CPU
  kullanıcı tarafından seçilmelidir. DirectML bu uygulamada uygulanmadı.

## Otomatik değiştirilmemiş kararlar

- **40 kHz korunur.** Uygulama RVC upstream ana dalının dinamik config'lerini
  kullanmaz; Applio commit'i ve eşleşen V2 G/D ağırlıkları sabitlenmiştir.
  40 kHz export, gerçek eğitim ve kullanıcı dinlemesiyle doğrulanmıştır.
  Raporda başka upstream dizininde 40k config olmaması bu profili geçersiz
  yapmaz. Varsayılan 40 kHz ve hazırlama 3.0 / 0.3 saniye korunur.
- **IndexFlatL2 korunur.** FAISS'in resmi rehberi tam sonuç garantisi veren
  index'in Flat olduğunu; IVF aramasının nprobe ile hız/doğruluk ödünleşimi
  yaptığını belirtir. Kullanıcı kaliteyi öncelediği için yalnız upstream
  varsayılanına yaklaşmak adına yaklaşık arama veya KMeans azaltma eklenmedi.
  Bu karar Flat'ın işitsel olarak her veri kümesinde daha iyi olduğu iddiası
  değildir; uzun veri için hız/bellek optimizasyonu ayrı A/B gerektirir.
- FP32, otomatik batch'in CUDA'da dört ile başlayıp yalnız bellek ihtiyacında
  azalması, LR 1e-4, sabit optimizer ve resume/RNG semantiği korunur.
- Otomatik erken durdurma eklenmedi: mel veya GAN kaybının tek başına
  işitsel kaliteyi temsil etmediği raporun temel bulgularındandır.
- Otomatik denoise/dereverb, nefes silme, pitch/formant augmentation veya
  bant genişliğine göre gizli sample-rate değiştirme yapılmaz.

## Henüz uygulanmayanlar

Tam şarkı düzeyinde ayrı final-test bölümü, otomatik yakın-duplikat kümelemesi,
true-peak/flat-top QC, göreli gürültü/yankı skorları, hedef şarkıyla perde kapsama
karşılaştırması, speaker embedding, MOS, ASR ve index oranı sweep'i henüz
uygulamada yoktur. Ayrı model/ölçüm doğrulaması olmadan bunlar varmış gibi
puan veya otomatik "en iyi" seçimi gösterilmez. Mevcut peak sınırı ölçümü
true-peak veya doğrulanmış clipping diye adlandırılmaz.

## Kontrol edilen birincil kaynaklar

- [FAISS index seçimi](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index):
  tam arama ve IVF hız/doğruluk farkı.
- [AMD ROCm Windows sınırlamaları](https://rocm.docs.amd.com/projects/radeon-ryzen/en/docs-7.2/docs/limitations/limitationsrad.html):
  native Windows için "No ML training support".
- Sabitlenmiş Applio kaynak/lisansı: `training/vendor/NOTICE.md`.
- Kullanılan gerçek ayarlar: `training/vendor/config_32000.json`,
  `config_40000.json`, `config_48000.json` ve `model_manager.py` G/D kaynakları.

Gerçek NVDA, AMD cihaz, DirectML, paketli EXE ve kullanıcı ses kalitesi testleri
otomatik regresyon testlerinin yerine geçmez.

Yerel doğrulama: CPU, iki thread, batch 1 ile iki sentetik kayıtta gerçek
analiz/F0/eğitim, altıncı adımda durdurma ve devam, 354 vektörlü index ve iki
adayın index kapalı/açık dört ses testi tamamlandı. Yeni rapor dosyaları oluştu;
devam sonrasında toplam adım altı kaldı. Sentetik test ses kalitesini ölçmez.
