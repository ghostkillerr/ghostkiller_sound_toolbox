# Eğitim için yayın düzeltmeleri

13 Ekim 2026. Bu belge eğitim alt sistemindeki değişiklik ve doğrulama kapsamını
kaydeder; fiziksel AMD/Intel GPU veya ekran okuyucu doğrulaması değildir.

| Bulgu | Düzeltme | Senaryo |
| --- | --- | --- |
| R08 | Her tamamlanmış D+G adımından sonra 300 saniyelik timer uygulanır. Epoch'un son batch cursor'u da geçerli checkpoint'tir. | Tek batch'li 10 epoch; sanal saatte 305. saniyede kayıt, native çökme ikamesi ve devam. Model tensorleri, scheduler, Torch/Python/NumPy RNG son durumda kesintisiz referansla birebir eşleşir. |
| R11 | Boş/whitespace hata yerine açıklama, sayısal ve hex çıkış kodu, son aşama ve sınırlı log sonu gösterilir. | `0xC0000005`, boş manifest hatası, logda DLL yükleme hatası. |
| R12 | Ayrı heartbeat, canlı uzun işlem ile yanıt vermeyen worker ayrımı, sınırlı hata temizliği ve kullanıcı kontrollü zorla durdurma. Windows Job Object tüm worker/FFmpeg çocuklarını sahiplenir. | IPC callback hatası; eski/canlı heartbeat; açık zorla durdurma; gerçek Windows parent ve grandchild sonlandırması; eski checkpoint byte'larının korunması. |
| R16 | Resume `map_location='cpu', mmap=True` ile yüklenir; G/D ve optimizer state'leri sıralı tüketilir. | Gerçek trainer kontrol akışında CPU staging çağrısı ve tam devam eşdeğerliği. GPU tepe farkı bu birim testinin ölçümü değildir. |
| R17 | Örnek düzeyinde pozitif stride zorunlu. Tüm kayıtlar için gerçek parça sınırlarını/minimum uzunluğu hesaplayan disk tahmini; özellik, pitch, index kopyaları, eski+yeni checkpoint ve export rezervi. | 600 saniye, 1 saniye parça ve 0.9 saniye örtüşme: 5.991 parça. Yetersiz diskte decode başlamaz ve kaynak değişmez. |
| R24 | Analiz/eğitim/model kayıt sonuçları native odaklı mesaj penceresinde bildirilir; ardından sonuç alanına odak döner. Zorla durdurma klavye erişimli ayrı kontroldür. | Native wx kontrol durumu ve açık Evet/Hayır akışı. NVDA/JAWS ile fiziksel ölçüm hâlâ gerekir. |

Ek sağlamlaştırmalar: her eğitim oturumu için süreçler arası `worker.guard`
kilidi; aynı oturumun ikinci worker'ı manifest/checkpoint değiştirmeden
reddedilir. Yeni atomik kayıtların yarım dosyaları yalnız hedef adıyla başlayan
dosya adlarıyla oluşturulur. Kilit altında yalnız bu isimli, doğrudan oturum
klasörüne ait yarım kayıtlar temizlenir; genel `.part` dosyaları korunur.
AI Cover kayıt yazısı ortak süreçler arası kilitle yeniden oku/değiştir/yaz
API'sine taşındı. Eğitim kaynakları ve seçilmiş kullanıcı modelleri değiştirilmez.

CUDA/ROCm ve Intel XPU işlemleri ortak cihaz katmanını kullanır; temizlik,
bellek örneklemesi ve RNG işlemleri seçilen cihaza bağlıdır. Eski `cuda_rng`
checkpoint alanı yüklenebilir; yeni kayıtlar `device_rng` kullanır. Bir backend'in
kodda bulunması, onun her kart/model kombinasyonunda fiziksel test edildiği
anlamına gelmez. Normal durdurma yarım optimizer adımını kaydetmez; zorla
durdurma yalnız önceden atomik kaydedilmiş durumu korur.

Odaklı doğrulama: `test_training_release.py` **17 test başarılı**,
mevcut `test_training.py` **15 test başarılı**. Testler sentetik/geçici dosyalar
kullanır. Tam uygulama regresyonu ve gerçek CUDA uçtan uca testi ana yayın
düzeltme raporunda ayrıca kaydedilir.

