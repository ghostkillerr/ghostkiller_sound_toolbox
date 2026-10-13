# Yerel tek kişilik RVC model eğitimi

## 13 Ekim: eğitim arayüzü temeli

- Üçüncü sekmede **Kayıtları analiz et**: kaynakları değiştirmeden, geçici
  dosyada akış halinde çözümleyip süre, kanal, RMS, tepe, sınırdaki örnekler,
  düşük seviyeli pencere oranı, dosya tekrarı ve mono enerji kaybını ölçer.
  RAM'e tüm kayıt alınmaz; dosyalar sırayla işlenir. Analiz iptal edilebilir.
- Analiz eğitim öncesinde tekrar yapılır; kaynak SHA-256 değerleri kontrol edilir.
  Rapor oturumda `quality_report.json` ve `quality_report.txt` olarak saklanır.
  −60 dBFS / 100 ms düşük seviye ölçümü bir sezgiseldir; gürültü, yankı,
  vokal kimliği veya veri çeşitliliğini doğrulamaz. Araştırma raporu gelmeden
  otomatik temizleme, perde ayarı veya kalite puanı uygulanmaz.
- Tam D/G optimizasyon adımlarından sonra yaklaşık beş dakikada bir atomik
  devam kaydı alınır. Değerlendirme aralığındaki kayıtlar ve kullanıcı
  durdurmasındaki kayıt devam eder. Ani güç kaybında son kayıt sonrası adımlar
  tekrar işlenir; kayıt yazımı ve uzun bir adım bu aralığı uzatabilir.
- Eğitim hızı ölçüldükten sonra kalan süre tahmini gösterilir. Tahmin o eğitim
  oturumunun hızına dayanır; final index ve cover testlerini kapsamaz.
- **Kayıtlı eğitim oturumu aç** tamamlanmış sonuçları yeniden eğitim
  başlatmadan açar. Devam sırasında form kayıtlı ayarlara döner; formdaki
  değişiklikler var olan optimizasyon durumuna sessizce uygulanmaz.
- AI Cover'a kayıt, SHA-256 ile doğrulanan model/index kopyasını kayıt
  dosyasının yanındaki `trained_models/` klasörüne koyar. Oturum klasörünün
  sonraki temizliği kayıtlı modeli silmez. Aynı model adı ezilmez.
- Model matematiği, FP32, başlangıç ağırlıkları ve değerlendirme ölçütü bu
  değişiklikte değiştirilmedi. Gerçek NVDA/AMD/paketli EXE doğrulaması ayrıdır.

Doğrulama: 102 regresyon testi başarılı. Ayrıca CPU / iki thread / batch 1 ile
iki altı saniyelik sentetik kayıt analizden geçti; gerçek RVC eğitiminde altıncı
adımda durdurma, tam checkpoint'ten devam, 354 vektörlü index ve iki export'un
gerçek AI Cover testi tamamlandı. Devam sonrasında toplam adım yine altıydı.
Örneklenen süreç RAM'i en yüksek yaklaşık 2.8 GiB idi; bu kısa testin kaynak
ölçümüdür, uzun kayıt veya ses kalitesi garantisi değildir. Bu testin sesleri,
ağırlıkları ve checkpoint'i doğrulama sonrası temizlendi.

## Kullanım

1. **4. Ayarlar:** CPU/GPU tercihini belirleyin ve donanım kontrolünü tamamlayın.
   ContentVec, RMVPE ve seçilecek örnekleme hızının **eğitim G/D ağırlıklarını**
   indirin/kontrol edin. CREPE seçilirse eğitim RMVPE gerektirmez.
2. **3. Model Eğitimi:** Aynı kişiye ait kayıtları ekleyin, model adını yazın.
   Başlangıç: 40 kHz, 200 epoch, otomatik batch, checkpoint/değerlendirme 10 epoch.
3. Gelişmiş seçenekler: öğrenme hızı, parça/örtüşme süresi, değerlendirme payı,
   CPU thread sınırı, F0 yöntemi ve gradyan checkpointing.
4. Eğitim sonunda `latest.pth` ve en düşük holdout mel hatasının adayı
   `best_validation.pth` oluşturulur. İki adaya ait test WAV'larını dinleyin.
   Seçili adayı **AI Cover'a ekle** ile kayıt edin. Mevcut adların üzerine yazılmaz.
5. İptal düğmesi tam G/D optimizasyon adımı bitince devam noktası kaydeder.
   **Eğitim oturumu seç ve devam et** aynı oturum/ayarlarla kaldığı yerden devam eder.

Öğrenme hızı/batch/epoch değerleri evrensel kalite optimumu değildir. Çok fazla
epoch overfit yapabilir. Mel hatası aynı kişinin ayrılmış kaydındaki yeniden
üretim hatasıdır; tını benzerliği, cover kalitesi veya insan tercihinin yerine geçmez.
Değerlendirme kaydı da düşük gürültülü ve temsil edici olmalıdır.

