# Ghostkiller Sound Toolbox — ajan ve geliştirici rehberi

Son kaynak düzenlemesi: **26 Ekim 2026**; son yayımlanan paket: **26 Ekim 2026**. Bu dosya projeye giriş noktasıdır; günlük veya
görev geçmişi değildir. Kullanıcının güncel talimatı burada yazanlardan önceliklidir.

## 1. Proje ve güncel durum

Türkçe, erişilebilir bir Windows masaüstü ses uygulaması. Geliştirici:
**Yasin Talha Gençsoy**. Windows x64, Python 3.12 ve wxPython kullanır.
Sesler yerel işlenir; internet model indirme ve sürüm denetimi içindir.

| Konu | Durum / kaynak |
| --- | --- |
| Uygulama sürümü | `version.json`: **2.1.0**, `published`, CPU ve CUDA hash/boyut/URL kayıtları |
| Dağıtım | [2.1.0 Release](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0): CPU ve NVIDIA CUDA installer'ları 26 Ekim 2026 tarihinde yenilendi; mevcut 2.1.0 için elle kurulum gerekir |
| Kaynak doğrulaması | 26 Ekim yenilemesi: CPU/CUDA ayrı ayrı **472 test**, iki frozen EXE, fiziksel CUDA preflight, CPU/CUDA/XPU kaynak CI ve temiz Windows kurulum kabulü başarılı. Ayrıntı: [Son durum](docs/SON_DURUM.md) |
| Yerel ortamlar | `build/release_cpu`, `build/release_cuda`; bağımsız Python **3.12.15** ortamları |
| Paket desteği | CPU ve NVIDIA CUDA; XPU kaynak/CI profili vardır. Doğrulanmış Windows ROCm yayın kilidi yok |
| Kullanıcı kabulü | Enstrüman düğmelerinin açık/kapalı okunması ve 10 saniyelik otomatik mikrofon ölçümünün çalışması doğrulandı. Son eşik/pencere değişikliği, genel ses kalitesi ve NVDA/JAWS kabulü sürüyor |

GitHub'a kaynak göndermek kurulu programları güncellemez. Test geçmişi, eski
setup veya eski frozen sonuçlar bugünkü kaynak için yayın kabulü sayılmaz.
Durum değişirse önce kod/paket kanıtını kontrol et, ardından bu tabloyu güncelle.

## 2. Kullanıcının gördüğü beş alan

- **Müzik ve Ses Temizleme:** enstrümantal çıkarma ve seçilen vokal temizleme
  adımları; aynı sekmede SCNet dört kanal veya deneysel HTDemucs altı kanal
  enstrüman ayırma. Arka vokal temizliğinde isteğe bağlı A2SB kısa vokal onarımı.
- **Ses Değiştirme (AI Cover):** yerel RVC `.pth` modeli ve isteğe bağlı `.index`
  ile ses dönüşümü; seçilen modeller sırayla çalışır.
- **Model Eğitimi:** kayıt inceleme, bölüm seçme, RVC V2 eğitimi, durdur/devam,
  ara model karşılaştırma, oturumlar, deney sırası ve eğitilen modeli kaydetme.
  Kayıt aralığı ile tutulacak son epoch modeli sayısı kullanıcıdan alınır. Kalıcı
  epoch modelleri adlarına ait temiz klasörde tek ortak index ile saklanır.
  Seçili aday tek başına; epoch modelleri, seçili aday ve notla tercih edilen
  model birlikte kalıcı kaydedilebilir. Oturum varsayılan olarak saklanır;
  Eğitim oturumlarım içinden ayrı onayla teknik dosyalar temizlenebilir; özgün kayıtlar ve kalıcı modeller bu işlemin dışındadır.
- **Canlı AI Cover (4. sekme):** mikrofonu kayıtlı RVC modeliyle dönüştürüp
  seçilen kulaklık/çıkış aygıtından dinleme. 26 Ekim kurulumlarında deneysel olarak bulunur;
  gerçek mikrofon, donanım gecikmesi ve ses kalitesi kabulü sürer.
- **Ayarlar (5. sekme):** donanım kontrolü, CPU/GPU tercihi, model hazırlama/onarım,
  ses dosyası biçimi, kanal düzeni, tema ve güncelleme denetimi.

