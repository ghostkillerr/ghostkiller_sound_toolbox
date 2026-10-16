# Ghostkiller Sound Toolbox — Geliştirme, kurulum ve yayın rehberi

Son güncelleme: **16 Ekim 2026**. Bir yapay zekâ ajanı işe başlamadan önce bu
dosyayı okumalı, sonra ilgili kaynakları ve güncel çalışma ağacını incelemelidir.
Kullanıcının sonraki talimatı bu rehberden önceliklidir. Eski raporlar tarihsel
kanıttır; bu rehberdeki güncel durumla karıştırılmamalıdır.

**16 Ekim yerel disk temizliği ve inceleme:** Kullanıcının talimatıyla eski
diagnostic/tekrarlanan derlemeler, eski Python 3.12.0 CPU/XPU ortamları ve geçici
`.pth` ortamı, paketleme çalışma dosyaları, pip önbelleği ve kanıtı bulunan yapay
eğitim çıktıları kaldırıldı: **28,74 GiB / 215.261 dosya**. Kişisel ses/model/ayarlar,
`build/release_cpu`, `build/release_cuda`, `build/release_python`, iki installer,
en son `build/rebuild_2026_10_16/dist_cpu` ve `dist_cuda` paketleri, lisans/kaynak
materyalleri ve tarihsel raporlar korundu. Eski raporlardaki kaldırılmış artifact
yolları tarihsel kayıttır; yeniden çalıştırma için güncel ortamları kullan.
CPU/CUDA 306'şar kaynak testi, gerçek CUDA ortam kontrolü, dört site testi ve
temizlik sonrası kaynak/worker başlangıcı geçti. GitHub'a gönderim/yayın yapılmadı.
Temizlik kanıtları `build/workspace_audit_20261016/`; sade sonuç ve kalan eksikler
[yerel inceleme raporunda](docs/YEREL_TEMIZLIK_VE_INCELEME_2026-10-16.md).
Ayarlar'da isteğe bağlı modellerin de başlangıçta seçili olması ve Windows CI'nin
tüm kaynak testlerini çağırmaması mevcut bulgulardır; bu görevde değiştirilmedi.

**16 Ekim sonraki kaynak değişikliği:** İsteğe bağlı kısa vokal onarımı uygulamaya
eklendi. Arka vokal temizliği açılınca görünür, kapatılınca kapanır/gizlenir;
varsayılan kapalıdır. Standart ve onarılmış mono sonuç ayrı kaydedilir. Mevcut
aç/kapat düzeni, NVDA için dinamik ad/basılı durum/eylem ve Tab sırası korundu.
Kullanım: [Kısa vokal onarımı](docs/VOKAL_ONARIMI.md). A2SB işleyicisi, sabit SHA
model doğrulaması, lisans materyalleri ve frozen kaynak listesi eklendi.
Mevcut ağırlık Ayarlar model listesinde hazırlandı. Gerçek CUDA worker onarım,
ilerleme ve iptal kontrolü geçti. CPU ve NVIDIA ortamlarında 306'şar kaynak
testi geçti; canlı NVDA dinlemesi ayrıca bekleniyor.
Son kaynak kanıtı `build/restoration_checks_20261016/verification.json`;
iki ortamın `*_tests_final.log` kayıtları ve son erişilebilirlik kontrollerinin
`*_accessibility_final.log` dosyaları aynı klasördedir. Bu yerel kayıtları Git'e ekleme.
`build/training_release_verified.json` artık kaynak doğrulamasının başarılı,
mevcut installer'larla kaynak eşleşmesinin ise **geçersiz / yeniden derleme
bekliyor** olduğunu ayırır. Buradaki `ok: false` değerini onarımın çalışmadığı
şeklinde yorumlama; eski paketlerin son kaynağı içermediğini gösterir.
**Aşağıdaki 01:28 kurulum kanıtları bu kaynak ekinden öncedir; yeni seçenek
henüz installer'larda yoktur.** Kurulumların güncel kaynakla eşleştiğini söyleme.

**16 Ekim 01:28 kurulum sonucu (sonraki kaynak ekinden önce):** CPU ve NVIDIA CUDA **2.1.0** kurulumları o andaki
kaynaklardan yeniden üretildi ve **01:28** son doğrulamasından geçti. Yeni
çıktı/çalışma/cache yolları `build/rebuild_2026_10_16/` altında; iki installer
ve yeni `.build.json` kayıtları `Setup/` içindedir. İki pakette kaynak kimliği
aynı (`e7a188f4…`); boyut/hash/receipt, lisans/ikon/helper ve frozen eğitim
modülleri doğrulandı. CPU **296**, CUDA **296** kaynak testi; iki frozen açılış
ve iki ayrı yerel Inno kurulum fixture'ı geçti. CUDA, ilk frozen ve fixture'a
kurulan kopyada **RTX 5060 Ti** üzerinde Torch/ONNX GPU testlerinden geçti.

Inno'nun 27 dosyası eski doğrulanmış hash'lerle, Python'ın 55 yerel bileşeni
özgün arşivle; iki ortamda 103'er dağıtımın toplam 83.180 RECORD dosyası
hatasız eşleşti. Yeni paket/installer başlıklarında özgül Jeefo işareti yok;
bilinen servis/dosya/mutex izi yok. **Defender kullanıcının tercihiyle tamamen
kapalı kaldı; yeni antivirüs taraması yapılmadı.** Bütünlük/özgül işaret
kontrollerini tam antivirüs temizlik garantisi olarak sunma veya korumayı
kendiliğinden açma. Eski enfeksiyon uyarısı yedeklenip kaldırıldı.

Güncel rapor: [16 Ekim yeniden derleme](docs/KURULUM_YENIDEN_DERLEME_2026-10-16.md).
Teknik bilgi gerektirmeyen ilk deneme ve kullanıcıdan beklenenler:
[İlk deneme rehberi](docs/KULLANICI_KABULU.md).
Makine kanıtı `build/training_release_verified.json` ve yeni build klasöründeki
`candidate_verification.json` dosyalarıdır. **Temiz Windows/üretim UAC/eski
sürümden geçiş/uninstall ve kullanıcı kabulü bekliyor**; üretim installer veya
Sandbox geliştirici hostta başlatılmadı. Yayın/push yapılmadı; `version.json`
2.1.0 / unpublished / boş packages kalır. Eski raporlar tarihsel kanıttır.

**15 Ekim 21:22 kullanıcı tercihi:** Kullanıcı Defender'ı önceki şekilde kapatmayı
açıkça istedi. Önceden değiştirilen yerel `DisableAntiVirus` değeri yedeklenip
**1** yapıldı. Microsoft imzalı aracın tam kapatma isteği Windows tarafından
**0x80070005 / erişim engellendi** ile reddedildi. Standart cmdlet ile
**gerçek zamanlı koruma kapandı**; son sorguda `AntivirusEnabled=True`,
`AMServiceEnabled=True`, `RealTimeProtectionEnabled=False`. Tam hizmet
kapanması veya kalıcı kapanma doğrulandı deme. Kurcalama koruması aşılmadı,
servis/driver izinleri değiştirilmedi, yeniden başlatma yapılmadı. Kullanıcının
bu açık tercihine karşı korumayı otomatik yeniden açma. Yerel işlem ve yedek:
`build/defender_disabled_2026_10_15/result.json` ve `before.json`.

