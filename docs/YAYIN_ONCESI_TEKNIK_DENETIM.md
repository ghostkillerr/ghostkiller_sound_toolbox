# Yayın öncesi teknik denetim

> Bu belge düzeltme öncesindeki tarihsel incelemedir. Güncel kod, testler ve
> kalan doğrulamalar [düzeltmeler ve ikinci analiz](YAYIN_DUZELTMELERI_VE_IKINCI_ANALIZ.md)
> belgesindedir. Kullanıcı EXE üretimini durdurmuştur; çalışma kaynak geliştirmesine devam eder.

Tarih: 13 Ekim 2026. İncelenen kapsam: mevcut, commit edilmemiş değişiklikler
dahil kaynak ağacı, yerel bağımlılıklar, eğitim ve çıkarım motorları,
donanım seçimi, model yönetimi, güncelleme, PyInstaller ve Inno Setup.

**Karar: mevcut kaynakları tüm Intel/AMD/NVIDIA GPU'larda çalışan genel bir
Windows sürümü olarak yayınlamak için henüz yeterli kanıt ve altyapı yok.**
CPU ve NVIDIA CUDA yolları uygulanmış; Intel XPU yolu yok. AMD ROCm yolu ayrı
bir çalışma ortamı gerektiriyor ve Windows eğitimi sürüm ayırmadan engelleniyor.
Bu, uygulamanın AMD/Intel işlemcilerde CPU üzerinden çalışamayacağı anlamına
gelmez. İşlemci markası ile GPU hızlandırması ayrı destek başlıklarıdır.

Bu belge hata düzeltmesi değildir. Ürün kodu, kişisel kayıtlar ve korunmuş
RVC ağırlıkları değiştirilmedi. Testler sentetik ve geçici dosyalar kullanır.
Bir inceleme bütün hataların bulunmuş olduğunu garanti etmez; aşağıda
yeniden üretilen sorunlar, kaynakta görülen sorunlar ve henüz ölçülmemiş riskler
ayrı belirtilmiştir.

## 1. Kanıt ve test kapsamı

- `python -m unittest discover -s test -v`: **110 test başarılı**. Test
  koşucusunun bildirdiği süre 5.697 saniye; bağımlılık importları ayrıca zaman
  alır. Bu testler tüm gerçek model/donanım kombinasyonlarını çalıştırmaz.
- `python -m pip check`: bağımlılık metadata çakışması bildirmedi. Bu kontrol,
  aynı Python modülünü iki dağıtımın birlikte sağlamasını tespit etmiyor.
- Windows 11 x64; Python 3.12; PyTorch/torchaudio 2.11.0+cu128;
  torchvision 0.26.0+cu128; wxPython 4.2.5; audio-separator 0.44.2;
  NumPy 2.4.6; FAISS CPU 1.14.3; transformers 5.14.1; PyInstaller 6.21.0.
- Yerel GPU: NVIDIA GeForce RTX 5060 Ti, yaklaşık 16 GB VRAM.
- Yerel işlemci: **AMD Ryzen 5 7500F**. Bu makinedeki native CPU testleri
  fiziksel AMD CPU üzerindedir; Intel CPU için aynı backend'in bulunması
  fiziksel Intel doğrulaması yerine geçmez.
- `onnxruntime=1.29.0` ve `onnxruntime-gpu=1.26.0` birlikte kurulu.
  Gerçekte import edilen modül 1.29.0; sağlayıcılar yalnız
  `AzureExecutionProvider`, `CPUExecutionProvider`. CUDA sağlayıcısı yok.
- Yerel 40 kHz eğitim G/D, ContentVec ve RMVPE hazır. 32/48 kHz eğitim
  ağırlıkları bu ortamda yok; denetimde indirilmedi.
- Gerçek CUDA testi: iki adet altı saniyelik sentetik kayıt, 40 kHz,
  FP32, batch 1, iki CPU thread, iki epoch. Altıncı adımda durdurma,
  checkpoint'ten devam, toplam **12 adım**, **354 vektörlü index** ve iki
  adayın index kapalı/açık **dört gerçek cover dönüşümü** tamamlandı.
  Son mel L1 0.8096, yalnız bu sentetik deneyin ölçümüdür; kalite puanı değildir.
- Bu CUDA çalışmasında olay örneklerindeki tepe GPU tahsisi yaklaşık
  **10,167 MiB / 9.93 GiB**, en yüksek örneklenen worker RAM'i yaklaşık
  **2.55 GiB**. Bu sayılar evrensel minimum gereksinim veya kararlı benchmark
  değildir; veri, profil, sürüm, batch ve arka plan yüküne göre değişir.
- `test/audit_release_checks.py` yalnız geçici dosyalarla mevcut davranışı
  yeniden üretmek için eklendi. Donanım markası taklit edilen kontroller,
  fiziksel AMD/Intel GPU testi yerine geçmez.