### Korunacak ürün davranışları

- Ortak çıktı biçimi **MP3/WAV/FLAC/OGG**, varsayılan **FLAC**. Kanal düzeni
  **mevcut düzeni koru/mono/stereo**, varsayılan mevcut düzen. Tercihler kalıcıdır
  ve vokal/enstrüman/cover/eğitim dinleme çıktılarına uygulanır.
- İşlem zincirindeki geçici sesler kayıpsızdır; MP3/OGG çıktısı sonraki temizleme
  adımına girdi yapılmaz. RVC ara WAV'ı float saklanır; kullanıcı WAV/FLAC
  dosyaları 24 bit kaydedilir.
- Canlı dinleme yalnız kullanıcı başlatınca mikrofonu açar; ses kaydetmez,
  otomatik model indirmez. Model ve yardımcılar oturum boyunca tutulur. Giriş/
  çıkış kuyrukları sınırlıdır; yetişemeyen işlemde eski ses atlanır ve bildirilir.
  Canlı dinleme de ortak `JOB_LOCK` kullanır; durdurma aygıtları serbest bırakır.
- Canlı ses eşiği varsayılan -45 dB'dir; dinleme sırasında değişebilir.
  Eşik altındaki tam parçalarda model çağrısı atlanır; ham mikrofon geçirilmez.
  Eşik yüzde değil **dB** değeridir; -80 dB alt sınırı yoktur. **-100** ve
  **-120,5** gibi 0 dB veya altında sonlu sayılar doğrudan yazılabilir. Yazım
  sırasında boş/eksik/geçersiz giriş son geçerli canlı ayarı değiştirmez.
- **Otomatik ayarla (10 saniye sessizlik)** yalnız seçili mikrofonu ölçer;
  model veya çıkış açmaz. Kullanıcı konuşmadan bekler; geri sayım durum alanında
  görünür. Mikrofon ve worker kapandıktan sonra ölçülen gate uygulanır ve
  **Dinleme tamamlandı** penceresinde **Ayarlandı**, ortam seviyesi ve eşikler
  gösterilir. Canlı dinleme ayrıca başlatılır; ölçüm arka planda sürmez.
  İptal/geçersiz ölçüm önceki eşiği korur; ölçüm sesi kaydedilmez.
- Gate 10 ms RMS, 6 dB açılma/kapanma farkı, 5 ms açılma, 150 ms bekleme ve
  120 ms yumuşak kapanma kullanır. Otomatik profil bu açılış için tutulur;
  mikrofon değişince yeniden ölçülür. Çok düşük eşikler sayısal alt-taşma
  yüzünden tam sessizlikte gate'i açmamalıdır.
- Seçilen canlı giriş/çıkışın kimliği ve adı açılışta doğrulanır; başka aygıta
  geçilmez. Gerçek açılan ses yolu arayüzde gösterilir. Canlı oturum günlüğüne
  yalnız **Mikrofon açıldı.** bir kez yazılır; ilerleme durum alanındadır.
  Model hazırlığı ve aygıt açılışı tamamlanınca seçilen çıkıştan kısa bir hazır
  sesi gelir; bu ses mikrofondan dönüştürülen kullanıcı sesi değildir.
- İşlem/model seçimleri ekran okuyucuya basılı düğme olarak değil, gerçek
  işaretli/işaretsiz durumu değişen onay kutuları olarak sunulur. Görsel
  `[AÇIK]` / `[KAPALI]` adı bu durumla eşleşir.
- Ses çıktılarına Ghostkiller eki veya `separation.json` eklenmez. Ad çakışırsa
  `(2)`, `(3)` ile yeni dosya/klasör oluşturulur; önceki sonuç korunur. Sonuç
  mesajı kapatılınca çıktı klasörü açılır.
- Biçim/kanal/donanım kısa özeti klavyeyle odaklanabilir. **Eksik modelleri
  hazırla** düğmesi yalnız seçili işlemin modelleri hazır değilse görünür ve
  yalnız o eksikleri hazırlar. Ses işlemi kendiliğinden model indirmez.
