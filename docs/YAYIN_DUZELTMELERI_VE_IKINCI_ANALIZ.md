# Kod düzeltmeleri ve ikinci analiz

Tarih: 13 Ekim 2026. Başlangıç: `YAYIN_ONCESI_TEKNIK_DENETIM.md` içindeki
R01–R28. Çalışma kaynak geliştirmesi, hata senaryoları ve yeniden incelemedir.
Kullanıcının son yönlendirmesiyle yeni EXE derleme/çalıştırma adımları durduruldu.
O yönlendirmeden önceki diagnostic derleme tamamlanmıştı; EXE çalıştırılmadı.
O çıktı yayın paketi sayılmaz ve yayın manifest aracı tarafından reddedilir.

Kod düzeltmesi ile bir cihazda fiziksel doğrulama ayrı değerlendirilir.
Bu çalışma bütün donanımlarda bütün seslerin hatasız çalışacağını kanıtlamaz.
Korunan kişisel sesler, RVC model/index dosyaları ve yardımcı ağırlıkların
byte içeriği değiştirilmedi. Mevcut beş hazır paketin derived
`models/.integrity.json` kayıtları offline tam kontrolle schema_version=2'ye yenilendi.

## Başlangıç bulgularının durumu

| Bulgu | Kodda yapılan çalışma | Kalan doğrulama / sınır |
|---|---|---|
| R01 P1 | CPU/CUDA-HIP/XPU cihaz katmanı; ayrı CPU/CUDA/XPU hash lock ve backend preflight | Fiziksel Intel/AMD GPU; doğrulanmış ROCm Windows lock henüz yok |
| R02 P1 | Eski Windows HIP sürümü ayrılır; uygun sürümde gerçek FP32 backward kontrolü | Her ROCm kart/runtime/model kombinasyonu fiziksel sınanmalı |
| R03 P1 | SystemExit hatası başarıya dönüşmez; cover/ayrıştırma GUI dışında native worker | Native worker bir güvenlik sandbox'ı değildir |
| R04 P1 | Win32 ShellExecuteExW runas; UAC iptali ayrı, uygulama açık kalır | Gerçek installer/UAC denemesi bu kaynak geliştirmesinde yapılmadı |
| R05 P1 | Backend/sürüm bağlı HTTPS GitHub asset, zorunlu SHA-256/boyut, redirect kontrolü; son hash ve Windows dosya paylaşım koruması | Yeni yayın metadata'sı gerçek imzalı/incelemiş installer hazırlanırken üretilmeli |
| R06 P1 | Tam hash lock, tek ORT dağıtımı, runtime/provider testi, temiz CPU venv ve CI/preflight | Kaynak CUDA ortamındaki çift ORT global olarak değiştirilmedi; temiz backend ortamı kullanılmalı |
| R07 P1 | RMVPE en çok 2048 frame/örtüşme, sınırlı STFT/mel, CPU F0 biriktirme, RAM ön kontrolü | Çok saatli ses bütünüyle diskten sentez desteği yok; uzun gerçek şarkı/az VRAM testi gerekir |
| R08 P1 | Timer son/tek batch'te de kayıt alır; terminal cursor/scheduler/RNG tutarlı | Fiziksel küçük CUDA A/B bit düzeyinde eşleşti; gerçek GAN kernel determinismi ayrı konu |
| R09 P1 | Erken kalıcı tanı, windowed stream, GUI'nin native motor importlarından ayrılması; kaynak probe'lar | Temiz Windows VM/paketli sürüm ileride dağıtım aşamasında sınanmalı |
| R10 P2 | JSON OS/thread kilidi altında read/modify/write, çatışma reddi, GUI singleton, snapshot merge | Kilit dosyaları derived koordinasyon dosyalarıdır |
| R11 P2 | Boş hata yerine worker exit code/aşama/log; checkpoint korunur | Yeniden üretme senaryosu geçti |
| R12 P2 | Worker heartbeat, bounded cleanup, ayrı kullanıcı kontrollü Zorla Durdur, Windows Job Object ağacı | GPU driver'ın işletim sistemini tamamen kilitlemesine kullanıcı süreci çözüm garantisi vermez |
| R13 P2 | Tam reconstruct_n kopyası yerine sınırlı komşu blokları; RAM bütçesi | FlatL2 kalite tercihi korunur, yaklaşık index'e geçiş yok |
| R14 P2 | Bir native işte tek converter; cihaz/dosya kimlikli en çok iki helper cache | İş sonunda yardımcı ağlar bırakılır |
| R15 P2 | Her parçada empty_cache kaldırıldı; yalnız seçili cihazda ölçülen baskı/iş sonu | Evrensel hız kazancı iddiası yok |
| R16 P2 | Resume CPU/mmap staging ve sırayla state aktarımı | Gerçek CUDA resume testi geçti; daha az VRAM kartta ölçüm gerekir |
| R17 P2 | Pozitif sample stride, gerçek overlap/tail parça sayısı, iki checkpoint nesli ve FP16→FP32/Adam disk rezervi | Kaynak/disk tahmini muhafazakâr; bütün veri profilleri için tek minimum değildir |
| R18 P2 | UTF-16 bounded, hashli çıktı adı; native motor kısa geçici input alias | Windows component sınırı korunur; aşırı uzun toplam klasör yolu ayrıca platform sınırına takılabilir |
| R19 P2 | Worker öncesi OMP/MKL/OpenBLAS/NumExpr sınırları, PyTorch ve FAISS sınırı | Hibrit CPU/laptop gerçek performans profili henüz ölçülmedi |
| R20 P2 | ContentVec/RMVPE commit ve sabit kaynak SHA-256; eski download API güvenli manager'a yönlendirilir | Diğer embedder ve ayrıştırma kaynaklarının güven/provenance kapsamı raporlarda açık |
| R21 P2 | RoFormer/UVR tam meta key/shape, bloklu sonluluk, archive/RAM sınırı | Hazır etiketi ses kalitesi garantisi değildir |
| R22 P2 | Üç native açık kalite seçeneği; eski varsayılanlar korunur, kanıtsız kalite yorumları kaldırılır | Kör gerçek ses A/B dinleme değerlendirmesi gerekir |
| R23 P2 | Notice/lisans/provenance toplama ve eksik kaynakta üretim kapısı; FFmpeg binary resmi arşivle eşleşti | Bağlı FFmpeg kütüphanelerinin tam kaynak/build materyali yok; dağıtım öncesi tamamlanmalı |
| R24 P2 | Native sonuç bildirimi/odak, scroll, erişilebilir adlar ve force stop kontrolü | Gerçek NVDA/JAWS, DPI/yüksek karşıtlık/klavye testi gerekir |
| R25 P2 | Embedder metadata eşleşmesi, model/rate/vocoder/archive/schema sınırları, GUI dışı yükleme | V1/no-F0/MRF/RefineGAN/32-48k bütün gerçek yayıncı modelleri sınanmadı |
| R26 P3 | Gerçek sabit hop=160 sözleşmesi, kalıcı/dönen log, sınırlı GUI metni, doküman/metadata güncellemesi | Sürüm 2.0.0; yayın yapılmadı |
| R27 P2 | L2 dışındaki metrikler hesap öncesi reddedilir | İç çarpımlı index harmanlama sunulmaz |
| R28 P1 | Kullanıcı index'i sınırlı Python veri parser'ıyla okunur; native read_index/deserialize kullanılmaz | Yalnız desteklenen little-endian x64 FlatL2/IVFFlatL2 veri düzenleri kabul edilir |