- Yeniden üretmeler: SystemExit(1) sonrası **"Seçilen 0 işlem başarıyla
  tamamlandı"**; stale registry yazısında ikinci model kaybı; worker hatasının
  boş string olması; validator'dan geçen **step=0**; NaN/yanlış şekilli
  separator tensorlerinin prefix kontrolünden geçmesi; RMVPE tek forward
  penceresinin **32,000** çerçeve olması. Gerçek trainer kontrol akışı küçük
  ikame ağlar ve sanal saatle çağrıldığında checkpoint'ler yalnız **0 ve 610
  saniyede** alındı; 300 saniyelik kayıt atlandı. Bu zaman fiziksel eğitim
  benchmark'ı değildir. Ayrıntılı çıktı `YAYIN_DENETIMI_HATA_KANITLARI.json`.
- Yerel olarak hazır iki ayrıştırma modeli gerçek, dört saniyelik sentetik
  stereo girdide **AMD CPU ve NVIDIA CUDA üzerinde geçti**. BS-RoFormer
  inference CPU 52.156 s / CUDA 16.656 s; DeEcho-DeReverb CPU 9.093 s /
  CUDA 1.343 s. GPU peak allocation sırasıyla 1,239 ve 1,328 MiB.
  Bu sırayla alınmış tek ölçümler kernel/import/cache ısınmasını içerir;
  eşit koşullu veya uzun şarkı benchmark'ı değildir. FLAC çıktılar
  sonlu/dolu olarak doğrulandı. Diğer üç ayrıştırma modeli bu ortamda eksik;
  indirilmedi. `YAYIN_DENETIMI_AYRISTIRMA_KANITLARI.json` ayrıntıları tutar.
- Yeni paketli EXE, temiz Windows makinesi, AMD GPU, Intel GPU, gerçek
  NVDA/JAWS ve uzun gerçek şarkılar bu denetimde uçtan uca doğrulanmadı.

## 2. Donanım desteğinin gerçek durumu

| Hedef | Kodun bugünkü durumu | Yayın iddiası / gereken çalışma |
| --- | --- | --- |
| Intel x64 işlemci | PyTorch CPU yolu; marka bazlı engel yok | Paketli CPU testi, minimum komut seti/Windows/RAM sınırı belirlenmeli |
| AMD x64 işlemci | Ryzen 5 7500F'de gerçek BS-RoFormer ve DeEcho CPU dönüşümü başarılı | Diğer CPU sınıfları, beş modelin tamamı ve temiz kullanıcı ortamı ayrıca doğrulanmalı |
| NVIDIA GPU | CUDA algılama ve açık cihaz aktarımı var; RTX 5060 Ti'de gerçek eğitim/cover geçti | Kart mimarisi, sürücü ve paketlenen CUDA sürümü için destek matrisi gerekli |
| AMD Radeon / Ryzen GPU | HIP, CUDA API'si üzerinden algılanabilir; CUDA paketi AMD runtime sağlamaz | Ayrı, sabitlenmiş native Windows ROCm paketi ve model bazlı gerçek testler gerekli |
| Intel Arc / uygun Core Ultra GPU | Algılama `torch.cuda` ile sınırlı; `Config('xpu:0')` reddediliyor | XPU runtime, cihaz soyutlaması ve tüm modellerin gerçek doğrulaması gerekli |
| Eski Intel iGPU / destek matrisinde olmayan AMD GPU | PyTorch GPU yolu garanti değil | CPU yolu desteklenebilir; GPU hızlandırması ayrıca kanıtlanmalı |
| ARM64 Windows / Snapdragon | Installer yalnız x64; ARM64 yerel backend yok | Native ARM64 desteği ilan edilmemeli; x64 emülasyonu ayrı test konusudur |