**15 Ekim 20:34 son kontrol:** Silme sonrası yeni tam Defender taraması
**19:00:02–20:33:09 arasında tamamlandı** (1:33:07). Aynı tarama kimliğine ait
1000/1001 olayları ve komut sonucu **0** doğrulandı. Başlangıç kayıtlarıyla
karşılaştırmada **yeni tespit, yeni kaynak yolu ve yeni tehdit olayı yok**.
20:34 kontrolünde bilinen Jeefo servisi/dosyası/mutex'i, başlangıç/görev eşleşmesi
ve silinen 14 kaynağın geri oluşması yok; örnek 11 dosyanın SHA-256 değerleri
19:02 kaydıyla aynı, 8 Microsoft paketi ve Inno derleyicisinin imzaları geçerli.
Defender ve gerçek zamanlı koruma açık; yönetici kontrolünde istisna yok,
yeniden başlatma gerekmiyor. Bu, gelecekte yeniden bulaşmama garantisi değildir.
Kurcalamaya karşı koruma kapalı. Kullanıcı Defender'ı kapatacağını söyledi;
onun tercihine karşı korumayı yeniden açma. Risk açıklandı; ayar değiştirilmedi.
Sonuç bildirimi için onaylanan `defender-son-tarama-sonucu` geçici takibi sonuç
kesinleşince **PAUSED** durumuna alındı; yeni tarama veya sürekli izleme başlatma.
Yerel rapor: `build/defender_recheck_2026_10_15/YENIDEN_BULASMA_KONTROLU.md`;
aynı klasörde `scan_state.json`, `progress_latest.json`, `command_result.json`
ve `verification_summary.json` kanıtları bulunur. Installer yeniden derleme
ve kabul engeli sürer; hiçbir yayın yapılmadı.

**15 Ekim 18:36 sonrası güncel güvenlik durumu:** Elektrik kesintisinden sonra
16:20'de yeniden başlatılan tam tarama **17:49:57'de tamamlandı**. Defender'ın
standart temizlemesinde 203 başarılı Jeefo onarım kaydı oluştu; örnek dört
Microsoft EXE'si yerinde ve imzası geçerli. Defender ve gerçek zamanlı koruma açık.

Kullanıcı önce dosyaları koruyan onarım istedi, ardından yedek/indirme kaynağı
olmadığını belirterek **kalan sorunlu dosyaların silinmesini açıkça istedi**.
Güncel kayıtlarla eşleşen **5 EXE ve 4 dış RAR arşivi**, ayrıca görevde oluşturulan
1 enfekte inceleme kopyası **18:34'te silindi**. Arşiv içi yollar ayrı fiziksel
dosyalar sayılmadı. Önceki dört CPU/CUDA 2.0.0/2.1.0 installer'ı da 16:19'da
silinmişti: toplam **13 asıl dosya + 1 inceleme kopyası**. Onarılmış programlar
bu silme listesine alınmadı. 18:36 kontrolünde bekleyen tespitlerle eşleşen mevcut
dosya/dış arşiv sayısı **0**; bu, silme sonrası yeni bir tam tarama değildir.
Kişisel tam yolları içeren son rapor yalnız yerelde:
`build/defender_repair_2026_10_15/SILINEN_DOSYALAR_RAPORU.md`.

Önceki geniş karantina/kural değişikliği otomatik onay denetimince reddedilmiş ve
çalıştırılmamıştı. Sonraki somut silme listesi yeni açık talimat kapsamında
uygulandı; Defender ayarı değiştirilmedi. Bu yetkiyi başka dosyalara genelleme.
Defender'ın kendi standart işleminde iki HackTool kaydı ayrıca karantinaya alındı.

**15 Ekim tarihsel paket engeli:** O gün dört installer silinmişti. Yeniden
derleme ve paket doğrulaması 16 Ekim'de tamamlandı; üstteki güncel raporu kullan.
Eski receipt'ları değiştirilmiş dosyaları geçerli göstermek için kullanma.
Kullanıcı kabulü ve yayın kararı hâlâ ayrı adımlardır.
Inno'nun orijinal paketi resmi SHA ile, 23 dosyası üretici imzalarıyla eşleşti.
7 Ekim'deki Jeefo servis izi, 14 Ekim'deki bu Inno kurulumundan daha eskidir;
ilk bulaşma kaynağı belirlenemedi. Kaynak düzeltmeleri korunur, yayın yoktur.
[Güncel engel ve kanıtlar](docs/KURULUM_GUVENLIK_ENGELI_2026-10-15.md).

## 1. Proje ve mevcut durum

Ghostkiller Sound Toolbox, Windows x64 / Python 3.12 / wxPython ile geliştirilen
Türkçe masaüstü ses uygulamasıdır. Geliştirici **Yasin Talha Gençsoy**.
Ses dosyalarını yerel işler; internet model indirme ve güncellemeler için kullanılır.

- **Müzik ve Ses Temizleme:** enstrümantal, ana vokal, arka vokal, yankı ve gürültü
  adımları; yerel RoFormer ve UVR modelleriyle PCM24 FLAC çıktıları. Arka vokal
  temizliği altında isteğe bağlı A2SB kısa vokal onarımı ve ayrı mono çıktı.
- **Ses Değiştirme:** yerel RVC `.pth` ve isteğe bağlı `.index` ile AI Cover;
  nota/pitch/index seçenekleri ve WAV çıktıları.
- **Model Eğitimi:** RVC V2 kayıt hazırlama, analiz, eğitim, durdur/devam,
  değerlendirme, index ve kalıcı ses modeli kaydı.
- **Ayarlar:** CPU/GPU tercihi, donanım denetimi, model indirme/kontrol/onarım,
  açık/koyu görünüm ve otomatik/elle program güncellemesi.

| Konu | Güncel durum |
| --- | --- |
| Uygulama sürümü | Yerel yayın adayı `version.json`: **2.1.0**, `distribution_status: unpublished`, `packages: {}`; master sürüm ilanı Release kabulüne kadar geriden gelir |
| Dağıtılacak iki profil | **CPU** ve **NVIDIA CUDA**; XPU/ROCm bu iki setup'ın yerine geçmez |
| Derleme ortamları | Bağımsız `build/release_cpu`, `build/release_cuda`; Python **3.12.15**, backend hash kilitleri |
| Inno Setup | Kullanıcı **7.1.0** kurdu; helper 7/6 standart yollarını bulur |
| Kaynak testleri | Son kaynakta CPU **306 / OK**, CUDA **306 / OK**; önceki installer kaynağında 296'şar test vardı |
| Otomatik güncelleme | Kaynakta uygulandı, varsayılan açık, Ayarlar'dan kapatılır; elle düğme/F5 korunur |
| Setup adayları | CPU/CUDA **2.1.0**, 16 Ekim 01:28 kaynağından üretildi; 296'şar test, frozen ve yerel kurulum fixture'ları geçti. Sonraki isteğe bağlı vokal onarımı bu installer'larda yok; yeni kaynak eşleşmesi için yeniden derleme gerekiyor |
| Eski setup adayları | Enfekte eski CPU/CUDA **2.0.0** dosyaları da aynı talimatla silindi; önceki koruma tercihi bu açık talimatla değişti. Receipt'lar yalnız tarihsel kayıt |
| Sandbox | Kullanıcı kurduğunu bildirdi; temiz Windows/üretim UAC kabul testlerini **daha sonra kendisi yapacak** |
| Kullanıcıya dağıtılan yeni sürüm | Henüz yok; GitHub kaynak gönderimi ve tanıtım sayfası, installer Release yayını değildir |