## İkinci incelemede bulunan ek sorunlar

- Resume'da CPU/CUDA/HIP/XPU veya GPU sayı/index değişimi RNG'yi sessizce
  kaybettirebiliyordu. Layout job/checkpoint'e kaydedilir ve uyumsuz devam reddedilir.
- İki controller aynı session cancel/heartbeat marker'ını değiştirebiliyordu.
  Parent controller guard ve worker guard ayrı kilitlerdir; marker dosyaları
  kilit alındıktan sonra hazırlanır.
- Native kesintide yarım checkpoint parçaları birikebiliyordu. Yalnız owned
  checkpoint adları temizlenir; başka kullanıcı dosyası silinmez.
- Küçük bir PTH içindeki dev config büyük ağ allocation'ı tetikleyebiliyordu.
  Config/key/shape/meta parametre sayısı/RAM ve ZIP central-directory bütçesi
  gerçek generator veya torch.load öncesinde denetlenir.
- Yayıncı RMVPE'nin FP16'ya çevrilmiş kullanılmayan BN sayaçları +Inf taşır.
  Yalnız tam pinned SHA-256 eşleşen modelde scalar positive Inf
  num_batches_tracked istisnası tanınır. Öğrenilen ağırlık/running statistic,
  NaN, yanlış şekil ve farklı dosya için istisna yoktur.
