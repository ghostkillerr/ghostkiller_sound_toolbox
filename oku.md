# Ghostkiller Sound Toolbox — Geliştirme, kurulum ve yayın rehberi

Son güncelleme: **17 Ekim 2026**. Kullanıcının sonraki talimatı bu rehberden
önceliklidir. Güncel testler ve kalan işler [Son durum](docs/SON_DURUM.md),
kullanım rehberleri [belgeler dizininde](docs/README.md) tutulur.

Enstrüman ayırma, isteğe bağlı A2SB vokal onarımı, iptal/geçici dosya temizliği
ve model kullanım koşulları kaynakta uygulanmıştır. Enstrüman kanal
düğmelerinin **[AÇIK]/[KAPALI]** okuması kullanıcı tarafından doğrulandı.
Tüm uygulama ve tam kayıt ses kalitesi kabulü bununla tamamlanmış sayılmaz.

Kullanıcı gereksiz dosyaları temizlemeyi ve biriken kaynak değişikliklerini
GitHub'a göndermeyi istedi. Eski raporlar, günlükler, test artıkları ve son
düzeltmeyi içermeyen installer adayları kaldırıldı. Aktif ortamlar, modeller,
kişisel kayıt/ayar/eğitim dosyaları ve son doğrulama özetleri korunur.
Yayın için güncel kaynakla **CPU ve NVIDIA CUDA** kurulumları yeniden
üretilmelidir. Kaynak gönderimi, installer Release yayını değildir.

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
| Uygulama sürümü | Yerel yayın adayı `version.json`: **2.1.0**, `distribution_status: unpublished`, `packages: {}`; paket indirmeleri gerçek Release kabulünden sonra açılır |
| Dağıtılacak iki profil | **CPU** ve **NVIDIA CUDA**; XPU/ROCm bu iki setup'ın yerine geçmez |
| Derleme ortamları | Bağımsız `build/release_cpu`, `build/release_cuda`; Python **3.12.15**, backend hash kilitleri |
| Inno Setup | Kullanıcı **7.1.0** kurdu; helper 7/6 standart yollarını bulur |
| Kaynak testleri | Güncel sonuç ve günlükler [Son durum](docs/SON_DURUM.md) içindedir |
| Otomatik güncelleme | Kaynakta uygulandı, varsayılan açık, Ayarlar'dan kapatılır; elle düğme/F5 korunur |
| Setup adayları | Bugünkü kaynakla eşleşme ve iki installer doğrulaması için [Son durum](docs/SON_DURUM.md); eski raporları güncel kabul etme |
| Yerel setup adayları | Son kaynak düzeltmesini içermeyen dosyalar temizlendi; yayın öncesi iki profil yeniden üretilecek |
| Sandbox | 16 Ekim eski iki adayın ilk kurulum/aynı sürüm yeniden kurulum/kaldırma kontrolü geçti; yeni adayın kabulü ayrıca gerekir |
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

Kullanıcı tek geliştiricidir; ayrı dal/PR yerine doğrudan **master** tercih eder.
İlgili değişiklikleri test edip tek anlamlı commit'te topla. Bu görevde GitHub
gönderimi açıkça istendi. Normal işlerde geçmişi yeniden yazma veya force push
yapma; eski tag/Release asset'lerini değiştirme. Önceki bir defalık geçmiş
düzenlemesi tamamlandı, yeni talimat sayılmaz; kurtarma bundle'ları yerelde korunur.
Kaynak veya site gönderimini installer yayımlama izni olarak yorumlama.

## 3. Veri ve mimari

Kullanıcı teknik konularda adım adım yardım istiyor. Kodu, testleri ve
kurulumları geliştirme tarafı hazırlar; kullanıcı sesleri dinleyerek ve
ekran okuyucuyla deneyerek geri bildirim verir. Kullanıcı programı kullanırken
eşzamanlı UI girişi gönderme.

Gerçek ses denemeleri `deneme/private_model/` altındadır; kişisel ses ve
raporları Git'e ekleme. İlk vokal ayırma sonucu beğenildi. Arka vokal temizliğinde
ana ses kaybı bildirildi; işlem sırasını değiştirmek çözüm olarak kabul edilmedi.
İsteğe bağlı kısa A2SB onarımı standart sonucu ayrı korur; onarılmış çıktı
monodur. Tam şarkı, cover ve eğitim kalitesi sırayla değerlendirilmeli.
Tek şarkı/üç tekrar veya sentetik fixture, kaliteli model kanıtı değildir.