- Model indirmelerinde boyut ve disk alanı kontrol edilir. Sunucu destekliyorsa
  Range ve ETag/Last-Modified ile yarım indirme sürer; değişmiş veya bozuk parça
  kullanılmaz. Kısmi dosyalar `models/.downloads` içindedir.
- Açılışta otomatik güncelleme **denetimi** varsayılan açıktır. Yalnız yeni doğrulanmış sürüm varsa indirme
  onayı çıkar. Geliştirici/paket bilgisi Yardım → Hakkında alanındadır; açılışta
  tekrar eden karşılama penceresi yoktur. **Evet** indirme/kurulumu başlatır; Hayır, hata veya iptal normal
  açılışa döner.
- Kapalı otomatik denetim açılışta ağ isteği yapmaz. Ayarlar/F5 elle denetler ve
  onay ister. Kaynak çalışması kendisini installer ile değiştirmez.

## 3. Kod haritası

| Dosya / dizin | Sorumluluk |
| --- | --- |
| `main.py` | Beş sekme, ortak ayarlar, açılış sırası, tek uygulama örneği, worker dispatch |
| `ui_separator.py`, `separation_steps.py` | Vokal/enstrüman seçimleri, temizleme zinciri ve çıktı adları |
| `ui_cover.py` | Kişisel RVC model listesi ve sıralı dönüşüm |
| `ui_live_cover.py`, `live_cover.py`, `live_audio.py` | Canlı dinleme arayüzü, bellekte RVC akışı ve doğrulanmış Windows ses aygıtları |
| `live_gate.py` | Gate, sınırsız alt eşik girişi, 10 saniyelik gürültü ölçümü ve mikrofonun kapanışı |
| `ui_training.py`, `ui_training_tools.py` | Eğitim, oturum, karşılaştırma ve deney sırası arayüzü |
| `ui_settings.py`, `ui_operation.py` | Tercihler, model hazırlama, koşullu düğme, sonuç klasörü ve hata yönlendirmesi |
| `ui_common.py`, `ui_model_terms.py` | Native tema, erişilebilir kontrol/açıklamalar ve model koşulları |
| `ui_models.py`, `ui_help.py` | Tek RVC ekleme formu, çevrimdışı görev yardımı ve paket kimliği |
| `app_runtime.py`, `app_settings.py`, `registry_store.py` | Dizinler, `JOB_LOCK`, UI dispatch, atomik ayarlar/kayıt kilitleri |
| `source_runtime.py` | Doğrudan kaynak açılışını kayıtlı GPU tercihine uygun hazır yerel ortama yönlendirme |
| `audio_export.py` | Akışla kodlama, kanal dönüşümü, doğrulama ve çakışmasız çıktı yayını |
| `audio_service.py`, `audio_worker.py`, `native_process.py` | Ayrı ses motoru süreci, IPC/heartbeat, Windows Job Object ve iptal |
| `separator_backend.py`, `separation_audio.py` | Yerel ayrıştırma modeli/cihaz adaptörü ve ses bütünlüğü |
| `instruments/`, `restoration/` | SCNet/HTDemucs ayırma ve isteğe bağlı A2SB onarımı |
| `rvc/infer/`, `rvc/lib/`, `rvc/configs/` | RVC dönüşümü, F0/helper cache, model/index kontrolü ve ağlar |
| `training/` | Analiz/dataset, FP32 GAN, checkpoint/resume, değerlendirme/index/model kaydı |
| `training/cleanup.py`, `registry_store.py` | Oturum temizliği/bağımlılık koruması ve UI'dan bağımsız, kilitli model kayıtları |
| `hardware.py`, `compute_backend.py` | Donanım keşfi, gerçek kernel denetimi ve açık cihaz seçimi |
| `model_manager.py`, `model_download.py` | Model kataloğu, bütünlük, atomik onarım ve sürdürülebilir indirme |
| `app_version.py`, `updater.py`, `release_security.py` | Sürüm, denetim ve backend/URL/hash doğrulaması |
| `windows_installer.py`, `update_helper.ps1` | UAC, aynı dizine sessiz güncelleme, yeniden açma ve geçici setup temizliği |
| `.spec`, `Ghostkiller_Kurulum.iss`, `tools/release/` | EXE/installer, kaynak kimliği, lisanslar ve yayın kapıları |
| `requirements/`, `third_party/` | Backend hash kilitleri ve dağıtım/lisans materyali |
| `website/`, `tools/build_site.py`, `.github/workflows/` | Tanıtım sitesi, yalnız kamuya açık dosyaları hazırlama, Pages ve runtime CI |
| `test/`, `docs/` | Regresyonlar, kullanım ve teknik belgeler |