Önceki bağımsız paketler gerçek frozen smoke, sentetik ayrıştırma/cover ve yerel
Inno kurulum fixture'ından geçti. Son güncelleme değişikliğinde küçük gerçek
Inno fixture sessiz güncelleme/eski PID'yi bekleme/model-ayar korumayı
**exit 0 / 8.110 s** ile doğruladı. Bunlar temiz Windows, gerçek UAC etkileşimi,
eski üretim installer'ından geçiş veya bütün GPU'lar için kabul kanıtı değildir.

Güncel tanıtım sayfasının kaynakları `website/`, yayın akışı
`.github/workflows/pages.yml` içindedir. Adres:
**https://ghostkillerr.github.io/ghostkiller_sound_toolbox/**.
Sayfa indirme kayıtlarını `version.json` üzerinden alır; boş/yayımlanmamış
paketlerden sahte bağlantı üretmez. İlk gerçek Release henüz hazırlanmalıdır.

## 2. Kullanıcının kalıcı talimatları

### “Setupları yap” ne demektir?

“Setupları yap / setup hazırla / kurulumları oluştur” talimatı, kullanıcı açıkça
tek profil istemedikçe **CPU ve NVIDIA CUDA setup'larının ikisini de üret**
demektir. Tek backend üretip işi bitmiş sayma; backend seçimini tekrar sorma.
Güncel kaynakla iki PyInstaller EXE ağacı, sonra iki gerçek Inno installer üret.
`--check-only`, `Output=no`, diagnostic build veya eski EXE'yi yeniden
adlandırmak kurulum üretme şartını karşılamaz.

**İkisinde de zorunlu:**

- **Sözleşme:** `lisans.txt`; `.iss` içindeki `LicenseFile` normal ilk kurulumda
  sözleşmeyi gösterir ve kabul gerektirir. `.spec` dosyayı uygulamaya da paketler.
  Metni kullanıcı istemeden değiştirme; üçüncü taraf lisans haklarını koru.
- **İkonlar:** `logo.ico`; `.iss` `SetupIconFile`, `.spec` `EXE(icon=...)` ve
  paketli ikon. `UninstallDisplayIcon` uygulama EXE'sini gösterir. Başlat menüsü
  kısayolu ve kullanıcının `desktopicon` seçimine bağlı masaüstü kısayolu korunur.
- **Güncelleme yardımcısı:** `update_helper.ps1` paketlenir; installer gate
  varlığını ve kaynakla byte SHA eşleşmesini doğrular.
- **Dağıtım materyali:** FFmpeg tam kaynak/lisans/reçete manifesti, Python ve
  diğer bağımlılık notices/lisansları, RVC/eğitim config'leri ve zorunlu DLL'ler.
- **Teslim:** iki `.exe` ve aynı adlı iki `.build.json`; doğru sürüm/backend,
  aynı uygulama kaynak kimliği, gerçek installer SHA-256 ve boyut kanıtı.

Hata varsa düzeltip yeniden üret. Bir profil hâlâ engelliyse eksik çıktıyı
açıkça bildir; başarılıymış gibi sunma. Setup üretme tek başına yayın/push izni
değildir. Kullanıcı ayrıca GitHub'a gönder/yayımla dediğinde o kapsam uygulanır.

### Otomatik güncelleme davranışı

**Ayarlar → “Açılışta güncellemeleri denetle ve otomatik güncelle” varsayılan açık.**
`AppSettings.auto_update` kalıcı saklanır; kapalıyken açılışta ağ isteği yapılmaz.
**Güncellemeleri denetle** düğmesi ve F5 tercihten bağımsız elle denetler;
yeni sürümü indirip uygulamak için onay ister. Otomatik akış ayrıca indirme
sorusu sormaz. Kaynak geliştirme ortamı kendisini installer ile değiştirmez.

Güncelleme aynı backend'in doğrulanmış paketini mevcut dizine **sihirbaz
göstermeden** uygular ve programı yeniden açar. Program Files'a yazmak için
Windows UAC izni gerekebilir; UAC atlatılmaz. İptal edilirse program açık kalır.
Çalışan ses/eğitim/model/donanım işi kesilmez; otomatik güncelleme bekler.

Yardımcı süreç kendi kullanıcı yetkisiyle kalır; yalnız Inno yükseltilir.
Son boyut/header/SHA ve salt okuma kilidi kontrol edilir. Inno
`PrepareToInstall` eski PID kapanmadan dosyaları yazmaz. Installer sonucu ve
kurulan sürüm/backend doğrulanır; sonra uygulama yeniden açılır.
`PYINSTALLER_RESET_ENVIRONMENT=1` eski bootloader ortamını tekrar kullanmayı önler.
UAC iptalinde geçici dosyalar temizlenir. Başarısız sürüm yeniden başlatma döngüsü
yaratmaz; Ayarlar'dan elle tekrar denenir. Windows yeniden başlatma gereksinimi
ayrı bildirilir. Sonuç `update-result.json`, günlükler `update-logs/` altındadır.

### Git ve kapsam

**16 Ekim yeni talimat:** Kullanıcı kaynakları GitHub'a göndermeyi, gereksiz
commitleri birleştirerek geçmişi düzenlemeyi, ardından açık eksikleri düzeltip
yeniden göndermeyi açıkça istedi. Bu işlem için yeni bundle yedeği alınır;
ilk dört ana geliştirme aşaması korunur, eğitim düzeltmeleri ve sonraki
durum kayıtları ilgili özellik aşamalarında toplanır. Ağaç eşitliği ve uzak
HEAD doğrulanmadan geçmiş değiştirilmez; uzak güncelleme açık SHA'lı
`--force-with-lease` kullanır. Bu talimat installer Release yayını değildir.

Kullanıcı tek geliştiricidir: **ayrı dal/PR yerine doğrudan master** tercih eder.
Her küçük düzeltmede push yapma; birbiriyle ilgili değişiklikleri test edip tek
anlamlı commit'te biriktir. Bu görevde kullanıcı
rehber, biriken değişiklikler ve GitHub tanıtım sayfasını göndermeyi açıkça istedi.
Gelecekte yalnız yeni kaynak geliştirmesi istendiğinde bunu otomatik Release
yayını olarak yorumlama. Force push, eski release/tag değişimi veya kullanıcı
verisini silme normal iş akışı değildir.

14 Ekim 2026 tarihinde kullanıcı eski küçük teknik commit'lerin de
birleştirilmesini açıkça istedi. Bu **bir defalık geçmiş düzenlemesinde** eski
geçmiş doğrulanan yerel Git bundle yedeğine alınır, dört anlamlı geliştirme aşaması
korunur ve son dosya ağacının eksiksiz eşleşmesi kontrol edilir. Uzak HEAD kontrolü
ve `--force-with-lease` ile güncellenir; açık PR'sı olmayan, önceden master'a
birleşmiş iki eski dal da yedekte korunarak kaldırılır. Sonraki normal işlerde
geçmişi yeniden yazma veya force push yapma.

## 3. Veri ve mimari: nereden devam edilir?

