# Ghostkiller Sound Toolbox — Geliştirme, kurulum ve yayın rehberi

Son güncelleme: **15 Ekim 2026**. Bir yapay zekâ ajanı işe başlamadan önce bu
dosyayı okumalı, sonra ilgili kaynakları ve güncel çalışma ağacını incelemelidir.
Kullanıcının sonraki talimatı bu rehberden önceliklidir. Eski raporlar tarihsel
kanıttır; bu rehberdeki güncel durumla karıştırılmamalıdır.

## 1. Proje ve mevcut durum

Ghostkiller Sound Toolbox, Windows x64 / Python 3.12 / wxPython ile geliştirilen
Türkçe masaüstü ses uygulamasıdır. Geliştirici **Yasin Talha Gençsoy**.
Ses dosyalarını yerel işler; internet model indirme ve güncellemeler için kullanılır.

- **Müzik ve Ses Temizleme:** enstrümantal, ana vokal, arka vokal, yankı ve gürültü
  adımları; yerel RoFormer ve UVR modelleriyle PCM24 FLAC çıktıları.
- **Ses Değiştirme:** yerel RVC `.pth` ve isteğe bağlı `.index` ile AI Cover;
  nota/pitch/index seçenekleri ve WAV çıktıları.
- **Model Eğitimi:** RVC V2 kayıt hazırlama, analiz, eğitim, durdur/devam,
  değerlendirme, index ve kalıcı ses modeli kaydı.
- **Ayarlar:** CPU/GPU tercihi, donanım denetimi, model indirme/kontrol/onarım,
  açık/koyu görünüm ve otomatik/elle program güncellemesi.

| Konu | Güncel durum |
| --- | --- |
| Uygulama sürümü | `version.json`: **2.0.0**, `distribution_status: unpublished`, `packages: {}` |
| Dağıtılacak iki profil | **CPU** ve **NVIDIA CUDA**; XPU/ROCm bu iki setup'ın yerine geçmez |
| Derleme ortamları | Bağımsız `build/release_cpu`, `build/release_cuda`; Python **3.12.15**, backend hash kilitleri |
| Inno Setup | Kullanıcı **7.1.0** kurdu; helper 7/6 standart yollarını bulur |
| Kaynak testleri | CPU **293 / OK**, CUDA **293 / OK**; eğitim deneyleri ve mevcut regresyonlar dahil |
| Otomatik güncelleme | Kaynakta uygulandı, varsayılan açık, Ayarlar'dan kapatılır; elle düğme/F5 korunur |
| Eski setup adayları | `Setup/Ghostkiller_V2_Setup_cpu_2.0.0.exe` ve `..._cuda_2.0.0.exe`, otomatik güncelleme değişikliğinden **önce** derlendi; güncel kaynakla rebuild gerekir |
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