## 4. Veri yolları ve değişiklik sınırları

- Modeller kaynakta ve kurulu EXE yanında `models/` içindedir. Installer bu
  dizine normal kullanıcıya yazma izni verir. `_MEIPASS` paket kaynakları içindir.
- Ayarlar, kişisel model kayıtları, eğitim ve cache; kaynakta proje kökünde,
  kurulu uygulamada `%LOCALAPPDATA%/GhostkillerSoundToolbox` altındadır.
- **Kişisel veri:** `deneme/`, `models/`, `modeller/`, `rvc/models/`,
  `trained_models/`, `training_runs/`, `settings.json`, `models.json`,
  `training_presets.json` ve bunların kilitleri. Silme, yeniden adlandırma,
  üzerine yazma veya Git'e/installer'a ekleme.
- `build/`, `dist/`, `Setup/` türetilmiş yerel çıktılardır; tamamının gereksiz
  olduğunu varsayma. Ortamları, FFmpeg/Python kaynak-lisans materyalini,
  araştırma modellerini ve Git kurtarma bundle'larını koru. Silmeden önce
  mutlak hedefi, içeriği ve workspace içinde kaldığını doğrula.
- `training/vendor/`, `restoration/vendor/`, `instruments/vendor/` ve
  `third_party/` lisans/NOTICE dosyalarını koru. Hash ile izlenen upstream
  byte'larını satır sonu normalleştirmesiyle değiştirme.

### Kodda korunacak sözleşmeler

1. UI kontrol değerleri iş başlangıcında alınır; worker UI getter'ı çağırmaz.
   UI güncellemeleri `post_ui` ile ana thread'e gider. Ortak `JOB_LOCK` eşzamanlı
   ses/eğitim/model/güncelleme işini engeller ve son UI callback'ine kadar tutulur.
2. İşe özel geçici dizinler kullanılır. Sonuç doğrulanmadan yayımlanmaz;
   iptal/çökme önceki sonuçları silmez. NaN/Inf sessizce gizlenmez.
3. Enstrümantal kol özgün girdiden çıkar; seçili vokal adımları zincirlenir.
   Standart ve onarılmış vokal ayrı saklanır. Onarımın ham sonucu monodur;
   kaydedilen kanal düzeni ortak tercihe bağlıdır.
4. Dış model/index için mevcut güvenli yükleme, arşiv/ağ boyutu, hash ve sınırlı
   parser kontrolleri korunur. JSON kayıtları kilit altında read/modify/write ve
   atomik replace kullanır; bozuk kaydı boş dosyayla ezme.
5. Eğitim split'i overlap'tan önce yapılır; index yalnız eğitim feature'larından
   üretilir. Checkpoint tam D+G adımı sonrası optimizer/scheduler/cursor/RNG
   saklar. Backend/GPU düzeni değişikliği aynı resume değildir.
6. RVC hop/F0/helper cache ve varsayılan kalite seçeneklerini sessiz değiştirme.
   Küçük sentetik test veya az epoch, gerçek ses kalitesi kanıtı değildir.
7. A2SB ticari olmayan, HTDemucs ağırlıkları bilimsel kullanım koşullarıyla
   sunulur; indirme/kullanım onayını koru. Yeniden miksleme ekranı ve TTS mevcut
   ürün kapsamında değildir. Canlı mikrofon dönüşümü 26 Ekim 2.1.0 yenilemesinde
   deneyseldir; paket kabulü gerçek ses/gecikme kabulü anlamına gelmez.

## 5. Çalıştırma ve doğrulama