16 Ekim gerçek kayıt denemesi: Kullanıcı, verdiği müzik dosyasıyla bütün uygulama
akışlarını sırayla denemek ve dinleyerek düzeltmek istiyor. Yerel tur planı
`deneme/private_model/05_rapor/TEST_PLANI.md`, özgün dosya kimliği
aynı klasördeki `session.json` içindedir; bu kayıtları/sesleri Git'e ekleme.
Geliştirme arayüzünde ilk müzik/vokal ayırma turu tamamlandı; kullanıcı “gayet
güzel ve profesyonel duyuluyor” diye değerlendirdi. İki PCM24 FLAC'ın bütünlüğü,
süresi ve özgün WAV'ın değişmediği doğrulandı. İlk kabul yalnız bu kayda aittir;
sıradaki arka vokal temizliği kullanıcı tarafından ana sesi kıstığı/bozduğu
için reddedildi. Kullanıcının önerisiyle önce yankı temizliği denemesi ve
aynı iki modelin iki sırasını karşılaştıran A–E sesleri hazırlandı. Beş
20 saniyelik dinleme örneği aynı bölüm/ortalama seviyede; süre/PCM24/sonluluk
ve özgün dosyaların korunduğu doğrulandı. Kullanıcı yankı öncesi/sonrası farkını
az buldu; yankı azken daha az bozulma olsa da ani seviye kaybının sürdüğünü
söyledi ve yapay tamamlama sordu. Sıra değişikliği çözüm olarak kabul edilmedi.
Yeni `03_vokal_koruma.json` denemesinde hafif sabit ve enerji kaybına bağlı
kaynak vokal karışımları üretildi ve kullanıcı tarafından dinlendi. Bunlar yapay ses üretimi
değildir, arka vokali geri getirebilir; enerji ölçümünü ana ses/kalite ölçümü
diye sunma. Bu karışım turunda kaynak/kurulum değişmedi ve yeni model indirilmedi.
Kullanıcı hafif karışımı yetersiz, değişken kaynak desteğini iyi ama
geliştirilebilir buldu; gerçek frekans üretimi yapan model araştırması istedi.
[Üretken vokal onarımı araştırması](docs/VOKAL_ONARIMI_ARASTIRMASI_2026-10-16.md)
kapsamında ayrı ignored alana Apollo ve NVIDIA A2SB kaynak/ağırlıkları indirildi
ve sabit hash'lerle doğrulandı. Apollo vokal uyarlamasıyla iki gerçek CUDA çıktı,
A2SB ile bir gerçek harmonik frekans çıktısı ve iki kısa aralığı onaran ayrı
bir çıktı üretildi. Aynı bölüm ve ortak seviye hedefiyle 12 mono PCM24 dinleme
örneği hazır; `07_uretken_model_karsilastirma.json` teknik kontrolleri geçti.
Kullanıcı 4 numaralı A2SB kısa aralık üretimini beğendi; hafif arka gürültü
bildirdi ve bu yöntemi standart arka vokal sonucuna uygulamamızı istedi.
`08_standart_temizleme_onarim.json` denemesi tamamlandı: aynı 45–65 saniyede
yedi kısa kayıp aralığına ve yumuşak geçiş çevresine üretim yerleştirildi;
diğer örneklerin hem dalga biçiminde hem ortak kazançlı PCM24 dışa aktarmada
birebir korunduğu doğrulandı. Bu, bütün şarkının veya stereo onarımın kabulü değildir.
Kullanıcı onarımı isteğe bağlı tutup standart sonucu da kullanmayı istedi;
bu tercih kaynakta uygulandı. Bütün kayıt için son dinleme kararı ayrıca bekleniyor.
Modellerin ses üretmesini ses kalitesi/aynı söz/nota veya ana
şarkıcı kimliği kanıtı sayma. A2SB mono olduğundan karşılaştırma kopyaları mono.
Araştırma turlarında uygulamanın kaynak/kurulumları ve üretim ortamları
değiştirilmemiş, yalnız ayrı araştırma bağımlılığı eklenmişti. Ardından kullanıcının
isteğiyle aşağıdaki isteğe bağlı özellik kaynakta uygulandı; bu entegrasyon için
üretim ortamlarına yeni bağımlılık kurulmadı. Yeni model/deney sesleri Git'e girmez.
Kanıt `deneme/private_model/05_rapor/02_sira_karsilastirma.json`;
kalıcı işleme sırası değiştirilmedi; sıra denemesi çözüm olarak kabul edilmedi.
Kullanıcı programı kullanırken eşzamanlı UI girişi gönderme.
Sonra arka vokal/yankı/gürültü, ses değiştirme, tek şarkıcı bölümüyle kısa eğitim
ve oturum özelliklerine geçilir. Tek şarkı/3 tekrar kalite kabulü değildir.

### İsteğe bağlı vokal onarımı: mevcut davranış ve kalan kontroller

**Müzik ve ses temizleme → 3. Arka Vokalleri ve Harmoni Seslerini Temizle**
açıkken hemen altında **Arka vokal temizliğinden sonra kısa vokal kayıplarını
onar** seçeneği görünür. Varsayılan kapalıdır. Ana seçenek kapatıldığında alt
seçim de kapanır ve gizlenir; gizli bir onarım seçimi çalıştırılmaz.

Standart arka vokal temizliği önce kaydedilir. Onarım açıksa A2SB yalnız kısa
kayıp bölgelerine üretim yapar; yumuşak geçişlerin dışındaki örnekler korunur.
`_Ghostkiller_2_ArkaSes_Silinmis.flac` ile
`_Ghostkiller_2_Onarilmis_Mono_Vokal.flac` ayrı kalır. Sonraki yankı/gürültü
adımları seçiliyse onarılmış dosyadan devam eder. Onarım başarısız olursa daha
önce tamamlanan standart dosya korunur. Onarılmış çıktı **mono**dur; standart
dosyanın kanal sayısı korunur. Uzun kayıp cümleler onarılmış sayılmaz.

`ui_separator.py` mevcut native aç/kapat düzenini kullanır. `ui_common.py`
içindeki `ToggleAccessible`, dinamik ad, basılı/basılı değil, devre dışı/gizli
durumu, açıklama ve aç/kapat eylemini sunar. Tab ile ana seçenekten görünen
onarıma, sonra yankı seçeneğine geçilir; gizliyken onarım atlanır. Odak
onarımdayken gizlenirse ana seçeneğe geri alınır. Canlı NVDA konuşması henüz
dinlenmedi; erişilebilirlik arayüzü ve klavye odağı kontrollerini bununla karıştırma.

Model Ayarlar listesinde **Kısa vokal kayıplarını onar: A2SB
(araştırma/değerlendirme)** olarak yer alır. Yaklaşık 2,26 GB ağırlığın sabit
SHA-256 ve ağ katmanları doğrulanır; bu bilgisayarda model hazırdır. Kapalı
onarım seçeneği bu modeli istemez/yüklemez. Çıkarım sırasında indirme yapılmaz.
NVIDIA'nın kod ve model lisansları ayrıdır; `restoration/vendor/` içindeki
lisans/NOTICE materyallerini paketlerden çıkarma veya ana uygulama lisansı
yerine geçmiş sayma. Ağırlıkları Git'e ya da installer'a ekleme.