- FP16 pretrained dosya boyutu gerçek FP32 model+Adam checkpoint boyutunu
  temsil etmiyordu. Gerçek 1,295,040,257 byte checkpoint ölçümüyle disk
  rezervi iki nesil+export için yükseltildi.
- GUI açılırken separator_backend üzerinden motor DLL'leri yükleniyordu.
  Import ertelendi; yeni ayrı süreç testi GUI modüllerinin torch/audio motoru
  import etmeden açılabildiğini doğruluyor.
- HuBERT valid CNN framing kısa kayıtta 20 ms tail kaybı ve no-F0 parçalarında
  zaman çizelgesi sapması üretiyordu. Gereken gerçek tail bağlamı/segment frame
  sınırları düzeltildi; CPU ve CUDA'da iki gerçek RVC modelinin 4 saniyelik
  girdiden tam 160.000 frame/40 kHz çıktı ürettiği doğrulandı.
- VR ayrıştırmada istft uzunluğu verilmediği için 4 saniyelik kayıt yaklaşık
  5,44 ms kısalıyordu. Yalnız owned girişe 100 ms gerçek yansımalı tail bağlamı
  eklenir; çıktı özgün sürenin hedef örnek sayısına kesilir. Eksik çıktı sıfırla
  doldurulmaz. CPU/CUDA DeEcho çıktıları artık tam 4 saniyedir.
- audio-separator/pydub writer, 24/32-bit başlığa rağmen bütün model çıktısını
  önce int16'ya düşürüyordu. Native FLAC writer PCM_24 kullanır; 16-bit altında
  kalan ayrıntı regresyonla korunur. Silence dosyası atlanmaz; hata yutulmaz;
  VR'nin ham spektrumundaki NaN/Inf kütüphanenin sıfıra çevirmesinden önce reddedilir.
- Windowed stderr log stream'i aynı dosyanın rollover hatasına tekrar log
  yazıp RecursionError üretebiliyordu. Per-process/owned worker logları,
  reentry guard ve güvenli handler ile düzeltildi; fallback bu logları da okur.
- Native ses progress/cancel callback'i hata verdiğinde worker açık kalabiliyordu.
  Callback/request I/O hatasında bounded cleanup yapılır. Unicode stdout için
  child ortamı UTF-8'dır; Japonca/emoji içeren gerçek giriş yolu test edildi.
- Bütünlük cache'inin varsayılan tam save API'si stale kayıt geri yazabiliyordu.
  Snapshot değişiklikleri merge edilir; aynı kayıt çakışırsa önceki dosya korunur.