Önce `git status` ve ilgili kod/testleri oku. Hazır CPU/CUDA ortamlarını
kontrol etmeden yeniden kurma. Kaynak açılışı için uygun ortamın
`Scripts/python.exe main.py` komutu veya yerel `Setup/Yeni_Ozellikleri_Ac.cmd`
kullanılır. Kullanıcı programı kullanırken ikinci arayüz açma veya UI girişi gönderme.
Doğrudan `main.py` açılışı da hazır yerel ortamı seçer; kayıtlı GPU tercihi
CPU Python'uyla açılırsa hazır CUDA ortamına yönlendirilir. Worker/self-test
ve frozen uygulama yönlendirilmez. Kişisel ayarlar/ortamlar yeniden yazılmaz.

PowerShell'de test geçici dosyalarını yazılabilir proje dizinine yönlendir;
sandbox'ın varsayılan TEMP yolu izin hatası çıkarabilir:

```powershell
New-Item -ItemType Directory -Force -Path build/agent_temp,build/hf_cache | Out-Null
$env:TEMP = (Resolve-Path build/agent_temp).Path
$env:TMP = $env:TEMP
$env:HF_HOME = (Resolve-Path build/hf_cache).Path
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
foreach ($backend in @('cpu', 'cuda')) {
    & "build/release_$backend/Scripts/python.exe" -m unittest discover -s test -v
    if ($LASTEXITCODE -ne 0) { throw "$backend testleri başarısız." }
}
```

Canlı ses/gate değişikliğinin ilgili regresyonları aynı ortam değişkenleriyle
her iki hazır ortamda şöyle çalıştırılır. Yayın öncesinde yukarıdaki tam matris
de çalıştırılır; güncel tam matris sonucu Son durum belgesindedir:

```powershell
foreach ($backend in @('cpu', 'cuda')) {
    & "build/release_$backend/Scripts/python.exe" -m unittest test.test_live_gate test.test_live_cover test.test_live_cover_ui test.test_audio_service -v
    if ($LASTEXITCODE -ne 0) { throw "$backend canlı ses testleri başarısız." }
}
```

Bağımlılık/derleme değişikliğinde aynı ortamda `pip check` ve
`python -m tools.release.preflight --backend <cpu|cuda>` çalıştır. Fiziksel GPU
kabulünü ayrı `--hardware-check` ile yap; GPU'suz hosted CI sonucu buna eşit değildir.
Temiz ortam ve iki gerçek setup reçetesi [Yayın derlemesinde](docs/RELEASE_BUILD.md).

Site değişikliğinde `node --test test/test_site.mjs` ve
`python -m tools.build_site` çalıştır. Çıktı yalnız `build/site` içinde olmalıdır.
Göndermeden önce stage edilmiş ağaçta `python tools/check_public_tree.py` ve
`git diff --cached --check` çalıştır. Kişisel yollar/ayarlar/raporlar gönderilmez.

## 6. Git, setup ve güncelleme yayını

26 Ekim yenilemesinde kullanıcının açık talimatı: **sürümü değiştirme**.
Uygulama 2.1.0 kalır; paket tarihi, kaynak etiketi ve hash ile ayrılır.
Aynı sürüm için otomatik güncelleme teklifi yoktur; elle kurulum açıklanır.
Yeni CPU/CUDA paketleri önce ayrı tarihli aday yayında sınanır; mevcut
kurulumlar kabulden sonra yedeklenerek yenileriyle değiştirilir.

- Kullanıcı doğrudan **master** üzerinde çalışmayı tercih eder. GitHub'a
  gönderme/yayımlama yetkisini güncel kullanıcı isteğinden al; eski görev
  anlatımını devam eden izin sayma. Force push veya geçmişi yeniden yazma.
- **“Setupları yap”**, aksi belirtilmedikçe **CPU ve NVIDIA CUDA için iki gerçek
  installer üretmek** demektir. Check-only veya diagnostic build teslim değildir.
- `version.json` uygulama ve setup sürümünün kaynağıdır. Hedef sürümü **önce
  yerelde** belirle, aynı kaynak/sürümden iki paketi üret. `.build.json` receipt,
  source SHA, backend, hash/boyut, frozen ve temiz Windows kabulü eşleşmelidir.