Gerçek `NativeAudioSession` ile kaydın 55–60 saniyesinde üç aralık, ayrıca
bir saniyelik kısa örnekte bir aralık üretildi. PCM24 FLAC, süre, sonluluk,
geçiş dışı örnek eşitliği, kaynak hash'leri, ilerleme ve iptalde kısmi dosya
bırakmama doğrulandı. Kanıtlar yerelde `09_uygulama_onarim_dogrulamasi.json`
ve `10_uygulama_kisa_kayit_dogrulamasi.json` dosyalarıdır.

Sıradaki kullanıcı kabulü: canlı NVDA ile açık/kapalı okuması ve Tab/Boşluk
kullanımı; tam kayıtta standart/onarılmış sonuçların ana ses, arka vokal ve
gürültü açısından karşılaştırılması. Kullanıcıdan kod/komut veya teorik ayar
seçmesi istenmez. Yeni kurulum istendiğinde güncel kaynakla **CPU ve NVIDIA
CUDA installer'larının ikisi** üretilip doğrulanır; önceki EXE'ler yeniden
adlandırılarak güncel sayılmaz. Bu kaynak değişikliği yayın/push talimatı değildir.

15 Ekim eğitim geliştirmeleri: eğitim öncesi inceleme/bölüm seçimi, sınırlı
ara model arşivi, ortak ve isteğe bağlı ayrı test sesleri, model tercihi/not,
oturum/ayar karşılaştırması, epoch uzatma, önceki G/D'den yeni oturum, sıralı
deneyler ve hash doğrulamalı hazırlık tekrar kullanımı eklendi. Güncel kullanım
[eğitim rehberinde](docs/MODEL_EGITIMI.md), kanıtlar
[doğrulama raporunda](docs/EGITIM_GELISTIRME_DOGRULAMA_2026-10-15.md).
Eski teknik eğitim anlatımı `docs/MODEL_EGITIMI_TARIHCE_2026-10-13.md` içindedir.
`training/experiments.py`, `comparison.py`, `preparation_cache.py` ve
`ui_training_tools.py` bu yeni akışları yönetir. Eğitim matematiği/precision
değişmedi; epoch uzatmada yalnız kaydedilmiş checkpoint hash'ine bağlı hedef
artışı kabul edilir. Fine-tune ayrı oturumdur, tam resume diye sunulmaz.

| Dosya / grup | Görev |
| --- | --- |
| `main.py`, `ui_common.py`, `ui_*.py` | Native dört sekme, tema, klavye/erişilebilirlik, başlangıç ve worker/self-test dispatch |
| `app_runtime.py`, `app_settings.py` | Kaynak/model/veri dizinleri, ortak JOB_LOCK, UI dispatch, atomik ayar tercihleri |
| `audio_service.py`, `audio_worker.py`, `native_process.py` | Kalıcı ayrı audio worker, IPC/heartbeat, Windows Job Object, sınırlı iptal/temizlik |
| `separator_backend.py`, `separation_audio.py`, `separation_steps.py` | Yerel ayrıştırma cihaz/model adaptörü, adımlar, süre/PCM24/sonluluk kontrolleri |
| `restoration/audio.py`, `restoration/engine.py`, `restoration/vendor/` | İsteğe bağlı kısa kayıp seçimi, ayrı worker'da A2SB üretimi, yerel yumuşak geçiş, mono PCM24 ve üçüncü taraf lisansları |
| `rvc/infer/`, `rvc/lib/`, `rvc/configs/` | RVC dönüşüm, F0/helper cache, güvenli model/index kontrolü, synth/config'ler |
| `training/` | Analiz/dataset, FP32 GAN, checkpoint/resume, eval/index/kayıt, native worker |
| `hardware.py`, `compute_backend.py`, `model_manager.py`, `registry_store.py` | Açık cihaz seçimi, gerçek kernel denetimi, model bütünlüğü ve kayıt kilitleri |
| `app_version.py`, `updater.py`, `release_security.py`, `windows_installer.py`, `update_helper.ps1` | Sürüm, tercihe bağlı denetleme, backend URL/hash ve sessiz yerinde güncelleme |
| `.spec`, `Ghostkiller_Kurulum.iss`, `tools/release/`, `requirements/`, `third_party/` | Backend paketleme, lisans/kaynak/DLL kapıları, installer/manifest kanıtı |
| `website/`, `tools/build_site.py`, `.github/workflows/pages.yml` | Tanıtım/indirme sayfası, yalnız kamuya açık dosyaları hazırlama ve Pages yayını |
| `test/`, `docs/`, `.github/workflows/native-validation.yml` | Regresyonlar, açık fixture'lar, doğrulama raporları ve CPU/CUDA/XPU CI |

**Korunan kullanıcı yolları:** `deneme/`, `models/`, eski `modeller/`,
`rvc/models/`, `trained_models/`, `training_runs/`, `settings.json`, `models.json`.
`models/voices/private_model/` altındaki model/index özellikle korunur.
Ses/model/ayar/session dosyalarını topluca silme, üzerine yazma, Git'e veya
installer'a koyma. `build/`, `dist/`, `Setup/` ignored türetilmiş çıktıdır;
eski kullanıcı artifact'ini varsayımla temizleme. Windows recursive işleminden
önce mutlak hedefin workspace/owned session içinde kaldığını doğrula.

Modeller EXE yanındaki `models/` klasöründedir. Kurulu uygulamanın ayar/kayıt/cache
dizini `%LOCALAPPDATA%/GhostkillerSoundToolbox`; kaynak çalışmada repo köküdür.
`_MEIPASS` kaynak içindir. Bozuk JSON'u boş dosyayla ezme; OS/thread kilidi altında
read/modify/write ve atomik replace korunmalıdır.

Arayüzde kullanıcının kabul ettiği görünüm: açık/koyu native tema, yüksek
karşıtlıkta Windows renkleri; eğitim sayısal alan → odaklanabilir kutusuz düz
açıklama → sonraki alan. `ExplanationText` native StaticText rolündedir.
Eski salt okunur açıklama kutularını/tekrar eden Tab duraklarını geri ekleme.
Programatik MSAA testini canlı NVDA/JAWS anonsu diye sunma.

Ses/eğitim sözleşmeleri: UI getter'ları worker'da okunmaz; owned staging sonucu
doğrulanıp atomik yayınlanır. İptal eski başarılı çıktıyı korur. Enstrümantal kol
özgün girdiden çıkar; diğer seçili vokal adımları zincirlenir. Ham NaN/Inf gizlenmez;
FLAC PCM24 ve özgün süre korunur. RVC hop 160/helper cache/F0 pencere sınırları
ve varsayılan filtre/index/protect seçenekleri sessiz değiştirilmez. Dış model
`weights_only`/archive/shape sınırlarıyla; dış index sınırlı veri parser'ıyla
doğrulanır. Eğitim grup split'i overlap'tan önce yapılır; index yalnız training
feature'larından üretilir. Checkpoint tam D+G adımı sonrası optimizer/scheduler,
cursor ve RNG'yi birlikte saklar. CPU↔CUDA/XPU/ROCm aynı resume değildir.
Küçük sentetik test/tek mel L1 değeri bütün seslerde kalite kanıtı değildir.
Kullanıcı RVC'yi seçti; Seed-VC/TTS/realtime deneyi yeni açık ihtiyaç olmadan kurulmaz.

## 4. Ortamı hazırlama ve kaynak testleri