- Windows venv python.exe ayrı bir gerçek Python worker başlatabilir. Popen
  PID'sini worker PID'si saymak yanlıştı; Job Object'e geç bağlanan launcher
  çocuğunu da kaçırabilirdi. Windows süreçleri CREATE_SUSPENDED ile başlatılır,
  Job Object'e atanır ve belgelenmiş Thread32/OpenThread/ResumeThread API'siyle
  devam ettirilir. Gerçek worker ve descendant handle'larının force stop sonrası
  sinyal verdiği temiz CPU venv regresyonuyla doğrulandı.

## Testler ve kanıtlar

Başlangıçta 110 test vardı. Son koşuda **224 testin tamamı**, hem mevcut
PyTorch 2.11.0+cu128 geliştirme ortamında hem ayrı hash-locked PyTorch
2.11.0+cpu ortamında geçti. Test koşucusu süreleri sırasıyla 19,282 ve 19,729
saniye; import ve dış süreç zamanı ayrıca vardır. Kaynak compile kontrolünde
91 Python dosyası geçti. `REGRESSION_FINAL_CHECK.json` sonucu kaydeder.

İkinci incelemede yeniden üretilen ek kod hataları da giderildi. Bu koşularda
yeni başarısız regresyon kalmadı. Fiziksel/model/kalite doğrulaması bekleyen
kapsamlar yukarıdaki tabloda durur; bunlar kapatılmış hata gibi sayılmadı.

- `TRAINING_FIXED_REAL_CHECK.json`: RTX 5060 Ti, gerçek FP32 RVC V2/40k,
  sentetik iki 6 saniyelik kayıt; step6 stop→step12 resume, 354 vektör,
  dört sonlu cover. Yaklaşık 10,164 MiB sampled GPU peak ve 3,679 MiB worker RSS;
  evrensel minimum veya kalite puanı değildir.
- `TRAINING_FIXED_CUDA_CHECKPOINT_EXACT.json`: küçük fiziksel CUDA ağlarıyla
  kesintisiz referans/checkpoint resume ağırlık, scheduler ve bütün RNG durumları
  bit düzeyinde eşleşti; gerçek GAN determinismi iddiası değildir.
- `INFERENCE_RMVPE_REAL_CHECK.json`: 8 saniyede CPU F0 önceki sonuçla aynı;
  45 saniyede CPU/CUDA voiced-frame uyuşmazlığı yok. Örtüşmenin bağlam/hız
  bedeli raporda ölçülür; seslerin tümünde eşit F0 veya algısal kalite iddiası yok.
- `NATIVE_AUDIO_REAL_CHECK.json`: gerçek ayrı worker, hazır iki separator ve
  korunan iki RVC modelini sentetik sesle deneme; aynı worker ve helper cache,
  decoded sonluluk, 24-bit FLAC ve tam hedef süre kontrolü. Aynı güncel senaryo
  NVIDIA CUDA'da `NATIVE_AUDIO_CUDA_0_REAL_CHECK.json` içinde de geçti.
- `YAYIN_DUZELTME_KAYNAK_NATIVE_KANITLARI.json`: temiz CPU hash-locked venv'de
  kaynak Python üzerinden gizli native wx kontrolleri, CPU backward, gerçek
  ORT MatMul, Unicode FFmpeg roundtrip ve ayrı ses/eğitim worker probe'ları geçti.
- `MANAGED_MODELS_REVERIFY.json`: beş mevcut paket offline tam kontrolü geçti;
  ağırlık byte içerikleri aynı, yalnız derived bütünlük kayıtları yenilendi.
- Gerçek owned-process ölüm/hang/force stop, child tree cleanup, Unicode input,
  eski çıktı korunması, stale JSON çatışması, yanlış model/index/ZIP ve RAM
  header senaryoları otomatik regresyonlarda bulunur.

Kaynak geliştirmesinde yeniden üretilen hatalar düzeltilip regresyonla korunur.
Fiziksel AMD/Intel GPU, bütün model varyantları, kör dinleme ve erişilebilirlik
kontrolleri tamamlanmadan geniş donanım/kalite iddiası yayınlanmamalıdır.