Enstrüman işleme dört/altı ayrı stereo PCM24 FLAC üretir; ses seviyesi
düzenleyen yeniden miksleme ekranı yoktur. Vokal onarımında bir saat sınırı
yoktur; çalışma dizileri için RAM ön kontrolü vardır. Özellik sınırları
[enstrüman](docs/ENSTRUMAN_AYIRMA.md), [onarım](docs/VOKAL_ONARIMI.md) ve
[eğitim](docs/MODEL_EGITIMI.md) rehberlerindedir. A2SB ticari olmayan,
HTDemucs ağırlıkları bilimsel kullanım koşullarıyla sunulur; indirme/kullanım
öncesi açıklama ve kabul gerekir. İsteğe bağlı model ağırlıklarını Git'e veya
installer'a ekleme, üçüncü taraf lisans/NOTICE materyallerini çıkarma.

| Dosya / grup | Görev |
| --- | --- |
| `main.py`, `ui_common.py`, `ui_*.py` | Native dört sekme, tema, klavye/erişilebilirlik, başlangıç ve worker/self-test dispatch |
| `app_runtime.py`, `app_settings.py` | Kaynak/model/veri dizinleri, ortak JOB_LOCK, UI dispatch, atomik ayar tercihleri |
| `audio_service.py`, `audio_worker.py`, `native_process.py` | Kalıcı ayrı audio worker, IPC/heartbeat, Windows Job Object, sınırlı iptal/temizlik |
| `separator_backend.py`, `separation_audio.py`, `separation_steps.py` | Yerel ayrıştırma cihaz/model adaptörü, adımlar, süre/PCM24/sonluluk kontrolleri |
| `instruments/` | Sabit SCNet/HTDemucs modelleri, bloklarla stereo ayırma, atomik ayrı kanal çıktıları |
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

`Setup/Yeni_Ozellikleri_Ac.cmd` kurulum yapmadan mevcut kaynak/venv ile
uygulamayı açar. Eski installer adayları ve onlara ait üretilmiş Sandbox
başlatıcıları temizlendi. Yeni iki paket üretildiğinde sürüm/hash/boyut ve
host mapping'leriyle yeni Sandbox başlatıcıları hazırlanmalıdır.

Kullanıcı Sandbox'ı kurdu; yeni talimat gelmeden Sandbox'ı veya üretim
installer'ını geliştirici hostta başlatma. `tools/release/windows_sandbox_acceptance.ps1`
disposable VM içindir. Yönetici izni istemeyen izole Inno fixture'ları kullanılabilir.
16 Ekim eski Sandbox ve 17 Ekim eski frozen sonuçlarını yeni paket kabulü sayma.

Final kabul: Python/FFmpeg önceden kurulu olmayan temiz Windows açılışı ve ayrı
workers; model/ayar koruma; UAC kabul/iptal; aynı backend eski→yeni yükseltme;
otomatik güncelleme açık/kapalı ve elle denetleme; yarım indirme sonrası tekrar
deneme; kaldırma; klavye ve ekran okuyucu. Sandbox'ta vGPU kapalı test gerçek
NVIDIA GPU kabulü değildir; fiziksel cihaz ayrıca sınanır. Kullanıcının enstrüman
kanalı açık/kapalı kabulünü tüm uygulamaya genelleme.

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

## 10. Kanıtlar ve raporlama

Güncel sonuç [Son durum](docs/SON_DURUM.md) içindedir. Yerel özetler:
`build/training_release_verified.json`, `build/github_sync_20261017/`,
`build/cleanup_fixes_20261017/candidate_verification.json` ve
`build/instrument_accessibility_20261017/verification.json`.
Son paket kanıtı tarihsel adaylara aittir; dosyaları temizlendi, yayın için
yeniden derleme gerekir. Yerel günlük/kanıt/installer ve kişisel veriler Git'e girmez.

`docs/` altındaki eski JSON ölçümleri belirli cihaz/model/sentetik ses
denemeleridir; güncel kaynak veya yayın kabulü olarak sunulmaz.
[RVC](docs/INFERENCE_RELEASE_FIXES.md) ve [eğitim](docs/TRAINING_RELEASE_FIXES.md)
belgeleri motorun teknik sınırlarını saklar.

GitHub CI sonucunu ilgili commit SHA'sıyla doğrula. Hosted CUDA/XPU kontrolleri
fiziksel ekran kartı kabulü değildir. Son raporda kaynak commit'i, testlerin
sonucu, kişisel verilerin korunduğu, setup/site/Release'in gerçek durumu ve
kalan kullanıcı kabulünü açık yaz. Kapanmış bulguları yeniden eksik sayma.