Repo kökünde PowerShell. Önce `git status`, sürüm/branch ve kullanacağın ortamı oku.
Bu workspace'te `build/release_cpu` ve `build/release_cuda` zaten bağımsız hazırdır;
kontrol etmeden silip yeniden kurma. `.pth` ile diğer ortamın site-packages'ini
paylaşan diagnostic venv üretim için kullanılmaz.

Temiz klon için örnek; güvenli **Python 3.12 x64** interpreter seç. Bu workspace'in
doğrulanmış interpreter yolu aşağıdadır; başka makinede mevcut doğrulanmış yolu
kullan. Python 3.12.0 frozen SciPy hatası nedeniyle reddedilir; runtime lisans
materyali seçilen interpreter/DLL ile eşleşmelidir.

```powershell
$basePython = 'build/release_python/cpython-3.12.15-windows-x86_64-none/python.exe'
foreach ($backend in @('cpu', 'cuda')) {
    & $basePython -m venv "build/release_$backend"
    if ($LASTEXITCODE -ne 0) { throw 'Venv hazırlanamadı.' }
    $python = "build/release_$backend/Scripts/python.exe"
    & $python -m pip install --no-deps --require-hashes -r requirements/bootstrap.lock
    if ($LASTEXITCODE -ne 0) { throw 'Bootstrap kurulamadı.' }
    & $python -m pip install --require-hashes --no-build-isolation -r "requirements/$backend.lock"
    if ($LASTEXITCODE -ne 0) { throw "$backend bağımlılık kurulumu başarısız." }
}
```

Test/derleme geçici dosyalarını proje içinde tut:

```powershell
$repo = (Get-Location).Path
New-Item -ItemType Directory -Force -Path build/agent_temp,build/hf_cache | Out-Null
$env:TEMP = (Resolve-Path build/agent_temp).Path
$env:TMP = $env:TEMP
$env:HF_HOME = (Resolve-Path build/hf_cache).Path
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONUTF8 = '1'
foreach ($backend in @('cpu', 'cuda')) {
    $python = "build/release_$backend/Scripts/python.exe"
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw "$backend pip check başarısız." }
    & $python -m tools.release.preflight --backend $backend
    if ($LASTEXITCODE -ne 0) { throw "$backend preflight başarısız." }
    & $python -m unittest discover -s test -v
    if ($LASTEXITCODE -ne 0) { throw "$backend testleri başarısız." }
}
```

Uygun fiziksel kart varsa CUDA ortamında `preflight --backend cuda --hardware-check`
gerçek Torch backward/ONNX MatMul denetimini de yapar. Kart yoksa bunu geçmiş sayma;
atlanmış fiziksel kontrolü kaydet. Intel XPU CI/lock doğrulaması vardır, fiziksel
Intel GPU kabulü eksiktir. AMD GPU için doğrulanmış Windows ROCm yayın kilidi/kart
profili olmadan paket üretme; CUDA paketine ROCm etiketi koyma.

## 5. FFmpeg ve runtime dağıtım materyali

Doğrulanmış yayın bundle'ı **`build/ffmpeg_material/8.1.1-release`**:
FFmpeg 8.1.1 + libsoxr 0.1.3, tam upstream kaynak/arşiv/hash/lisans/reçeteler,
LGPL-2.1-or-later, yalnız Windows sistem DLL'leri. Eski Gyan full development
binary'sinin `ffmpeg-only` kaynak manifestini `complete` diye değiştirerek geçme.
Kaynak/ikili/etkin kütüphane eşleşmesi gerçekten sağlanmalıdır.

Yeni makinede hazırlama komutları:

```powershell
build/release_cpu/Scripts/python.exe -m tools.release.build_ffmpeg --download
build/release_cpu/Scripts/python.exe -m tools.release.build_ffmpeg --toolchain build/ffmpeg_toolchain/w64devkit
build/release_cpu/Scripts/python.exe -m tools.release.fetch_runtime_material
```

Builder var olan `work` klasörünü silmez; tekrar üretimde ayrı `--output` seç veya
kendi eski çalışma hedefini açıkça doğrula. `fetch_runtime_material` bu projedeki
pinned Python 3.12.15/20261009 full ve install-only arşivlerini kullanır; başka
runtime'a sessiz uyarlamaz. `third_party/runtime` 21 özgün lisans/metadata dosyası
ve kullanılan DLL hash'ini içerir. Lisans byte'ları `.gitattributes` ile korunur.
Ayrıntılar [RELEASE_BUILD.md](docs/RELEASE_BUILD.md) içindedir.

## 6. İki gerçek setup'ı üretme

Önce `version.json` içinde hedef sürümü yerelde belirle. Dağıtılmış 2.0.0'a
güncelleme gönderilecekse daha yüksek sürüm gerekir (örneğin 2.0.1).
Release dosyaları hazır olmadan daha yüksek sürümü `master/version.json` üzerinden
ilan etme. Yeni numara verildiğinde EXE ve installer birlikte yeniden derlenir.

```powershell
$env:GHOSTKILLER_BUILD_PURPOSE = 'release'
$env:GHOSTKILLER_FFMPEG_DIR = (Resolve-Path build/ffmpeg_material/8.1.1-release).Path
$version = (Get-Content version.json -Raw | ConvertFrom-Json).version
foreach ($backend in @('cpu', 'cuda')) {
    $python = "build/release_$backend/Scripts/python.exe"
    $package = "build/release_dist_$backend/Ghostkiller_Sound_Cleaner_V2"
    $env:GHOSTKILLER_BACKEND = $backend
    $env:PYINSTALLER_CONFIG_DIR = Join-Path (Get-Location).Path "build/pyinstaller_cache_$backend"
    & $python -m tools.release.preflight --backend $backend --ffmpeg-dir $env:GHOSTKILLER_FFMPEG_DIR
    if ($LASTEXITCODE -ne 0) { throw "$backend ön kontrol başarısız." }
    & $python -m PyInstaller --noconfirm --clean --distpath "build/release_dist_$backend" --workpath "build/release_work_$backend" Ghostkiller_Sound_Cleaner_V2.spec
    if ($LASTEXITCODE -ne 0) { throw "$backend EXE derlemesi başarısız." }
    $smoke = Join-Path (Get-Location).Path "build/frozen_smoke_$backend.json"
    $process = Start-Process -FilePath "$package/Ghostkiller_Sound_Cleaner_V2.exe" -ArgumentList @('--self-test', ('"'+$smoke+'"')) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Get-Content $smoke -Raw | ConvertFrom-Json).ok) { throw "$backend frozen smoke başarısız." }
    & $python -m tools.release.build_installer --backend $backend --package-dir $package --check-only
    if ($LASTEXITCODE -ne 0) { throw "$backend installer girdileri geçersiz." }
    & $python -m tools.release.build_installer --backend $backend --package-dir $package
    if ($LASTEXITCODE -ne 0) { throw "$backend setup derlemesi başarısız." }
}
```

Inno standart yol dışındaysa `--compiler 'C:\...\ISCC.exe'` ver.
Helper `.iss`'ye doğrulanmış `Backend/PackageDir/AppVersion` parametrelerini
aktarır, taze compiler çıktısını ölçer ve atomik teslim eder. Çıktılar:

| Profil | Setup | Kanıt |
| --- | --- | --- |
| CPU | `Setup/Ghostkiller_V2_Setup_cpu_<sürüm>.exe` | Aynı adlı `.build.json` |
| NVIDIA CUDA | `Setup/Ghostkiller_V2_Setup_cuda_<sürüm>.exe` | Aynı adlı `.build.json` |

İki build-info'da sürüm ve kaynak SHA aynı, backend'ler farklı olmalı.
Zorunlu config/helper/lisans/DLL yoksa veya frozen kaynak eskiyse kapıyı aşma.
Özel modeller ve test sesleri pakette bulunmamalı. Installer tek EXE'dir;
`.bin` sidecar desteklenmez. Legacy **AppId=Ghostkiller Sound Cleaner V2** ve
kurulum dizini korunur; yalnız eski kök ffmpeg/ffprobe EXE'leri temizlenir.
Model/ayar/eğitim dosyalarını yükseltmede/uninstall'da topluca silme.

## 7. Sandbox ve yayın kabul testleri

16 Ekim: yeniden üretilen adaylar için `Setup/acceptance/CPU_2.1.0_Kontrol.wsb`
ve `CUDA_2.1.0_Kontrol.wsb` güncellendi. Bunlar yeni receipt/hash/boyut denetiminden sonra
aynı backend 2.1.0 ilk kurulum → 2.1.0 yeniden kurulum → kaldırma kontrolü
yapar ve okunabilir `SONUC.txt` açar. Sonuçlar `build/windows_sandbox_results_2_1_0_20261016`
altına yazılır. Ağ ve vGPU kapalıdır; CUDA fiziksel kart kabulü değildir.
Gerçek eski üretim sürümü → yeni sürüm otomatik güncelleme ve UAC kabul/iptal
bu yeniden kurulum testinden ayrı kalır. Dosyalar bu görevde başlatılmadı.
`Setup/Yeni_Ozellikleri_Ac.cmd` normal kurulum yapmadan mevcut kaynak/venv ile
uygulamayı açar. Yerel `training_presets.json` içine kaynak yolu içermeyen
“Kısa işleyiş denemesi (3 tekrar)” şablonu eklendi; mevcut şablonlar korunur.

Kullanıcı Sandbox'ı kurdu ve gerçek kabul testini sonra yapacak. Yeni talimat
gelmeden Sandbox veya üretim installer'ını geliştirici hostta başlatma.
`tools/release/windows_sandbox_acceptance.ps1` yalnız disposable VM'de çalışır.
`Setup/acceptance/acceptance.wsb` yerel örnektir; Git'e eklenmez. Yeni build'de
host mapping'lerini ve installer adlarındaki **sürüm numarasını** güncelle.
Acceptance betiğini `Setup/acceptance/` içine kopyala; sonuç mapping'i
`build/windows_sandbox_results` gibi özel test dizinine yönelsin.

