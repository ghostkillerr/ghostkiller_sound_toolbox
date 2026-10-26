# Güncel durum — 26 Ekim 2026

## Açılış gecikmesi düzeltmesi — kabul sürüyor

Kullanıcı NVIDIA CUDA setup'ın UAC izninden sonra yaklaşık üç dakika
beklediğini, kurulu uygulamanın da geç açıldığını bildirdi. Önceki yayımlanmış
kurulumun EXE'si 2,14 GB, içindeki uygulama EXE'si yaklaşık 81 MB idi.
Kaynakta boş verili gizli pencere yaklaşık 0,67 saniyede oluştu; aynı
bilgisayardaki önbellekli eski frozen worker yaklaşık 0,5–0,9 saniyede açıldı.
Bu ölçümler kullanıcının üç dakikalık beklemesini yeniden üretmedi.

- PyInstaller uygulama arşivi EXE dışına, yanındaki aynı adlı `.pkg` dosyasına
  taşındı. Paket doğrulaması bu dosyayı zorunlu tutar.
- Otomatik donanım kontrolü Torch/CUDA'yı artık arayüz sürecine yüklemez;
  sahipliği uygulamaya ait ayrı worker içinde çalışır ve iptal edilebilir.
- Elle kurulum için küçük setup EXE'si ve sıkıştırılmış `.bin` parçaları tek
  `_offline.zip` içinde hazırlanır. Tamamı aynı klasöre ayıklanmalıdır.
  Mevcut otomatik güncelleme protokolü ZIP kabul etmez.
- Normal uygulama günlüğü Python girişini, pencerenin gösterilmesini ve olay
  döngüsünün hazır olmasını süreç başlangıcından itibaren ölçer.
  `--startup-probe` gizli, boş verili pencereyi ölçer; kişisel dosyaları,
  modelleri, mikrofonu veya ağı kullanmaz. Soğuk açılış/görünür pencere testi değildir.

Yerel kanıt klasörü: `build/startup_20261026/`. Yeni paketlerin derleme ve
temiz Windows kabulü tamamlanmadan aşağıdaki yayımlanmış paketlerin
değiştirildiği varsayılmamalıdır. Sürüm numarası **2.1.0** olarak korunur.