- İkon, `lisans.txt`, üçüncü taraf lisansları, eşleşen Python runtime materyali,
  FFmpeg tam kaynak/lisans/reçeteleri, config'ler ve update helper zorunludur.
  Yerel aktif FFmpeg bundle'ı `build/ffmpeg_material/8.1.1-release` içindedir.
- Kaynak push'u, setup üretimi ve Release yayını ayrı işlemlerdir. Hazır olmayan
  installer için yayın tarihi/hash/link uydurma; daha yüksek sürümü erken duyurma.
- Yayın sırası: yerel sürüm → iki gerçek setup ve receipt → yerel frozen kabulü
  → sabit tag ile test edildiği açıkça belirtilen GitHub ön sürümü → salt okunur
  Windows kurulum kabulü → manifest ve normal Release → dosyalar doğrulandıktan
  sonra `master/version.json` ve site duyurusu. Ön sürüm güncelleme diye duyurulmaz.
- Tag paketlenen kaynak anını, master'daki manifest sonraki yayın duyurusunu
  gösterir. Duyuru `version.json`'u değiştirdiği için eski paketin kaynak
  kimliğini incelerken kendi yayın tag'iyle karşılaştır; master ile farklılık
  tek başına yeni bir uygulama düzeltmesi değildir.
- Setup'lar Git ağacına zorla eklenmez; Release asset olarak yüklenir. Legacy
  `AppId` ve kurulum dizini korunur. Güncelleme aynı backend'i seçer, UAC'yi
  atlatmaz; helper sonucu doğrulayıp yeniden açar ve kendi geçici setup'ını temizler.
- Kullanıcı ayrıca istemeden üretim installer'ını veya Windows Sandbox'ı
  geliştirici bilgisayarında başlatma. Kabul araçları disposable VM içindir.

## 7. Sıradaki iş ve belge seçimi

**26 Ekim 2.1.0 CPU/CUDA yenilemesi tamamlandı.** Kullanılabilirlik
incelemesindeki 15 bulgunun düzeltmeleri paketlendi; GitHub ve sunucudaki
Ghostkiller sayfası yenilendi. Kaynak, frozen ve Windows kurulum kanıtları
Son durum belgesindedir. Gerçek sesle uzun işlem/eğitim, NVDA/JAWS,
%125/%150 ölçeklerde görsel kontrol ve etkileşimli UAC/güncelleme kabulü sürer.
Kullanıcıdan kod/hash/derleme komutu beklenmez; ses ve kullanım geri bildirimi alınır.

Kaynaktaki canlı AI Cover geliştirmesinde otomatik 10 saniyelik ölçüm kullanıcı
tarafından çalışır bulundu. Alt sınırı kaldırılmış eşik girişi ve sonuç
penceresinin son kullanıcı kabulü; gerçek modelle ses kalitesi, Line 2'de
akustik dinleme/gecikme ve ekran okuyucu anonsları hâlâ doğrulanmalıdır.
26 Ekim yenilemesinin paketlenen kaynağı `v2.1.0-source-20261026`
etiketindedir; eski `v2.1.0` etiketi ilk yayını gösterir ve taşınmamıştır.
Sürüm numarası aynı kaldığı için bu yenileme mevcut 2.1.0 kurulumlarına
otomatik teklif edilmez; aynı backend paketi elle kurulmalıdır.

- Güncel kanıt ve açık işler: [SON_DURUM.md](docs/SON_DURUM.md)
- Kullanıcı denemeleri: [KULLANICI_KABULU.md](docs/KULLANICI_KABULU.md)
- Deneysel canlı dinleme: [CANLI_AI_COVER.md](docs/CANLI_AI_COVER.md)
- Derleme ve yayın ayrıntıları: [RELEASE_BUILD.md](docs/RELEASE_BUILD.md)
- Kullanıcıya sunulacak sürüm notları: [CHANGELOG.md](CHANGELOG.md)
- Kullanım ve teknik konu dizini: [docs/README.md](docs/README.md)

Bu rehberi değiştirirken geçmiş temizlik sayıları, silinmiş rapor yolları,
yerel kişisel model adları ve tek kullanımlık görev talimatları ekleme.