PyTorch'un resmi Intel belgesi Windows üzerinde XPU ile eğitim ve çıkarımı
destekliyor; Arc A/B ve belirli Core Ultra ailesini listeliyor. Bu, bizim
RVC/RMVPE/RoFormer zincirimizin otomatik olarak XPU uyumlu olduğunu kanıtlamaz.
[Resmi PyTorch Intel GPU belgesi](https://github.com/pytorch/pytorch/blob/main/docs/source/notes/get_start_xpu.md).

**AMD belgelerindeki sürüm değişimi önemli:** projenin kullandığı 7.2 dönemindeki
Windows eğitim yasağı bütün gelecek sürümlerin özelliği gibi ele alınmamalı.
Eski Radeon/Ryzen belgesi, 7.13'ten itibaren birleşik belgelere yönlendiriyor.
Güncel resmi portal ROCm 10.1.0 ve Windows için PyTorch 2.14.0 listeliyor.
Bu veriden tüm Radeon kartlarında bütün eğitim iş yüklerinin doğrulandığı
sonucu çıkarılamaz. GPU/işletim sistemi/sürücü/runtime kombinasyonu seçilerek
güncel matris ve gerçek GAN backward testi kontrol edilmelidir.
[Eski Windows matrisi](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html),
[güncel ROCm sürüm notları](https://rocm.docs.amd.com/en/latest/about/release-notes.html),
[güncel uyumluluk matrisi](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html).

NVIDIA için yalnız marka adı yeterli değil: kullanılan PyTorch wheel'inin
derlendiği mimariler, CUDA/cuDNN ve Windows sürücüsü birlikte önemlidir.
Sürücü minimumu CUDA sürümüne ve uyumluluk moduna bağlıdır; uygulama tanı
raporunda bu bilgileri ve gerçek kernel hatasını göstermelidir.
[NVIDIA CUDA 12.8 sürüm/uyumluluk bilgisi](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html).

## 3. Öncelikli bulgular

Öncelik: **P1** yayından önce ele alınması gereken ciddi hata/destek açığı;
**P2** kullanıcı deneyimi, performans veya güvenilirlik sorunu;
**P3** düşük etkili API/dokümantasyon eksikliği.
Kanıt: **yeniden üretildi**, **kaynakta kesin**, **doğrulama açığı**.

### R01 — P1: Tek CUDA paketi çok markalı GPU hedefini karşılamıyor

Konum: `hardware.py:110`, `rvc/configs/config.py:11`,
`separator_backend.py:27`, `.spec`.
Algılama CUDA/HIP ile sınırlı; XPU ve DirectML reddediliyor. PyInstaller
`collect_all('torch')` ile o ortamda kurulu olan runtime'ı topluyor; farklı
üreticinin runtime'ına otomatik dönüşmüyor. Intel GPU desteğinin eksikliği
kaynakta kesin, XPU reddi küçük kontrolle yeniden üretilebilir.
Çözüm: desteklenen backend'leri açıkça temsil eden cihaz katmanı, backend'e
göre ayrılmış native worker/runtime paketleri ve CPU seçeneği. CUDA, HIP ve
XPU wheel'lerini aynı Python kurulumuna üst üste kurmak uygun mimari değildir.

### R02 — P1: Windows HIP eğitim engeli runtime sürümünü ayırmıyor

Konum: `hardware.py:59`, `training/service.py:20`, `training/worker.py:45`.
`os.name == 'nt'` ve `torch.version.hip` dolu olduğunda her sürüm engelleniyor.
Kullanıcıya bütün native Windows ROCm eğitimlerinin resmi olarak desteklenmediği
söyleniyor. Kuralın dayandığı belge eski; güncel portal daha yeni paketler
listeliyor. Kaynakta kesin destek/politika sorunu.
Çözüm: güvenlik ön kontrolünü kaldırıp körlemesine eğitim açmak yerine,
sabitlenmiş ve doğrulanmış backend/sürüm/kart tablosu kullanmak; doğrulanmamış
kombinasyonlara uygulamanın doğrulama sınırını açıklamak.

### R03 — P1: Ayrıştırma motorunun `SystemExit` hatası başarı mesajına dönüşebilir

Konum: `ui_separator.py:395`, `ui_separator.py:450`.
Kurulu audio-separator 0.44.2 içindeki
`separator/architectures/mdxc_separator.py:116`, model yükleme `RuntimeError`
sonrasında `sys.exit(1)` çağırıyor. Bu, model uyumsuzluğu veya OOM yolunda
olabilir. İki uygulama katmanı yalnız `Exception` yakalıyor; `SystemExit`
bunun alt sınıfı değil. `ProcessChain` final bloğunda `failed=False`
kalabildiği için sıfır adımlı başarı mesajı hazırlanıyor ve thread ölüyor.
SystemExit üreten motor ikamesiyle yanlış başarı sonucu yeniden üretildi;
fiziksel OOM veya bozuk kullanıcı modelini zorlayarak çökertme yapılmadı.
Çözüm: üçüncü taraf motor sınırında `SystemExit`'i işlem hatasına çevirmek;
ayrıştırmayı native subprocess içinde izlemek; hata sonucu ve thread bitişini
ayrıca test etmek. `KeyboardInterrupt` dahil bütün `BaseException` türlerini
gelişigüzel başarıya çeviren genel bir catch eklenmemeli.

### R04 — P1: Güncelleyici normal kullanıcıdan yönetici kurulumu başlatamıyor

Konum: `updater.py:261`, `Ghostkiller_Kurulum.iss`.
Inno Setup `PrivilegesRequired` belirtilmezse varsayılan `admin` kullanır.
Uygulama kurulumu `subprocess.Popen(..., shell=False)` ile başlatıyor.
Normal, yükseltilmemiş Windows sürecinden yönetici manifestli EXE için
CreateProcess `ERROR_ELEVATION_REQUIRED` döndürür; UAC başlatılmaz.
Kaynak ve resmi platform sözleşmesiyle doğrulandı; kurulum bu denetimde
çalıştırılmadı. Çözüm: ShellExecuteEx / `runas`, iptal ve başarı sonucunu
izleme; uygulamayı her zaman yönetici çalıştırmayı çözüm olarak sunmama.
[Microsoft UAC belgesi](https://learn.microsoft.com/en-us/windows/win32/dxtecharts/user-account-control-for-game-developers),
[Inno Setup varsayılanı](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm).

### R05 — P1: Güncelleme kurulumunun güvenilirliği yalnız iki baytla kontrol ediliyor

Konum: `updater.py:141`, `updater.py:242`, `version.json`.
HTTPS ve boyut kontrolü var; ancak istenen herhangi bir HTTPS hostu kabul
ediliyor ve yalnız `MZ` başlığı denetleniyor. Yayınla eşleşen SHA-256,
beklenen yayıncı Authenticode imzası veya imzalı manifest yok. Kaynakta kesin
dağıtım güvenilirliği açığı; bir saldırı yaşandığına dair bulgu değil.
Çözüm: sürüme sabitlenmiş URL, güvenilen yayın kaynağı, hash ve mümkünse
beklenen yayıncı imzası; kontrol geçmeden kurulum başlatmama. Değişken
`releases/latest` adresi manifest sürümüyle farklı dosya indirebilir.

### R06 — P1: Tekrarlanabilir yayın ortamı yok; ORT çakışması şimdiden görünür

Konum: proje kökü ve `.spec`.
Sabitlenmiş bağımlılık manifestosu / lock dosyası / temiz build CI yok.
Yerel ORT CPU ve GPU paketleri aynı `onnxruntime` modülünü sağlıyor; import
edilen kopyada CUDA sağlayıcısı yok. `pip check` bunu yakalamadı.
Beş mevcut ayrıştırma modeli PyTorch VR/RoFormer yollarıdır; bu bulgu onların
tamamının CPU'ya düşmesi anlamına gelmez. ONNX yolu kullanıldığında GPU
tercihine rağmen CPU sağlayıcısı seçilecektir.
Çözüm: her backend için temiz ve sabitlenmiş ortam; tek ORT dağıtımı;
CUDA/cuDNN sürüm eşleşmesi ve gerçek `InferenceSession` testi.
[ORT kurulum](https://onnxruntime.ai/docs/install/),
[CUDA sağlayıcısı](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).

### R07 — P1: Uzun cover kayıtlarında F0 hesabı bellek açısından yeterince sınırlı değil

Konum: `rvc/infer/pipeline.py:510`, `rvc/lib/predictors/RMVPE.py:445`.
Ses tümüyle okunuyor; F0 tüm padded kayıt için sentez parçalarından önce
çıkarılıyor. RMVPE chunk var, fakat varsayılan 32,000 çerçeve yaklaşık
**320 saniyeyi tek U-Net forward** içinde işliyor. Bütün mel ve çıktı chunk'ları
da bellekte tutuluyor. Bu, kısa sentetik eğitim parçasının bellek ihtiyacından
çok farklı; düşük VRAM kartında hata veya ağır paging riski var. Chunk boyutu
kaynakta kesin; düşük VRAM üzerinde OOM bu denetimde zorlanmadı.
Çözüm: örneklenen serbest RAM/VRAM'e göre küçük, örtüşmeli F0 pencereleri,
CPU'ya kontrollü çıkış biriktirme ve sınırda F0 sürekliliği testi. Kalite
ayarlarını gizlice azaltmak veya sessiz CPU geçişi yapmak uygun değil.

### R08 — P1: Beş dakikalık checkpoint timer'ı tek batch'li epoch'larda atlanıyor

Konum: `training/engine.py:281`.
Periyodik kayıt için `next_batch < len(chunks)` şartı var. Epoch tek batch'e
sığıyorsa bu hiçbir zaman doğru olmaz; kayıt yalnız `save_every` epoch'ta
veya bitişte yapılır. `save_every` 1000'e kadar seçilebildiğinden uzun süre
checkpoint alınmayabilir. Sorun yalnız uzun bir optimizasyon adımının
beklenmesi değildir. Çözüm: tamamlanan G+D adımı sonrasında epoch sınırında da
timer'ı uygulamak; scheduler/epoch/cursor/RNG tutarlılığını korumak.

### R09 — P1: Temiz makine ve paketli EXE yayın doğrulaması yapılmamış

Konum: `.spec`, `.iss`, `main.py:195`.
110 test kaynak ortamında geçiyor; temiz Windows'ta DLL yükleme, ffmpeg,
eğitim worker dispatch'i, Program Files izinleri ve güncelleyici doğrulanmadı.
Model GPU forward testi tam GAN backward veya uzun RoFormer testi değil.
Erken import hataları global handler kurulmadan oluşuyor. Doğrulama açığı.
Çözüm: yayın paketini normal kullanıcı, Python/FFmpeg kurulu olmayan temiz
VM ve fiziksel donanım üzerinde çalıştırmak; başlangıç hata günlüğünü ağır
importlardan önce hazırlamak. VC runtime ve eksik DLL tanısı test edilmeli.

### R10 — P2: İki uygulama örneği model kayıtlarını kaybedebilir

Konum: `app_runtime.py:10`, `ui_cover.py:73`, `training/service.py:138`.
`JOB_LOCK` yalnız aynı süreçte çalışır. İki uygulama örneği aynı `models.json`
ve `.integrity.json` üzerinde eski kopyalarını atomik olarak yazabilir;
atomik replace kayıp güncellemeyi önlemez. İkinci eklenen model kaydı sonraki
eski yazıyla silinebilir. Çözüm: single-instance mutex veya süreçler arası
kilit, kilit altında yeniden oku/değiştir/yaz. Fiziksel ağırlık silinmese bile
kullanıcının liste kaydı kaybolur.

### R11 — P2: Bozuk worker çıkışında kullanıcıya boş hata mesajı gösterilebilir

Konum: `training/service.py:133`, `training/worker.py:25`.
Worker çalışma sırasında manifest'e `error=''` yazar. Native çökme veya
try bloğundan önceki import hatası bunu değiştiremez. Parent
`manifest.get('error', fallback)` kullandığı için boş string fallback'i
engeller; `RuntimeError('')` oluşur. Çözüm: `error or fallback`, exit code,
worker.log sonu ve çöken aşama bilgisi; önceki checkpoint korunmalı.

### R12 — P2: Native hesaplama kilitlenirse güvenli süre/çıkış denetimi yok

Konum: `training/service.py:118`, `ui_separator.py:312`, `ui_cover.py:649`.
İptal bayrakla; cover ve ayrıştırma mevcut motor dönüşünü bekliyor. Eğitim
IPC exception yolunda `process.wait()` sınırsız. GPU driver/native katman
kilitlenirse pencere kapanması da JOB_LOCK yüzünden engellenebilir.
İptal sonrası checkpoint beklemek doğru; fakat yanıt vermeyen worker için
ayrı durumu ve kullanıcı kontrollü kurtarma akışı yok. Doğrulama açığı.
Çözüm: subprocess heartbeat, yanıt vermeme tanısı ve son sağlam checkpoint'i
koruyan açık zorla-sonlandırma seçeneği; normal iptalde yarım optimizer
adımını checkpoint olarak kaydetmeme.

### R13 — P2: Index dönüşümde ikinci kez RAM'e kopyalanıyor

Konum: `training/index.py:29`, `rvc/infer/pipeline.py:463`.
Flat index tüm vektörleri RAM'de tutuyor; `reconstruct_n(0, ntotal)` ayrıca
aynı vektörlerin NumPy kopyasını oluşturuyor. D=768 FP32 için her kopya
vektör başına 3072 bayt. 50 feature/s varsayımıyla bir saatlik özellik,
örtüşme/holdout hariç, yaklaşık 553 MB index + 553 MB kopya gerektirir.
Her query'nin 8 komşusu ayrıca büyük geçici matris oluşturur.
Çözüm: komşuları sınırlı query bloklarıyla reconstruct etmek veya desteklenen
Flat buffer görünümü; boş RAM ve index boyutu ön kontrolü. Kullanıcının
kalite öncelikli Flat tercihinin kendisi hata değildir; IVF/KMeans'e sessiz
geçiş önermiyoruz. [FAISS bellek tablosu](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).

### R14 — P2: Yardımcı ağlar model kuyruğunda tekrar tekrar yükleniyor

Konum: `ui_cover.py:780`, `rvc/infer/pipeline.py:251`,
`rvc/infer/infer.py:387`.
Her ses modelinde yeni converter ve ContentVec/RMVPE oluşuyor; cleanup
hepsini kaldırıyor. Disk okuma ve model hazırlama çoklu model kuyruğunun
her öğesinde tekrarlanıyor. Çözüm: tek iş boyunca cihaz+embedder+model
kimliğine bağlı sınırlı cache; bellek baskısında bırakma. Eski ağın yeni
checkpoint ile karışmasını engelleyen anahtar ve yaşam döngüsü gerekir.

### R15 — P2: `empty_cache()` her parçada çağrılıyor

Konum: `rvc/infer/pipeline.py:391`, `rvc/lib/predictors/RMVPE.py:509`.
Canlı tensorleri bırakmaz; sonraki segmentin allocator bloklarını tekrar
istemesine yol açabilir. Üstelik bazı çağrılar seçilen CPU işinde bile global
CUDA kullanılabilirliğine bakıyor. Bu bir kesin hız kazanımı iddiası değil;
karşılaştırmalı profil gerektiren performans sorunu.
Çözüm: iş sonu veya ölçülen bellek baskısında, seçilen cihazla sınırlı temizlik.

### R16 — P2: Resume yüklemesi geçici GPU bellek tepesini büyütebilir

Konum: `training/engine.py:169`, `training/engine.py:182`.
G/D zaten GPU'da oluşturulduktan sonra bütün resume state'i
`torch.load(..., map_location=device)` ile tekrar GPU'ya alınır. Ağ, optimizer
ve RNG tensorleri bir arada yüklenir. Normal adımın sığdığı kartta yükleme
aşaması sığmayabilir; düşük VRAM'de ayrıca ölçülmedi.
Çözüm: CPU/mmap yükleme, gerekli state'lerin sıralı taşınması ve resume
öncesi tepe bellek kontrolü. Batch'i gizlice değiştirmek devam matematiğini
değiştirir; ayrı ve açık karar gerektirir.

### R17 — P2: Hazırlama disk tahmini yüksek örtüşmeyi hesaba katmıyor

Konum: `training/dataset.py:106`, `training/config.py:49`.
Tahmin kayıt süresine dayanır, `segment/(segment-overlap)` çarpanını kullanmaz.
GUI'de 1.0 saniye segment / 0.9 saniye overlap geçerli: yaklaşık 10 kat
parça/feature üretilebilir. Daha uç API değeri örnek yuvarlamasıyla step=0
olabilir; validator bunu kabul eder. Çözüm: pozitif örnek step'i doğrulama,
parça sayısını gerçek sınırlar ve minimum parça uzunluğuyla hesaplama;
checkpoint'in geçici ikinci kopyasını da disk ihtiyacına ekleme.

### R18 — P2: Ayrıştırma uzun dosya adları için çıktı sınırını korumuyor

Konum: `ui_separator.py:417`, `ui_separator.py:439`.
Özgün base_name'a uzun suffix ekleniyor. 240 karakterlik geçerli basename
34 karakter suffix ile 274 karakterlik component üretir; Windows'un 255
component sınırını aşar. Cover iki adı ayrı kısaltıyor, ayrıştırma yapmıyor.
Çözüm: suffix için yer ayıran ortak ad üretimi; toplam yol kontrolü ve
kısaltmada çakışma koruması. LongPathsEnabled component sınırını kaldırmaz.

### R19 — P2: CPU thread sınırı bütün yerel kütüphaneleri kapsamıyor

Konum: `hardware.py:142`, `rvc/infer/pipeline.py:9`, `training/service.py:85`.
GUI ses işlerinde yalnız PyTorch thread sayısı sınırlı. FAISS OpenMP,
NumPy/BLAS, ORT ve FFmpeg kendi thread havuzlarını kullanabilir. Eğitim
worker'ı OMP/MKL/OpenBLAS ortamını sınırlıyor; aynı kontrol ses işinde yok.
Çözüm: native worker başlamadan ortam sınırları ve model bazlı profil;
hibrit Intel CPU / düşük güç laptop üzerinde gerçek ölçüm. Her makineye
tek sabit sayı performans optimumu değildir.

### R20 — P2: Model kaynağı kimliği bazı yardımcı modellerde sabitlenmemiş

Konum: `model_manager.py:13`, `rvc/lib/utils.py:81`.
Eğitim G/D kaynakları commit ve hash ile sabit; ContentVec/RMVPE URL'leri
`resolve/main`. İlk indirme hash'i güven temeli oluyor; upstream değişirse
iki temiz kullanıcı farklı yardımcı model alabilir. Eski hash ile onarım
güncel upstream dosyayı reddedebilir. Çözüm: model sürümlü, yayıncı hash'li
asset manifestosu ve açık model güncelleme/göç akışı. Tam kontrolü her ses
işinde tekrar yapmak gereksiz disk maliyetidir; mevcut hızlı kontrol korunabilir.

### R21 — P2: Separator şema kontrolü ağırlıkların tamlığını/sonluluğunu kanıtlamıyor

Konum: `model_manager.py:123`.
Üç RoFormer prefix'inde birer key/tensor bulunması yeterli; yanlış şekil
ve NaN tensor bu bölümden geçebilir. HuBERT/RMVPE kontrolleri daha ayrıntılı.
Rehber bu sınırı dürüstçe belirtiyor; fakat kullanıcıdaki "Hazır" etiketi
yüklenebilir/sağlıklı tüm parametre garantisi sayılmamalı.
Çözüm: sabit config ile meta ağ key/shape kontrolü, bloklarla finiteness
kontrolü ve yayımlanmış hash; ilk kurulumda kısa gerçek model testi. Bütün
kontroller birlikte bile ses kalitesi garantisi oluşturmaz.

### R22 — P2: Varsayılan 80 Hz + 48 Hz filtreler ve F0 smoothing kalite açısından ölçülmemiş

Konum: `rvc/infer/infer.py:259`, `rvc/infer/pipeline.py:476`,
`rvc/infer/pipeline.py:295`.
İki high-pass ve smoothing sabit uygulanıyor; eğitim özellik hazırlığı aynı
filtreleri kullanmıyor. Düşük ses temel frekansı ve hızlı vibrato etkisi için
kontrollü A/B yok. "SOTA", "vibratoyu bozmaz", "boğuklaşmayı önler" kaynak
yorumları test kanıtı değil. Çözüm: düşük/orta/yüksek perde, nefes/ünsüz ve
vibrato örneklerinde kör dinleme + F0 karşılaştırması; gerekli olduğunda
açık seçenek ve tutarlı hazırlama politikası. Varsayılanları körlemesine
kaldırmak da kaliteyi doğrulamaz.

### R23 — P2: Kurulum boyutu ve lisans belgeleri yayın için eksik

Konum: `.spec`, `.iss`, `tools/ffmpeg/`, `lisans.txt`.
Yerel FFmpeg + FFprobe toplam yaklaşık **433.5 MiB**; birçok kullanılmayan
video/AI kitaplığı içeren full build. `--enable-gpl --enable-version3`
ile derlenmiş. Installer yalnız iki EXE'yi alıyor; eşleşen lisans/kaynak
dağıtım bilgisi açıkça paketlenmiyor. Geniş `collect_all` runtime'ı da
büyütüyor; nihai installer boyutu ölçülmedi.
Çözüm: kullanılan ses codec'leri + soxr ihtiyacını karşılayan lisansı
belirlenmiş build, tüm üçüncü taraf notices/lisansları ve kaynak erişim
bilgisi; temiz build'de boyut ölçümü. Ayrı FFmpeg EXE çağırmak tek başına
uygulamanın bütün kaynaklarının GPL olması sonucunu doğurmaz.
[FFmpeg lisans bilgisi](https://ffmpeg.org/doxygen/trunk/md_LICENSE.html),
[FFmpeg dağıtım rehberi](https://www.ffmpeg.org/legal.html).

### R24 — P2: Erişilebilirlik iddiası yayın kanıtının önünde

Konum: `ui_training.py:444`, ana pencere, `version.json`.
Standart native wx kontrolleri ve erişilebilir adlar iyi temel; ancak test
control adı düzeyinde. Eğitim/analiz/kayıt bitişinde yalnız text güncellenen
akışlar var; odak değişmeden NVDA'nın sonucu anons ettiği ölçülmedi.
150/200% DPI, küçük ekran, yüksek karşıtlık ve uzun çeviri/dosya adı
senaryoları yok. Mevcut wx.Panel Ayarlar düzeninde dikey scroll yok.
Çözüm: NVDA/JAWS ile klavye, sonuç bildirimi ve odak dönüşü; gerçek DPI/
ekran testleri. "Tam NVDA/JAWS" yayın metni doğrulama olmadan kullanılmamalı.

### R25 — P2: Geniş model uyumluluk iddiasının test matrisi eksik

Konum: `rvc/infer/infer.py:414`, `training/worker.py:102`.
Motor v1/v2, F0/no-F0 ve üç vocoder kabul ediyor; GUI her modeli ContentVec
ile çağırıyor. Checkpoint `embedder_model` bilgisi seçimde kullanılmıyor.
Başka embedder ile eğitilmiş, boyutça uyumlu model yanlış feature alabilir.
32/48 kHz, v1, no-F0, RefineGAN/MRF, dış index türleri ve farklı yayıncı
checkpoint'ler için gerçek matris yok. Sentetik kendi export'u yalnız
V2/40k/F0/HiFi-GAN uyumluluğunu kanıtladı.
Çözüm: model metadata uyumluluk kontrolü; desteklenmeyen kombinasyonu
başlamadan açıklama veya doğru embedder'i hazırlama. Güvenilmeyen büyük
PTH/index kaynaklarını ana GUI sürecinde sınırsız yüklememe.

### R26 — P3: API parametresi etkisiz, loglar ve ürün metinleri tutarsız

Konum: `rvc/infer/infer.py:185`, `rvc/lib/utils.py:12`, README,
`version.json`, `.iss`, `lisans.txt`.
`hop_length` doğrulanıyor fakat Pipeline'a aktarılmıyor; pencere 160 sabit.
GUI bu parametreyi sunmuyor, mevcut GUI işinin sonucu etkilenmiyor.
Global `warnings.filterwarnings('ignore')` tüm warning'leri bastırıyor;
console=False EXE'de print tabanlı motor tanıları kullanıcıya görünmeyebilir.
README eğitim olmadığını söylüyor; yayın metni eski, ürün adı/V2/lisans
sürümü tutarsız. Çözüm: API sözleşmesini düzeltme/kaldırma; hedefli warning
filtreleri, kalıcı loglar ve gerçek yayın hazır olduğunda tutarlı metadata.

### R27 — P2: Dış FAISS index'in uzaklık metriği denetlenmiyor

Konum: `rvc/infer/pipeline.py:402`, `rvc/infer/pipeline.py:462`.
Boyut/vektör sayısı kontrol ediliyor; `metric_type` edilmiyor. Harmanlama
`1 / score²` ile küçük skora büyük ağırlık verir; bu L2 içindir. İç çarpım
index'inde büyük skor daha benzer vektördür. Geçerli `IndexFlatIP` dosyası
kabul edilirse ağırlıklar ters yönde çalışır. Kendi eğitimimizin FlatL2
index'i etkilenmez; dış model/index içe aktarmada sessiz kalite hatasıdır.
Çözüm: desteklenen L2 metriğini açıkça doğrula ve farklı metriği açıklayıcı
hatayla reddet veya ayrı ve doğrulanmış harmanlama uygula.
[FAISS metrik sözleşmesi](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances).

### R28 — P1: Dış index dosyası native FAISS'e güven denetimi olmadan veriliyor

Konum: `ui_cover.py:514`, `rvc/infer/pipeline.py:462`.
Kullanıcı herhangi bir `.index` seçebiliyor. FAISS'in resmi I/O belgesi,
yanlış/zararlı dosyanın OOM ve özenle hazırlanırsa kod çalıştırma
üretebileceğini bildiriyor; `read_index` güven denetimi sağlamıyor. Python
`try/except` native erişim ihlali veya böyle bir dosyayı güvenlik açısından
izole etmez. Bir exploit çalıştırılmadı ve kişisel index'e zarar verilmedi.
Çözüm: güvenilir kaynak/provenance, dosya hash'i, boyut/kaynak sınırları ve
uygun güvenlik sınırında native worker. Aynı kullanıcı yetkileriyle sıradan
subprocess yalnız çökme izolasyonu sağlar; güvenlik sandbox'ı diye sunulmamalı.
[FAISS resmi I/O uyarısı](https://github.com/facebookresearch/faiss/wiki/Index-IO%2C-cloning-and-hyper-parameter-tuning).

## 4. Native Windows için önerilen hedef mimari

Arayüzün wxPython kalması native kontroller, klavye ve ekran okuyucu açısından
uygun. WSL, Docker veya bulut bu hedef için zorunlu tutulmamalı.

Öneri: tek native arayüz/kurulum yöneticisi; CPU, NVIDIA CUDA, AMD HIP ve Intel
XPU için ayrı yerel worker/runtime paketleri. Kullanıcı backend adlarını
öğrenmek zorunda kalmadan desteklenen cihazı seçebilmeli. İndirilen runtime
ve model sürümleri/hash'leri sabitlenmeli; çalışan backend adı, gerçek cihaz
ve başarısızlık nedeni tanı raporuna yazılmalı. Seçilen GPU'nun uygun olmadığı
durumda açık CPU seçeneği olmalı. Farklı donanım için aynı GUI'nin altında
ayrı native süreçler bulunması uygulamayı native olmaktan çıkarmaz.

Inference'i tek üreticiden bağımsız ONNX yolunda birleştirmek ayrıca
araştırılabilir. Microsoft yeni Windows ONNX dağıtımlarında WinML'e yöneltiyor;
DirectML EP sürdürülüyor ancak yeni geliştirme WinML tarafında. Dinamik EP
indirmeleri Windows 11 24H2+ ve ilgili sürücü/cihaz koşullarını gerektiriyor.
Bu, bugün RVC/RoFormer modellerine bir ayar ekleyerek sağlanacak destek değil:
ONNX export, dinamik uzunluk, STFT/complex operator, F0, vocoder ve ses
eşdeğerliği ayrı doğrulanmalı; GAN eğitimi ayrı PyTorch backend'lerinde kalır.
[ORT DirectML yönlendirmesi](https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html),
[Microsoft WinML sağlayıcıları](https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/supported-execution-providers).

## 5. Yayına hazırlanma sırası ve kabul ölçütleri

1. **Destek sözleşmesi ve build:** minimum Windows/x64/RAM/disk/CPU komut
   seti; CPU/CUDA/HIP/XPU ayrı lock dosyaları; tek ORT dağıtımı; temiz,
   tekrarlanabilir build; kişisel model/veri paketlenmediğinin kontrolü.
2. **Hata güvenilirliği:** SystemExit sonucu, yükseltmeli installer, imza/hash,
   interprocess kayıt kilidi, boş worker hatası, checkpoint timer ve başlangıç
   import tanısı. Her biri için ilgili hata senaryosu regresyonu.
3. **Bellek ve performans:** RMVPE küçük pencereler, index kopyası, resume tepe
   belleği, yardımcı cache, thread havuzları, disk/parça tahmini ve ad sınırı.
   Önce/sonra aynı girdide süre ve RAM/VRAM ölç; kaliteyi dinleyerek karşılaştır.
4. **Donanım matrisi:** Intel ve AMD CPU; en az farklı VRAM/mimari sınıflarında
   NVIDIA; güncel resmi matristen AMD; Intel Arc A/B ve uygun Core Ultra.
   Her backend'de beş ayrıştırma modeli, RVC + RMVPE/CREPE, index açık/kapalı,
   eğitim forward+backward+stop/resume/export/cover testleri.
5. **Gerçek kullanım:** 10 saniye, 5 dakika ve 30–60 dakika ses; düşük/normal/
   yüksek perde, sessizlik, stereo faz iptali, Unicode/uzun yol, salt okunur
   çıktı, dolu disk, bozuk model/index, çevrimdışı kullanım, iptal ve driver
   reset. Native çökme GUI'yi düşürmemeli; eski çıktı/checkpoint korunmalı.
6. **Dağıtım ve erişilebilirlik:** yeni EXE ve installer'ı temiz Windows'ta
   normal kullanıcıyla kur/güncelle/kaldır; NVDA/JAWS, DPI/yüksek karşıtlık,
   odak ve bitiş bildirimleri; lisans/notices ve yayın metadata'sı.

Benchmarks: ilk açılış/import, soğuk/sıcak model yükleme, gerçek-zaman faktörü
(işleme saniyesi / ses saniyesi), RAM/VRAM tepe ve boş alan, cancellation
gecikmesi, checkpoint süresi/boyutu ve sonraki işte kaynak geri kazanımı.
Sentetik küçük test, gerçek şarkının işitsel kalite ölçümü yerine geçmez.

Korunacak mevcut kararlar: kaynak kayıtların değişmemesi; atomik çıktı;
açık CPU/GPU tercihi; eğitim/değerlendirme ayrımı; FP32 ve 40 kHz doğrulanmış
profil; bütün train vektörlerini tutan Flat index; latest/best-mel ayrımı;
kişisel model ve seslerin Git/paket dışında kalması. Kullanıcının RVC
tercihini veya ölçülmemiş kaliteyi evrensel üstünlük diye sunmama.