## Kaliteyi koruyan hat

- Kaynaklar FFmpeg/SoXR ile mono ve seçilen hıza, float32 WAV'a çevrilir.
  Uzun ses tamamıyla RAM'e alınmaz. Gürültü azaltma, pitch değişimi, otomatik
  ses yükseltme, lossy yeniden sıkıştırma uygulanmaz. Peak .95'i aşarsa yalnızca
  kazanç azaltılır; kaynakta bulunan clipping böylece onarılmış sayılmaz.
- Kaynak SHA-256 ile aynı dosyanın kopyaları tekilleştirilir. Birden fazla özgün
  kayıtta kaynak dosya bazında split yapılır. Aynı oturumun farklı dosyaları
  otomatik tanınmaz; kullanıcı oturum/ortam çeşitliliğini dikkatle seçmelidir.
  Tek kayıtta son bölüm ayrılır, sınırdan geçen örtüşmeli parça üretilmez.
  Dosya bazında ayırmada gerçek holdout payı seçilen yüzdeden sapabilir.
- ContentVec 768 özellikleri ve F0 çıkarımı ayrı geçişlerle yapılır; büyük
  modeller aynı anda bellekte tutulmaz. V2 / F0 / HiFi-GAN / tek konuşmacı profili
  uygulamanın kendi `Synthesizer` mimarisiyle eğitilir.
- G ve D pretrained ağırlıklarının bütün zorunlu katmanları/boyutları kontrol edilir.
  Eksik katmanları rastgele başlatıp devam edilmez. Başlangıç ağırlıkları pinned
  kaynak revision ve yayıncı SHA-256 ile doğrulanır.
- Eğitim ve export FP32'dir. AMP, FP16 ağırlık export'u ve TF32 etkinleştirilmez.
  GAN kayıpları: adversarial, feature matching, mel L1 ve KL; AdamW ve exponential
  LR scheduler. Gradyan checkpointing aynı hesaplamayı tekrar ederek belleği azaltır.
- NaN/Inf loss veya gradyan eğitimi durdurur. Böyle bir yarım optimizasyon
  adımının ağırlıkları sağlam devam noktasının üzerine yazılmaz.
- FAISS index yalnız eğitim özelliklerinden, **tam FlatL2 komşu aramasıyla**
  üretilir. IVF yaklaşık araması, KMeans azaltımı veya quantization uygulanmaz;
  bütün eğitim vektörleri korunur. Bu tercih retrieval doğruluğunu korur;
  çok büyük veri setlerinde cover dönüşümünün index araması daha uzun sürebilir.
- Export sonrası gerçek `VoiceConverter` ile kısa holdout sesi dönüştürülür.
  Dosya çözümlenebilirliği ve sonlu örnekler kontrol edilir. Ancak bu kontrol
  bir ses kalitesi değerlendirmesi değildir. Kayıttan hemen önce model/index
  hash'leri tekrar doğrulanır.

## Kaynak kullanımı

GUI işçisi ayrı süreçtır. Kaynak/bellek ölçümü yaklaşık 5 saniyede bir ve aşama
sonlarında yapılır. RAM çalışma kümesi, boş RAM, CPU süreç kullanımı ve CUDA
ayrılan/rezerve/tepe/boş VRAM değerleri oturum günlüğüne kaydedilir. CPU yüzde
hesabında bir çekirdek %100'dür; %200 iki çekirdeğe eşittir. VRAM ölçümü GPU
hesaplama kullanım yüzdesi değildir.

CUDA allocator fiziksel VRAM'in en fazla %85'iyle ve mevcut boş VRAM'e göre
daha düşük bütçeyle sınırlandırılır. Böylece Windows shared RAM'e taşma azaltılır.
Gereksiz D feature-map referansları G hesaplamasından önce bırakılır. Ölçülen
bellek baskısında yalnız boş cache blokları bırakılır; canlı tensörler korunur.

Auto GPU batch 4/2/1 tam ileri/geri GAN adımlarıyla ölçülür. Deneme güncellemeleri
ve optimizer state atılır, pretrained ağırlıklar ve RNG geri yüklenir; eğitim
deneme adımlarını saymaz. CPU Auto muhafazakâr olarak batch 1 dener. Kullanıcı
batch seçtiyse eğitim sırasında otomatik değiştirilmez. Bellek hatasında örnekleme
hızı, ağ boyutu veya precision sessizce düşürülmez. Batch 1 de sığmıyorsa iş durur.

CPU thread sayısı torch, OMP, MKL ve OpenBLAS'a aktarılır. DataLoader worker/
prefetch/GPU dataset cache kullanılmaz; her batch diskten okunur. UI günlük metni
sınırlıdır, tam günlük diskte kalır. FAISS ekleme parçalıdır. Index dosyasının
kendisi ve inference sırasındaki index reconstruction'ı veriyle birlikte büyür;
sınırsız veri için sabit RAM garantisi yoktur.