İkinci kaynak incelemesinde force-kill sonrası yarım dosya birikmesi ve aynı
oturuma iki worker başlatma riski bulundu; yukarıdaki dar kapsamlı temizleme
ve oturum kilidiyle giderildi. Temiz Windows paketi, fiziksel AMD/Intel GPU,
NVDA/JAWS, DPI/yüksek karşıtlık ve gerçek uzun kayıt kalite testleri bu
kod/test değişiklikleriyle tamamlanmış sayılmaz.

İkinci doğrulama turunda RNG backend'i değişirken GPU RNG'nin sessizce
atlanabileceği bulundu. Yeni oturum/checkpoint `rng_layout` içinde backend,
CUDA/HIP ayrımı, GPU sayısı ve seçili GPU index'ini kaydeder. CPU/GPU, CUDA/HIP,
XPU, GPU sayısı veya seçili index değişirse tam devam açık hatayla reddedilir.
Eski CPU checkpoint'leri desteklenir; eski CUDA kayıtları yalnız GPU 0 ve
eşleşen RNG sayısıyla kabul edilir. Eksik legacy metadata HIP'e veya başka
GPU index'ine sessiz geçiş sağlamaz.

Parent `controller.guard` kilidi çalışma süresince tutulur; aktif worker'ın
`worker.guard` kilidi başlangıçta ayrıca kontrol edilir. İkinci denetleyici veya
aktif raw worker varsa cancel/heartbeat/checkpoint dosyaları değiştirilmez.
Bu iki durum marker byte'larını koruyan regresyonla doğrulandı.

Gerçek RTX 5060 Ti'de küçük ikame ağlar, gerçek CUDA AdamW ve CUDA RNG ile
deterministik checkpoint A/B testi geçti: G/D tensorleri, scheduler,
CPU/GPU Torch RNG, Python ve NumPy RNG birebir eşleşti. Kanıt
`TRAINING_FIXED_CUDA_CHECKPOINT_EXACT.json`. Bu test tam RVC GAN'ın her CUDA
kernelinde bit düzeyinde tekrarlanabilirlik veya ses kalitesi kanıtı değildir.
Gerçek RVC durdur/devam/index/dört cover doğrulaması
`TRAINING_FIXED_REAL_CHECK.json` içinde ayrıca kaydedilir.

Gerçek CUDA uçtan uca doğrulaması geçti: 6. adımda epoch 1/cursor 6/batch 1
ile durdurma, CPU/mmap checkpoint'ten devam, toplam 12 GAN adımı, 354 vektörlü
güvenli FlatL2 okuma ve iki adayın index kapalı/açık dört cover çıktısı.
Dört ses sonlu/dolu olarak doğrulandı. Son holdout mel L1 yaklaşık 0.7792;
bu sentetik ses deneyinin ölçümüdür, kalite puanı değildir. Olay örneklerinde
tepe VRAM 10.164 MiB (yaklaşık 9.93 GiB), worker RSS 3.679 MiB oldu; evrensel
minimum sistem gereksinimi veya eşit koşullu benchmark değildir.

Gerçek yardımcı model doğrulaması güncel şema/CRC/yayıncı SHA-256 kontrolünü
kullandı; yalnız geçici kontrol kaydı yazıldı. Kaynak ağırlıklar, `models.json`,
`settings.json` ve kişisel `.integrity.json` SHA-256 değerleri değişmedi.
Kanıt JSON'u ve log korundu; bu turda oluşturulan beş sentetik session/fixture
klasörü, mutlak hedef ve doğrudan `training_runs` ebeveyni doğrulandıktan sonra
temizlendi.

Gerçek checkpoint 1.295.040.257 byte ölçüldü. Sabit pretrained G/D dosyaları
FP16 olduğundan, yalnız dosya boyutunu üç Adam/weight kopyasıyla çarpmak
FP32 genişlemesini kaçırıyordu. Taze oturum rezervi iki FP32 checkpoint
neslini, iki Adam slotunu ve üç FP32 export kopyasını kapsayacak şekilde
genişletildi; FP16 boyut senaryosu regresyonla doğrulandı.