VM içinden örnek (yollar Sandbox mapping'lerine göre):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\HostSetup\acceptance\windows_sandbox_acceptance.ps1 -Installer C:\HostSetup\Ghostkiller_V2_Setup_cpu_2.0.0.exe -UpgradeInstaller C:\HostSetup\Ghostkiller_V2_Setup_cpu_2.0.1.exe -OutputDirectory C:\HostResults
```

Bu örnek eski CPU→yeni CPU geçişidir; aynı şekilde CUDA→CUDA ayrıca sınanmalıdır.
Mevcut CPU→CUDA template backend geçişi/sentinel testi yapar; bunu otomatik
güncellemenin aynı backend kabulü diye sunma. vGPU kapalı Sandbox gerçek CUDA
kernel/driver kabulü değildir; uygun fiziksel NVIDIA kart ayrıca gerekir.

Kabul: Python/FFmpeg kurulu olmayan temiz Windows açılışı ve ayrı workers;
model/ayar koruma; UAC **kabul ve iptal**; aynı backend eski→yeni geçiş;
otomatik seçenek açık/kapalı ve elle düğme; sessiz güncelleme sonrası yeniden
açılma; başarısız/yarım indirme ve tekrar deneme; uninstall; klavye/NVDA/JAWS.
Sentinel model dosyası gerçek RVC ağırlığı veya ses kalitesi kanıtı değildir.

## 8. Kullanıcılara güncelleme yayımlama

**GitHub'a kod göndermek kurulu programları güncellemez.** Her geliştirme
commit'inde setup üretmek gerekmez; dağıtacağın yeni sürüm için iki yeni setup,
testler ve sürüme bağlı GitHub Release gerekir. Aynı sürüm numarasıyla değiştirilmiş
EXE yeni güncelleme bildirimi oluşturmaz. Eski tag/asset'i yeniden etiketleme.

### Sürüm notları ve yayın düzeni

Kullanıcıya görünen önemli değişikliklerin tek kaynağı [CHANGELOG.md](CHANGELOG.md)
dosyasıdır. Birbiriyle ilgili geliştirmeleri tek sürümde topla; her küçük fix,
metin düzenlemesi veya CI değişimi için ayrı sürüm/yayın hazırlama. Aynı özellik
üzerindeki tekrarları tek maddeye indir ve kullanıcının göreceği sonucu anlat.
Geçmiş küçük commit'lerden hayali sürüm numarası veya yayın tarihi üretme.

- **Yayın hazırlığında:** henüz dağıtılmayan yenilikleri bu başlıkta biriktir.
- **Gerçek yayın:** kabulden sonra `X.Y.Z — YYYY-AA-GG` başlığıyla tarihi ekle;
  kısa yenilikler, düzeltmeler, gerekiyorsa geçiş bilgisi ve CPU/CUDA bağlantıları.
- **Sürüm numarası:** mevcut davranışı koruyan hata düzeltmesinde patch
  (`2.0.1`), yeni özellikte minor (`2.1.0`), uyumsuz veri/iş akışı geçişinde major
  (`3.0.0`). Bu örnekler yayımlanmış sürüm değildir.

`build/release_notes.md` dosyasını CHANGELOG'un ilgili sürümünden hazırlayıp
GitHub Release'e ver. Ham commit/merge listesini otomatik yayın notu olarak
kopyalama. `version.json` içindeki kısa `changelog` metni de aynı gerçek
yeniliklerin özeti olmalıdır. Teknik kanıtlar `docs/` altında kalır.

### Yayını hazırlama ve duyurma

Yayın sırası:

1. Yeni sürümü **yerelde** belirle; kaynakları/testleri sabitle, iki setup'ı üret.
2. Frozen ve temiz Windows/kullanıcı kabulünü tamamla; source/receipt/hash/size
   ve lisans/ikonları doğrula. İki backend aynı kaynak/sürüme bağlı olsun.
3. Gerçek installer byte'larından yerel güncelleme JSON'unu üret:

```powershell
$version = (Get-Content version.json -Raw | ConvertFrom-Json).version
$date = Get-Date -Format 'yyyy-MM-dd'
build/release_cpu/Scripts/python.exe -m tools.release.make_update_manifest --version $version --package cpu "Setup/Ghostkiller_V2_Setup_cpu_$version.exe" build/release_dist_cpu/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --package cuda "Setup/Ghostkiller_V2_Setup_cuda_$version.exe" build/release_dist_cuda/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --release-date $date --changelog 'Bu sürümdeki gerçek değişiklikleri yazın.' --output "build/version-$version.json"
if ($LASTEXITCODE -ne 0) { throw 'Güncelleme manifesti hazırlanamadı.' }
```

4. Kaynak/sürümü yerelde commit et, aynı commit'ten sabit `v<sürüm>` tag oluştur.
   Daha yüksek sürümü master'da erkenden ilan etmemek için önce **tag'i** gönder:

```powershell
git tag -a "v$version" -m "Ghostkiller Sound Toolbox $version"
git push origin "v$version"
gh release create "v$version" "Setup/Ghostkiller_V2_Setup_cpu_$version.exe" "Setup/Ghostkiller_V2_Setup_cuda_$version.exe" --repo ghostkillerr/ghostkiller_sound_toolbox --verify-tag --draft --title "Ghostkiller Sound Toolbox $version" --notes-file build/release_notes.md
```

`build/release_notes.md` önce hazırlanmalı; CHANGELOG'dan kısa değişiklikleri,
iki profil seçimini ve varsa geçiş/sistem sınırlarını anlatmalı. Installer'lar `Setup/` ignored kaldığı için
`git add -f` ile repoya gönderilmez; **Release asset** olarak yüklenir.

5. Draft'ın iki asset'inin ad/size/hash eşleşmesini doğrula. Release'i yayımla:

```powershell
gh release edit "v$version" --repo ghostkillerr/ghostkiller_sound_toolbox --draft=false
```

6. Sürüme bağlı iki indirme URL'sinin erişilebilir olduğunu ve gerçek byte'ları
   doğrula. **Ancak bundan sonra** `build/version-<sürüm>.json` içeriğini kökteki
   `version.json` dosyasına kopyala, commit et ve master'a gönder.
   Yayın sonrası metadata değişimi tag'deki frozen kaynak kanıtını değiştirmez;
   arşiv receipt'larını elle güncelleme. Sonraki installer için güncel kaynakla
   yeni derleme yapılır.
7. Kurulu eski CPU ve CUDA uygulamalarından açılış/elle güncelleme akışını ve
   Pages indirme bağlantılarını denetle; doğru tag/run/sürümle sonucu kaydet.

Manifest her backend için `download_url`, gerçek `sha256`, `size` içerir.
URL aynı repo ve sabit `releases/download/vX.Y.Z/Asset.exe` yolunda olmalıdır.
`latest`/hashsiz/başka host/sürüm/backend kabul edilmez. JSON hash'lerini,
tarihi, compiler kaydını veya Authenticode imzasını uydurma. `.build.json`
bir Authenticode imzası değildir. Yeni updater kurulum sihirbazını göstermeden
bu doğrulanmış paketi uygular; ayrıca kullanıcıya setup indirtme gerekmez.
Çok eski updater sürümlerinin ilk geçiş davranışı ayrıca gerçek kurulumda sınanır.

## 9. GitHub tanıtım/indirme sayfası

Kaynak: `website/index.html`, `styles.css`, `app.mjs`. Builder yalnız bu dosyaları
ve `logo.ico`, `lisans.txt`, `version.json` dosyalarını `build/site/` içine alır.
Repo kökü, sesler, modeller, runtime arşivleri ve özel ayarlar yayımlanmaz.

```powershell
node --test test/test_site.mjs
python tools/build_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory build/site
```

Yerel adres `http://127.0.0.1:8765/`. GitHub Pages repository ayarında kaynak
**GitHub Actions** olmalıdır. `pages.yml`, master'a website/builder/ikon/lisans/
version/workflow değişimi gönderilince siteyi hazırlar ve yayımlar; elle de
`gh workflow run pages.yml --repo ghostkillerr/ghostkiller_sound_toolbox` çağrılır.
Yayınlanmış URL ve workflow sonucunu doğrulamadan site canlı deme.

CPU/CUDA bağlantıları statik HTML'e elle yazılmaz. Aynı `version.json` hem
uygulama güncelleyicisine hem siteye sürüm URL/hash/size bilgisi sağlar.
Yayımlanmamış/eksik/geçersiz kayıtlarda indirme alanları kapalı kalır;
GitHub yayınları bağlantısı korunur. Bir sürüm yayımlanınca metadata push'ı
sayfayı da günceller. Doküman için site metadata'sına hayali installer ekleme.

## 10. Kanıtlar ve sonraki ajanın raporu

| Kanıt | Kapsam |
| --- | --- |
| [İsteğe bağlı vokal onarımı](docs/VOKAL_ONARIMI.md), [model araştırması](docs/VOKAL_ONARIMI_ARASTIRMASI_2026-10-16.md) | Kaynakta yeni seçenek, görünürlük/NVDA arayüzü, ayrı standart/mono çıktı; CPU ve NVIDIA'da 306'şar test, gerçek CUDA kısa kayıt/iptal kontrolü; eski installer'lar bu eki içermez |
| `build/restoration_checks_20261016/verification.json` | Son kaynak kimliği, test günlükleri, hazır model ve gerçek worker kanıtları; canlı NVDA konuşması, tam kayıt kalite kabulü ve yeni installer derlemesi bekliyor |
| [Güncelleme doğrulaması](docs/GUNCELLEME_DOGRULAMA_2026-10-14.md) | 277'şer kaynak testi, sessiz helper/native fixture ve mevcut setup'ların rebuild gereği |
| [Önceki dağıtım doğrulaması](docs/DAGITIM_DOGRULAMA_2026-10-14.md) | 260'şar test dönemindeki bağımsız frozen CPU/CUDA adayları, FFmpeg/runtime, yerel kurulum; son özellikleri içermez |
| [Dağıtım incelemesi](docs/DAGITIM_INCELEMESI_2026-10-14.md) | Kök codec/sürüm/config/receipt ve ilk diagnostic aşamasındaki bulgular |
| [Ayrıntılı yayın derlemesi](docs/RELEASE_BUILD.md) | Kilitler, toolchain/runtime/source/notices, paket ve güncelleme kapıları |
| `build/auto_update_verification.json`, `auto_update_*_tests.log` | Yerel son kaynak/277 test/fixture ve iki eski paketin güncel gate tarafından reddi |
| `docs/MODEL_EGITIMI.md`, `docs/INFERENCE_RELEASE_FIXES.md`, `docs/TRAINING_RELEASE_FIXES.md` | Eğitim/inference kararları, kalite ve resume sınırları |
| `docs/NATIVE_AUDIO*_CHECK.json`, `docs/TRAINING_FIXED*.json` | Önceki gerçek cihaz/model/sentetik ses testleri; canlı yayın/kalite genellemesi değildir |
| [Önceki ajan rehberi arşivi](docs/AJAN_DEVIR_ARSIVI_2026-10-14.md) | Eski ayrıntılı tarihçe; güncel talimat veya son test sonucu değildir |

GitHub CI'yi **ilgili commit** için oku; önceki 348a44d/run 38469997537 sonucunu
yeni commit'in sonucu gibi sunma. Hosted CUDA/XPU CI, fiziksel ekran kartı kabulü
değildir. En son kullanıcı talimatlarını, canlı HEAD/diff'i ve gerçek artifact
durumunu doğrula. Son raporda: değişiklikler, test ortamı/sonucu, iki setup/site/
release'nin gerçek durumu, korunan veriler ve kalan kullanıcı kabulünü açık yaz.
Kapanmış eski bulguları yeniden eksik sayma; ölçülmemiş kalite/uyumluluğu ilan etme.