## Oturum ve devam

`training_runs/<ad>_<id>/` Git dışında tutulur. Dosyalar:

- `manifest.json`: backend commit, seçenekler, precision, cihaz, Python/torch
  sürümleri, yardımcı modellerin hash kayıtları ve hazırlanmış veri hash'leri.
- `dataset.json`: kaynak hash'leri, süre/peak/RMS/clipping, split ve parça sınırları.
- `resume.pth`: G/D, iki optimizer, iki scheduler, epoch/batch cursor, step,
  batch ve Python/NumPy/torch/CUDA RNG. Temp dosya + fsync + replace ile yazılır.
- `latest.pth`, `best_validation.pth`, `voice.index`, test WAV'ları, `result.json`.
- `events.jsonl`, `worker.log`, `metrics.jsonl`: kaynak ölçümleri, hata ve holdout metriği.

Kaynak dosyalar sonradan kaldırılmışsa hazırlanmış verisi tamamlanmış oturumdan
devam edilebilir. Hazırlanmış ses/özellik dosyaları veya yardımcı model hash'leri
değişmişse devam reddedilir. İptal edilince ara dosyalar korunur. Güç kesintisi
veya hata sonrasında son **kaydedilmiş** checkpoint kullanılabilir; aralık içindeki
kaydedilmemiş adımlar kaybolabilir. Aynı seed farklı donanımda bit düzeyinde aynı
sonucu garanti etmez. Bu işlem finetune veya başka `.pth` dosyasından resume değildir.

## Kaynaklar ve doğrulama sınırları

Applio 3.6.5 commit `55fe0b976a6990bb75261c32ccecf6bfca3198f1` eğitim
primitifleri/config'leri MIT lisansıyla `training/vendor` içinde; yerel değişiklikler
`NOTICE.md` içinde belirtilmiştir. Orijinal GUI/launcher kullanılmaz.

- [Applio pinned kaynak](https://github.com/IAHispano/Applio/tree/55fe0b976a6990bb75261c32ccecf6bfca3198f1)
- [RVC pretrained ağırlıkları](https://huggingface.co/lj1995/VoiceConversionWebUI/tree/e6d0c1a17da07c33557852f9dfa2bd44cc75737d/pretrained_v2)
- [Applio eğitim rehberi](https://docs.applio.org/getting-started/training/)

CPU ve PyTorch CUDA/uyumlu ROCm kod yolu vardır. AMD markasını görmek eğitim
desteği sayılmaz; gerçek backward/optimizer çalışması gerekir. AMD donanım testi,
uzun CPU eğitimi, 32/48 kHz gerçek ağırlık denemeleri ve paketli EXE/NVDA testi
ayrı doğrulamalar gerektirir. Otomatik test ve sentetik sesle kısa tam eğitim,
profesyonel şarkı tınısının doğrulandığı anlamına gelmez.

## 11 Ekim 2026 yerel doğrulama

40 kHz resmi G/D, yerel ContentVec ve RMVPE ile iki adet 6 saniyelik **sentetik**
kayıt, 1.2 saniyelik parçalar ve 0.3 saniye örtüşme kullanıldı. Bu testler yalnız
hattın çalışması, format ve kaynak kontrolü içindir. Son FlatL2 index, CPU'da
iki gerçek export ile ayrıca dönüştürülüp kontrol edildi.

| Deneme | Sonuç |
| --- | --- |
| NVIDIA CUDA, Auto batch | Gerçek GAN ölçümü batch 4 seçti; 1 epoch / 2 adım, iki aday için gerçek AI Cover testi geçti. |
| NVIDIA iptal/devam | 1. epoch sonunda iptal; optimizer/scheduler/RNG ve cursor kaydedildi; 2 epoch / 4 adım tamamlandı. Değerlendirme cache'inin backward'ı bozduğu hata bulundu ve regresyon testiyle düzeltildi. |
| CPU, 2 thread, batch 1 | 1 epoch / 6 adım, index ve iki aday için gerçek AI Cover testi geçti. |

Optimize GPU testinde süreç RAM'i yaklaşık 2.6 GiB; ölçülen tepe CUDA tensör
belleği yaklaşık 9.4 GiB oldu. CPU testinde ölçülen RAM yaklaşık 2.6 GiB'a ulaştı.
Bu sayılar kısa fixture'a aittir; uzun kayıt, farklı parça/batch veya donanımda
aynı bellek kullanımı vaat edilmez. Önceki cache referanslarıyla sistem RAM'ine
taşma gözlendi; gereksiz feature-map referansları ve CUDA boş cache yönetimi düzeltildi.

NVDA ile canlı kullanım, paketli EXE, AMD eğitimi ve gerçek şarkı kaydıyla
dinleme/kalite karşılaştırması bu doğrulamanın kapsamına dahil değildir.