Teknik gerekçe: Inno Setup, büyük EXE'lerin Windows'ta açılışı
yavaşlatabileceğini belirtir ve ayrı veri parçalarını önerir
([Inno değişiklikleri](https://issrc.innosetup.nl/whatsnew.htm),
[DiskSpanning](https://jrsoftware.org/ishelp/topic_setup_diskspanning.htm)).
Bu, kullanıcıdaki gecikmenin kesin nedeninin saptandığı anlamına gelmez.

## Önceki tamamlanan 26 Ekim yayını

| Konu | Doğrulanmış durum |
| --- | --- |
| Yayın | **2.1.0 — 26 Ekim yenilemesi**; CPU/CUDA kurulumları, receipt ve hashli manifest yayımlandı |
| Kurulumlar | CPU **373.901.992 bayt**, NVIDIA CUDA **2.136.914.047 bayt** |
| Kaynak | Commit **3c4f7b6**; yerel CPU/CUDA ayrı ayrı **472 test**; [CPU/CUDA/XPU kaynak CI](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/40265608581) başarılı |
| Paket testleri | İki gerçek frozen EXE; 24 biçim/kanal dönüşümü, yardım ve model formu kontrolü; fiziksel NVIDIA Torch ve ONNX CUDA preflight başarılı |
| Temiz Windows | [CPU kabulü](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/40266512734) · [CUDA kabulü](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/actions/runs/40292190906): ilk kurulum, aynı paketle yeniden kurulum, iki açılış ve kaldırma; örnek kullanıcı dosyaları korundu |
| Siteler | GitHub Pages kaynakları ve sunucudaki Ghostkiller sayfası yeni tarih/paket bilgileriyle güncellendi; diğer proje alanları korundu |
| Sürüm davranışı | **2.1.0 korundu**; mevcut 2.1.0 kullanıcıları aynı backend paketini **elle yeniden kurmalı** |
| İmza | Dijital yayıncı sertifikası yok; SHA-256 ve derleme receipt'leri yayımlandı |

## 26 Ekim yayın kanıtı

25 Ekim kullanılabilirlik düzeltmeleri yeni CPU/CUDA kurulumlarına dahil edildi.
Paketlenen kaynak [v2.1.0-source-20261026](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/tree/v2.1.0-source-20261026)
etiketindedir; ilk yayının `v2.1.0` etiketi değiştirilmedi. Kaynak SHA-256:
`9f01b06ba6e6f7b414823cafb56397dc4a24f535c3be50ac27254854ac2519ba`.

- CPU SHA-256: `71fea69c5a691a87eef509d0c511bbcf9ea6dc2702b40d82058b3970ced348a8`
- CUDA SHA-256: `226c54bf8db0f633d9f7d1e56388a9c5c8a5aae7530d06967bed44f75a761ee4`
- Yerel derleme, frozen, yükleme ve kabul kanıtları: `build/release_20261026/`.
- Önceki 23 Ekim dosyaları Release'te `.previous-20261023` adlarıyla korundu.
- Sunucu sayfası ve proje metni yedeklenerek güncellendi; sayaçlar, diğer proje
  alanları ve dosya sahipliği/izinleri korundu. HTTP sayfa ve indirme yönleri doğrulandı.

Gerçek NVDA/JAWS anonsları, %125/%150 ölçekleri, uzun eğitim, gerçek mikrofon
ses kalitesi ve akustik gecikme kabulü açık kalır. Otomatik kurulum testleri
bu kullanıcı denemelerinin yerine geçmez. Kişisel ayar/model kayıtları korunmuştur.

## 25 Ekim kullanılabilirlik düzeltmeleri — 26 Ekim paketlerine dahil

[İncelemedeki 15 bulgu](KULLANILABILIRLIK_INCELEMESI_2026-10-25.md) için kod ve
kullanım belgeleri güncellendi. [Yeni arayüz rehberi](ARAYUZ_KULLANIMI.md)
beş ekranın temel akışını ve klavye erişimini anlatır.

- Seçili eğitim modelini tek başına kaydetme, toplu kayıtta tercih edilen adayı
  koruma ve kalıcı kopyası bulunmayan tercihte temizliği engelleme eklendi.
  Oturum kalıcı kayıttan sonra tutulur; teknik dosya temizliği ayrı işlemdir.
- Başlat/durdur/durum alanı sabitlendi. Koyu tema seçenekleri düzeltildi;
  canlı sesin teknik ayarları ve günlükler açılır bölüme alındı. Ctrl+Tab alt
  alanda da çalışır; F6 işlem alanına, F1 çevrimdışı yardıma gider.
- Vokal/temizlik zinciri, standart ve deneysel enstrüman yöntemleri açıklandı.
  Sonuç listesi, dinleme/klasör açma ve vokali AI Cover’a aktarma eklendi.
- Tek model ekleme formu, arama, seçili sayısı, bağımsız liste yönetimi ve eksik
  form yönlendirmesi eklendi. Ses tonu ve index katkısının anlamı düzeltildi.
- Model hazırlığında indirme öncesi boyut/onay ve göreve dönüş eklendi.
  Onay penceresi, tahmin işinin kilidi bırakıldıktan sonra gösterilir.
- Açılış bilgi penceresi kaldırıldı; geliştirici ve kopyalanabilir paket kimliği
  Hakkında alanına taşındı. Yeni build metadata’sı UTC derleme tarihini içerir.

**Kanıt:** CPU/CUDA tam testleri ayrı ayrı **472**; 14 yeni akış regresyonu.
İki ortamda `pip check` ve release preflight başarılı. Native yerleşim testi
800×850, 680×600 ve 1000×700 pencerelerde beş sekmenin alt durum alanını denetler.
Son doğrulama: **26 Ekim 2026**. Yerel kayıtlar:
`build/usability_20261025/` (test/preflight logları ve `verification.json`).
Kişisel `settings.json` ve `models.json` SHA-256 değerleri başlangıçla aynı;
kişisel ses/model/eğitim verileri değiştirilmedi.

**Açık kabul sınırı:** İlk görsel kontrol sonrası bilgisayar kontrolü kullanıcı
Escape tuşuyla durdurduğundan son değişikliklerin etkileşimli görsel tekrarı
bitmedi. Gerçek NVDA/JAWS, Windows %125/%150 ölçekleri ve ses kalitesi kabulü
ayrıca yapılmalıdır. Otomatik yerleşim testi bunların yerine geçmez.

**Dağıtım:** Bu düzeltmeler 26 Ekim 2.1.0 CPU/CUDA kurulumlarına dahil edildi.
Güncel paket kanıtı yukarıdadır. Aşağıdaki 23 Ekim bölümleri önceki yayının
tarihsel kayıtlarıdır.

## 23 Ekim yenilemesi ve kaynak kimliği

22 Ekim incelemesindeki eğitim temizliği/kilit, indirme sınırı ve model/index/
CUDA seçimi düzeltmeleri bu kurulumlardadır. Deneysel Canlı AI Cover, otomatik
ses eşiği, erişilebilir seçimler ve düzenli epoch modelleri de paketlenmiştir.
Gerçek mikrofon ses kalitesi, akustik gecikme, uzun eğitim ve bütün arayüzde
NVDA/JAWS kabulü açık kalır; kurulum testleri bu kabulün yerine geçmez.

Paketlenen kaynak commit'i **`b519bba`**, [sabit kaynak etiketi](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/tree/v2.1.0-source-20261022).
İki paketin ortak source SHA-256 değeri:
`9d774349e11bcdc3191b7924877a1610ae6c63c038d36134fe84e8dcf9a8beef`.
İlk yayının `v2.1.0` Git etiketi değiştirilmedi. Release'teki önceki dosyalar
`.previous` ve `.previous-20261020` adlarıyla geri dönüş için korundu;
indirilecek güncel kurulumlar normal `.exe` adlarıdır.

- CPU SHA-256: `c95948ab3583412203c566fc31ecd50513617aa7d29f7d3118a004a19531ddc6`
- CUDA SHA-256: `eb67e89289f9afead5e5b330b8ebfcc5fc756ec95f513c78655a6037d5d8dba6`
- Yerel derleme, frozen, receipt, yükleme ve kabul kayıtları: `build/release_20261022/`.
- Yerel kaynak regresyonları ve korunmuş veri envanteri: `build/audit_20261022/`.

[Kurulumları indir](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0) ·
[Program sitesi](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/) ·
[Ekransız Oyuncular](https://ekransizoyuncular.gen.tr/projeler/ghostkiller_sound_cleaner).

## 23 Ekim site yayını

Ekransız Oyuncular'daki Ghostkiller sayfası ve ilgili proje açıklaması yeni
kurulumlarla eşleştirildi. Tarih, boyut, SHA-256, deneysel canlı ses açıklaması
ve aynı sürüm için elle kurulum bilgisi güncellendi. Dosya sahipliği/izinleri,
diğer proje alanları ve indirme sayaçları korundu; önceki içerik yedeklendi.

Canlı HTTP denetiminde sayfa `200`, iki paket için HEAD isteği doğru GitHub
dosyasına `302` verdi. HEAD istekleri sayacı artırmadı. `download[]=cpu`
gibi dizi parametreleri artık PHP hatası oluşturmuyor; sayfa `200` açılıyor.
Tarayıcıda yeni tarih, paket seçimi ve açıklamalar doğrulandı. GitHub Pages
için dört JavaScript ve üç site paketleme testi geçti.

## Yayın sonrası derleme temizliği

İki setup'ın kabulünden sonra yeniden oluşan CPU/CUDA `release_dist` ve
`release_work` klasörleri kaldırıldı: **7.334.676.222 bayt (6,83 GiB)**.
Ölçülen boş disk alanı artışı **5,66 GiB**. Güncel iki setup, receipt'ler,
hazır ortamlar, kaynak/lisans materyali ve derleme kanıtları saklandı;
PyInstaller teşhis tabloları sıkıştırıldı. Koruma listesindeki **2.019 dosya**
silmeden önce ve sonra SHA-256 ile aynı bulundu. Ayrıntı:
`build/release_20261022/cleanup-verification.json`.

## Önceki denetimlerin tarihli kayıtları

Aşağıdaki bölümler kendi tarihlerindeki durumu korur. “Henüz yayımlanmadı” veya
“kurulumlar üretilmedi” ifadeleri güncel 23 Ekim paket durumunu anlatmaz.

## 22 Ekim kod incelemesi ve disk temizliği

[Ayrıntılı inceleme](KOD_INCELEMESI_2026-10-22.md), mimariyi, hata tetikleyicilerini,
düzeltmeleri, regresyonları ve kalan bakım borcunu açıklar. Başlangıçta 441 test
geçiyordu; 17 yeni testle CPU ve CUDA ortamlarında ayrı ayrı 458 test geçti.

- Eğitim temizliği, başarısız fakat devam edilebilir bağlı oturumları, özgün/
  karşılaştırma kayıtlarını ve model listesinde kullanılan dosyaları korur.
  Yarım kalan silme ayrı durumla yeniden denenebilir; o oturum çalıştırılmaz.
- Devam doğrulaması oturum kilitlerini alır; UI iptal işaretini kilitsiz silmez.
  Oluşturma ve temizleme aynı yaşam döngüsü kilidini kullanır.
- Model indirmelerinde metadata/model boyutu ve bilinmeyen uzunluktaki akışın
  disk boşluğu sınırlandı. RVC'nin seçilen index yolunu `trained`/`added`
  değişimiyle başka dosyaya çevirmesi kaldırıldı. ONNX'e seçili CUDA cihaz
  numarası da iletilir.
- Temizlik ayrı `training/cleanup.py` modülüne taşındı; model doğrulama ve
  cache yolları için backend'in UI modülü yüklemesi kaldırıldı.
- Eski `release_dist_cpu/cuda`, `release_work_cpu/cuda` ve asıllarıyla hash'i
  eşleşen iki `.candidate.exe` kaldırıldı: toplam **9,17 GiB dosya**.
  Ölçülen serbest disk alanı artışı **6,07 GiB**. Setup'lar, hazır ortamlar,
  lisans/kaynak materyali ve derleme kayıtları korundu. Koruma envanterindeki
  **2.019 kişisel/veri dosyası** ve iki setup hash ile yeniden doğrulandı.

Kanıtlar `build/audit_20261022/` içindedir. Eski PyInstaller teşhis kayıtları
sıkıştırılarak burada saklandı; temizlenen dist/work klasörleri sonraki
derlemede yeniden üretilir. Bu düzeltmeler kaynakta; aşağıdaki 19 Ekim yerel
setup'ları bunları içermez. Yeni installer, yayın veya fiziksel mikrofon testi
yapılmadı. Uzun gerçek eğitim, ses kalitesi ve NVDA/JAWS kabulü açık kalır.

## 19 Ekim devam kontrolü: yeni yerel paketler hazır

Limit sonrası denetimde CPU ve CUDA için yeni gerçek 2.1.0 setup'ların
üretildiği doğrulandı. 19 Ekim paketleme anındaki kaynak kimliği, iki build-info, iki
receipt ve frozen raporları aynı:
`f9c4e600ad33cca82ae91d3572eee25aceec4e92d45de952d2ab22d62eb2cea7`.
CPU **373.870.115 bayt**, CUDA **2.136.866.539 bayt**; iki dosyanın SHA-256 ve
boyutu kendi receipt'leriyle yeniden eşleşti. Paketli açılış raporlarının ikisi
de başarılı; canlı gate ve sentetik mikrofon ölçümü fiziksel mikrofon açmadan
kontrol edildi. Kanıtlar `build/release_20261019_live/` altındadır.

19 Ekim kontrolünde bu paketler henüz GitHub indirmeleri değildi; Release üst
tablodaki 18 Ekim dosyalarını sunuyordu. Yeni setup'ların temiz Windows kurulum/yükseltme/
kaldırma kabulü bekler; önceki paketlerin kabulünü bu dosyalara genellemeyin.
Kullanıcının koruduğu **2.1.0** numarası nedeniyle mevcut 2.1.0 uygulaması bu
yenilemeyi daha yeni sürüm diye algılamaz (`updater.py` yalnız daha yüksek sürümü
teklif eder). Aynı sürümle dağıtımda bu kullanıcılara elle kurulum gerektiği
açıklanmalıdır; sürüm numarası kendiliğinden değiştirilmez.

Yerel site değişikliklerinde dört Node testi, site üretimi ve Git indeksinin
kişisel veri/yol kontrolü geçti. Bu kontrol kaynak veya site gönderimi yapmadı;
site/tanıtım değişiklikleri ve `.agents/` kullanıcı çalışması korunur. Son
rehber commit'i yerelde, Canlı AI Cover kaynak commit'i GitHub master'dadır.
Yeni paket ve site yayını için güncel kullanıcı talimatı gerekir.

[2.1.0 kurulumları](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0) · [Program sitesi](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/).
Projeye giriş [oku.md](../oku.md), yeni yayın reçetesi [RELEASE_BUILD.md](RELEASE_BUILD.md).

## 19 Ekim kaynak geliştirmesi — tarihsel kayıt

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
- Canlı model hazırlığı ve seçilen aygıt açılışı tamamlanınca seçilen çıkıştan
  kısa bir hazır sesi üretilir. İşlem/enstrüman/model seçimlerinin erişilebilir
  rolü onay kutusuna çevrildi; gerçek onay kutuları da işaretli/işaretsiz
  durumunu doğrudan canlı kontrol değerinden bildirir.
- Model eğitiminde kayıt aralığı ve tutulacak son epoch modeli sayısı ana formda
  sorulur. Kalıcı kayıt seçildiğinde tutulan epoch modelleri model adına ait
  temiz klasöre `Ad_Epoch_NNN.pth` adlarıyla yazılır ve tek `Ad.index` paylaşır.
  En eski ara modeller kesin sayı sınırına göre budanır. Eğitim oturumu işlemleri
  tek seçim menüsünde toplandı; teknik klasör bitişte kendiliğinden açılmaz.
  Model kaydında teknik oturum boyutu gösterilip önerilen temizlik onayı alınır;
  onaylanırsa checkpoint, hazırlık verileri ve test sesleri kaldırılır. Özgün
  kayıtlar ve kalıcı modeller korunur. Tamamlanan oturumlar oturum menüsünden de
  temizlenebilir; yarım ve bağımlı oturumlar reddedilir.
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

## İlk 18 Ekim yayınının doğrulama kanıtları

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

## Web sitesi canlı durum denetimi (20 Ekim 2026)

- `ekransizoyuncular.gen.tr` ana sitesi doğrudan sunucudaki kaynak üzerinden
  incelendi. Apache, MySQL ve Certbot zamanlayıcısı etkin ve açılışta devreye
  girecek durumda; sertifika 3 Aralık 2026 tarihine kadar geçerli ve otomatik
  yenileme zamanlayıcısı çalışıyor.
- Web kökündeki kurulum, aktarım, hata ayıklama ve şema değiştirme betikleri;
  ilk yönetici oluşturma sayfaları, eski `yayinci.php` aracı, Python/SQL/yedek
  dosyaları ve doğrudan veritabanı yapılandırma erişimi HTTP üzerinden kapatıldı.
- Dizin listeleme kapatıldı; HSTS, MIME koklama, çerçeveleme, yönlendiren ve
  tarayıcı izin başlıkları eklendi. Apache ayrıntılı sürüm başlığı gizlendi.
- Yönetici oturum çerezleri `Secure`, `HttpOnly` ve `SameSite=Lax` kullanıyor;
  girişte oturum kimliği yenileniyor. Eski MD5 hatırlama çerezi kaldırıldı,
  yönetim formlarına CSRF doğrulaması eklendi ve son yönetici hesabının
  silinmesi engellendi.
- Medya yükleme JPEG/PNG/GIF/WebP ve 8 MB ile sınırlandı; MIME doğrulaması,
  rastgele dosya adı ve yükleme klasöründe çalıştırılabilir dosya engeli eklendi.
  Yükleme klasörü izni `0755` olarak daraltıldı.
- Ziyaretçi sayfalarında API içeriği HTML/URL bağlamına göre temizleniyor.
  Proje açıklamalarındaki izinli zengin metin korunuyor. Rehber kartlarındaki
  çalışmayan uyarı düğmesi yerine `/rehber/<id>` ayrıntı sayfası ve API ucu
  eklendi; rota kuralları uzantısız özel yollar önce çözülecek biçimde düzeltildi.
- İndirme sayacı yalnız geçerli dış bağlantı veya gerçekten bulunan yerel dosya
  için artıyor; yerel yol ve dosya adı doğrulaması sıkılaştırıldı.
- Canlı doğrulamada ana sayfa, projeler, Ghostkiller sayfası, videolar, yayınlar,
  rehberler ve yönetici girişi `200`; kapatılan bakım/kurulum uçları `404/403`
  verdi. JavaScript ve PHP sözdizimi ile Apache yapılandırma testi geçti.
- Geri dönüş yedekleri sunucuda `/root/backups/` altındaki
  `ekransizoyuncular-20261020-site-hardening`,
  `ekransizoyuncular-20261020-public-fixes` ve
  `ekransizoyuncular-20261020-final-hardening` klasörlerindedir.
- SEO denetiminde `www` ve ana alan adı ile `.html`/temiz URL çiftlerinin aynı
  içeriği `200` ile verdiği, sitemap'in eski `www` yollarını kullandığı ve genel
  sosyal paylaşım görselinin `404` döndüğü saptandı. `www` ve eski `.html`
  yolları kalıcı olarak ana temiz URL'lere yönlendirildi; robots ve sitemap
  güncellendi, ana sayfalara canonical/Open Graph/Twitter etiketleri eklendi.
- Ana sayfaya `Organization`, Ghostkiller sayfasına `SoftwareApplication`
  JSON-LD verisi eklendi. JavaScript çalıştırmayan tarayıcıların da proje adını
  ve açıklamasını görebilmesi için ana sayfa ile proje listesine başlangıç
  içeriği kondu. İçeriksiz rehber listesi geçici olarak `noindex,follow` oldu.
- ImageGen ile üretilen genel sosyal paylaşım görseli 1200×630 PNG olarak
  `uploads/ekransiz-oyuncular-og-20261020.png` yolunda yayına alındı. SEO geri
  dönüş yedeği `/root/backups/ekransizoyuncular-20261020-seo/` altındadır.
