# Native Windows yayın derlemesi

CPU ve NVIDIA CUDA ayrı, hash kilitli ortamlardan üretilir. Bu belge derleme
reçetesidir; güncel test/paket durumu [Son durum](SON_DURUM.md), kullanıcı
talimatları ve yayın sırası [oku.md](../oku.md) içindedir. Önceki installer
adayları son kaynak düzeltmesini içermediği için temizlendi; yeniden derleme gerekir.

## Çalışma ortamları ve kilitler

Windows x64 / CPython 3.12 için `requirements/cpu.lock`, `cuda.lock` ve
`xpu.lock` bütün doğrudan/geçişli bağımlılıkları sürüm ve SHA-256 ile sabitler.
CPU: PyTorch 2.11.0+cpu, ORT 1.29.0. NVIDIA: PyTorch 2.11.0+cu128,
ORT GPU 1.26.0. Intel: PyTorch 2.11.0+xpu ve aynı wheel metadata'sındaki
oneAPI runtime sürümleri; ONNX modelleri için bu profilde CPU ORT bulunur.
Intel GPU'da ONNX hızlandırması bu profilin iddiası değildir.

Her backend ayrı ve temiz venv kullanır. CPU/GPU/DirectML ORT dağıtımları aynı
modülü sağladığından birlikte kurulamaz. `preflight` bunu `pip check`ten ayrı
kontrol eder, kilit dışı paketleri ve yanlış PyTorch backend'ini reddeder.
AMD ROCm için doğrulanmış native Windows lock henüz sağlanmadı; mevcut CUDA
kilidini AMD paketi diye adlandırmak kabul edilmez. ROCm release derlemesi bu
kilit ve gerçek kart/runtime doğrulaması olmadan kapalıdır.

```powershell
build/release_python/cpython-3.12.15-windows-x86_64-none/python.exe -m venv build/release_cpu
build/release_cpu/Scripts/python.exe -m pip install --no-deps --require-hashes -r requirements/bootstrap.lock
build/release_cpu/Scripts/python.exe -m pip install --require-hashes --no-build-isolation -r requirements/cpu.lock
build/release_cpu/Scripts/python.exe -m pip check
build/release_cpu/Scripts/python.exe -m tools.release.preflight --backend cpu --hardware-check
```

Kilitler temiz CPU venv'inde gerçekten kuruldu; `pip check`, PyTorch
forward/backward ve gerçek küçük ONNX MatMul oturumu geçti. Aynı komutların
CUDA/XPU profillerinde fiziksel GPU testleriyle geçmesi ayrıca gerekir.
`.github/workflows/native-validation.yml` üç temiz ortamı kurar; hosted
runner'da CUDA/XPU adımı gerçek GPU kullanımı iddia etmez. Bu makinedeki iki
ortam Python 3.12.15 kullanır; Python 3.12.0 frozen build için reddedilir.
Yeni yayınlarda desteklenen güvenlik patch'i ve eşleşen runtime materyali
birlikte seçilmelidir.

14 Ekim gerçek frozen test, Python 3.12.0 ile SciPy'de `NameError: obj`
üretti. Aynı durum küçük `code.replace()`/comprehension örneğinde de
yeniden üretildi; [CPython düzeltmesi](https://github.com/python/cpython/pull/111866)
ve [PyInstaller kaydı](https://github.com/pyinstaller/pyinstaller/issues/7992)
kök nedeni açıklar. Kaynak testinin geçmesi bu frozen hatayı yakalamıyordu.
Build/preflight ve installer input artık 3.12.0'ı reddeder; minimum
3.12.1, yayın için güncel güvenlik patch'i gerekir.

Proje `build/release_python` dizininde uv ile Python **3.12.15** hazırlandı;
Windows kayıt defteri/PATH/global Python değiştirilmedi. Bu çalışma zamanı
Python.org Windows installer'ı değil, Astral python-build-standalone
**20261009** build'idir. Resmi uv metadata'sının immutable commit'i
`b757f15552203f42d8081b2378955e725cd732ce`; indirilen runtime arşivinin
SHA-256'sı `11ed9f8a6ac64fb1b5a55e40e305a6744a3f77a70863c8f8197a6e4349abc64a`.
Metadata/URL/hash kaydı `build/dagitim_python_provenance.json` içindedir.
[uv runtime açıklaması](https://docs.astral.sh/uv/guides/install-python/).

Yerel bağımsız Python **3.12.15** ortamları `build/release_cpu/Scripts/python.exe`
ve `build/release_cuda/Scripts/python.exe` olarak bulunur. Yeni makinede
hash-locked kurulum reçetesini kullanın. Başka ortamın site-packages'ini `.pth`
ile paylaşan diagnostic ortam yayın derlemesi sayılmaz.

`tools.release.generate_locks` sadece resmi PyPI/PyTorch metadata'sını okur.
Sürüm güncellemesi `requirements/versions.json` ve ilgili profil değişikliği
olarak incelenir. Bazı XPU index kayıtlarında SHA-256 bulunmadığı için
bu wheel'in resmi HTTPS akışı kurmadan/diske kaydetmeden hash'lenmiştir.
Kilit üretimi bağımlılık kurmaz. Kaynak/sdist yeniden derlemesi bit düzeyinde
aynı binary garantisi vermez; yayın kullanılan wheel'leri arşivlemelidir.

14 Ekim kalan sorunlar çalışmasında `build/release_cpu` ve `build/release_cuda`
Python 3.12.15 ile **ayrı ve bağımsız** kuruldu. İkisi de bootstrap/backend
SHA-256 kilitleriyle sıfırdan kurulum, pip check ve hardware-check preflight'tan
geçti; CUDA gerçek NVIDIA kartta Torch backward ve ONNX CUDA MatMul çalıştırdı.
Güncel kaynak testlerinin sayısı [Son durum](SON_DURUM.md) içindedir.
Geçici .pth ortamı yayın ortamı olarak kullanılmaz.

## FFmpeg, lisanslar ve kaynaklar

Aktif yayın bundle'ı `build/ffmpeg_material/8.1.1-release` altında kaynaklardan
derlendi. FFmpeg 8.1.1 ve libsoxr 0.1.3 tam commit/arşiv/hash ile sabitlendi;
taşınabilir w64devkit 2.10.1 resmi asset SHA-256'sıyla doğrulandı. Geliştirici
makinesinin native işlemci bayrakları kullanılmadı. `--disable-autodetect`,
GPL/nonfree/version3 kapalı, libsoxr açık; yalnız Windows sistem DLL'lerine
bağlanır. Lisans LGPL-2.1-or-later'dır. ffmpeg/ffprobe configure/version, bütün
özgün kaynak byte'ları, lisanslar ve reçete manifestte doğrulanır. Etkin her
harici kütüphane `source_components` içinde kaynak arşivine bağlanır; yalnız
`source_completeness: complete` yazmak artık kapıyı açmaz.

```powershell
# Resmi portable toolchain'i build/ffmpeg_toolchain içine SHA ile doğrulayarak çıkarın.
build/release_cpu/Scripts/python.exe -m tools.release.build_ffmpeg --download
build/release_cpu/Scripts/python.exe -m tools.release.build_ffmpeg --toolchain build/ffmpeg_toolchain/w64devkit
$env:GHOSTKILLER_FFMPEG_DIR=(Resolve-Path build/ffmpeg_material/8.1.1-release).Path
```

Builder var olan `work` klasörünü silmez; yeniden üretim için temiz bir
`--output` seçin. Kaynak tarball'ı üstteki proje Git revizyonunu FFmpeg sürümü
sanmasın diye upstream RELEASE/make REVISION sabitlenir. Build reçetesi ve
orijinal kaynak arşivleri kurulumda `third_party/ffmpeg` içinde yer alır.
WAV/FLAC/MP3/AAC/OGG okuma, precision=28 libsoxr resampling ve PCM24 FLAC
testleri geçti; önceki codec ile fark en fazla yaklaşık 2.84e-7 idi.

`tools.release.fetch_runtime_material` seçilmiş CPython 3.12.15/20261009
build'inin SHA doğrulanmış full ve install-only-stripped arşivlerini kullanır.
Kurulu python312.dll byte hash'i install-only arşiviyle eşleşir; full build'den
21 özgün lisans/metadata dosyası `third_party/runtime` altında korunur. CPU/CUDA
paketleri bu lisansları, kaynak provenance'ını ve Python DLL hash'ini içerir;
başka runtime/patch için materyal yeniden hazırlanmalıdır. Üç Microsoft CRT
DLL'si ve runtime lisans/provenance manifesti installer'da zorunludur.

### Dağıtım için kaynak eşleşmesi

Yayın girdisi kaynaklardan üretilen `8.1.1-release` bundle'ıdır. Eski Gyan full
build'in yalnız FFmpeg kaynağını içeren `ffmpeg-only` manifesti bütün bağlı
kütüphanelerin kaynaklarını karşıladığı anlamına gelmez. Böyle bir kaydı
`complete` diye etiketleyerek yayın kapısını geçmeyin. İkili, etkin kütüphaneler,
tam kaynaklar, lisans ve reçete eşleşmelidir.
[FFmpeg dağıtım rehberi](https://www.ffmpeg.org/legal.html).

Yayın amaçlı spec otomatik olarak şunları ister:

- `ffmpeg.exe`, `ffprobe.exe` ve varsa gerekli DLL'lerin exact SHA-256'ları.
- `manifest.json`: version, configure, gerçek lisans kimliği,
  `source_completeness: complete`; boş olmayan licenses/sources/build_recipes
  dosya listeleri, her dosya için yerel yol ve SHA-256.
- Paket kökü içinde kalan dosyalar; path traversal, eksik kaynak veya hash
  uyuşmazlığı kabul edilmez. `--enable-nonfree` reddedilir, libsoxr zorunludur.
- Bütün sabitlenmiş Python bileşenlerinin lisansları. Wheel'de eksik olan
  Cython, samplerate/libsamplerate, tokenizers ve flatbuffers metinleri tam
  upstream tag ve hash manifestiyle `third_party/python` altında saklanır.

Kullanıcı EULA'sı bu bileşenlerin kendi lisans haklarını kısıtlamaz.
PyInstaller kaynaklar/notices/lisansları toplar; Inno Setup onları EXE
ağacıyla birlikte kurar. Installer FFmpeg'in yalnız iki EXE'sini alıp
lisansları dışarıda bırakmaz.

## EXE derlemesi ve paket kontrolü

```powershell
$env:GHOSTKILLER_BUILD_PURPOSE='release'
$env:GHOSTKILLER_FFMPEG_DIR=(Resolve-Path build/ffmpeg_material/8.1.1-release).Path
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

Önce [oku.md](../oku.md) içindeki TEMP/cache ortamını hazırlayın. İki bağımsız
venv, eşleşen dağıtım materyali ve Inno Setup 7/6 bulunmalıdır. Standart yollar
dışındaki compiler için `build_installer` komutlarına `--compiler` ekleyin.

Spec, ortak çıktı kodlayıcısını (`audio_export`), model indirmeyi
(`model_download`) ve işlem arayüzünü (`ui_operation`) açıkça toplar. Ortak
biçim/kanal tercihleri ve güncelleme akışı mevcut Python kaynaklarıyla paketlenir.
`--self-test`, gerçek kodlayıcılarla dört biçim × üç kanal tercihi × iki girdi
kanal düzeni için **24 dönüşümü**, kayıpsız hassasiyeti ve çakışmada eski çıktının
korunmasını sınar. Başarısız bir biçim paketin smoke sonucunu başarısız yapar;
deneme sesleri başarıda ve hatada temizlenir. Yeni kaynak eklemek eski setup'ı
değiştirmez; kaynak kimliği eski EXE ile installer oluşturulmasını reddeder.

`GHOSTKILLER_BACKEND` zorunludur. EXE'de `build-info.json` gerçek backend,
uygulama sürümü, Python/PyTorch, lock hash'leri ve FFmpeg bilgilerini taşır. XPU derlemesi
oneAPI wheel'lerinin native DLL/resource düzenini ve erken DLL search path
hook'unu içerir. UPX kapalıdır. Kullanıcı modelleri, sesleri, model kayıtları,
ayarlar ve eğitim oturumları paket kontrolünde reddedilir. CREPE/FCPE'nin
wheel ile gelen sabit yardımcı ağırlıkları ve audio-separator'un mixer
checkpoint/catalog kaydı açık izin listesindedir.

Inno Setup normal kullanıcıdan yönetici kurulumu için UAC ister. Ürün adı
Sound Toolbox'dır; önceki installer'ın AppId ve hedef dizini korunmuştur,
böylece yükseltme mevcut `models` dizinini kullanır. Backend installer adı
`Ghostkiller_V2_Setup_<cpu|cuda>_<sürüm>.exe` olur. Yukarıdaki akış her backend'i
kendi hash-locked venv'inde üretir; iki gerçek installer ve aynı adlı `.build.json`
teslim edilir.
CPU ve CUDA derlemelerinin dist klasörlerini birbirine karıştırmayın: her
backend'in doğrulanmış EXE ağacını ayrı yerde saklayıp `--package-dir` ile verin.

Installer helper eski uygulama kaynaklarını, yanlış backend'i, diagnostic
artifact'i, eski dependency lock'larını, eksik Python/FFmpeg/RVC/eğitim config'lerini,
kişisel verileri ve eksik/değiştirilmiş FFmpeg kaynak materyalini reddeder.
Kaynak kimliği `build-info.json/application_source_sha256` içindedir; uygulama
kaynakları veya spec değişirse EXE yeniden üretilir. Sürüm paketli version.json'dan
alınır; .iss'ye elle eski sürüm yazılmaz. `.iss` doğrudan kontrolsüz varsayılan
dist klasörü kullanmaz; helper'ın doğruladığı PackageDir/AppVersion parametreleri
gerekir. Setup modern native wizard kullanır, masaüstü kısayolu seçilebilir,
çift kurulum SetupMutex ile engellenir. Uygulamayı otomatik yeniden başlatmaz.
Eski AppId/kurulum hedefi ve app/models yazma izni korunur.

Frozen testte RVC'nin `@torch.jit.script` fonksiyonu için source access
hatası da bulundu. Spec `rvc` ve `training` modüllerini **pyz+py** olarak
toplar; TorchScript gerçek `.py` dosyalarını okuyabilir. Decorator/eğitim
matematiği kaldırılmadı veya değiştirilmedi. Installer input, kritik
`commons.py`/`synthesizers.py` kaynaklarının bulunmasını ve kaynak repo
SHA-256'larıyla eşleşmesini ister. Kaynak dosyaları eklenen önceki diagnostic
paketle repair probe 25.0 saniyede geçti; bu ara deneme yeni spec'ten fresh
build kabulünün yerine geçmez.
[PyInstaller source collection açıklaması](https://pyinstaller.org/en/stable/hooks.html).

`app_version.py` runtime'da paketli `version.json` dosyasını okur; ayrı elle
güncellenen CURRENT_VERSION sabiti yoktur. Build-info/application_version,
paketli version.json ve kaynak sürümü eşleşmeden installer oluşturulmaz.
Helper compiler'ı özel geçici çıktı dizininde çalıştırır; eski Setup dosyasını
yeni derleme diye kabul etmez. Başarılı çıktının yanında `.build.json` kaydı
bulunur: uygulama sürümü/backend/kaynak kimliği, build-info SHA-256,
installer SHA-256/boyut ve .iss SHA-256. Güncelleme manifesti bu kaydı
installer byte'ları ve verilen build-info ile karşılaştırır.

Frozen FFmpeg/FFprobe yolları `_internal` içinden mutlak olarak seçilir.
Pydub ve separator'un sürüm kontrolü de bu ikilileri kullanır. Eğitim decode
ve analiz bare `ffmpeg`/`ffprobe` komutuna dayanmaz. `[InstallDelete]` eski
installer'ın yalnız `{app}/ffmpeg.exe` ve `ffprobe.exe` dosyalarını temizler;
modeller/kayıtlar için toplu silme eklenmedi.

`third_party/python` dosyalarının manifest SHA-256'ları exact byte'lara
aittir. `.gitattributes` bu dizinde Windows CRLF dönüşümünü kapatır. Yerelde
LF'ye dönünce zaten kayıtlı hash'lerle birebir eşleşen altı lisans dosyası
orijinal byte biçimine getirildi; hash kontrolü gevşetilmedi.

14 Ekim ilk hazırlık doğrulamasında 240 regresyon testi geçmişti; eski
diagnostic_cpu klasörü installer helper tarafından beklendiği gibi reddedildi.
Sonraki düzeltmede Inno Setup **7.1.0** kullanıcı tarafından kuruldu ve
standart yolda bulundu. Güncel .iss CPU/CUDA parametreleri ve sentetik paket
fixture'ı ile gerçek ISCC'de **Output=no** kullanılarak iki kez başarıyla
derlendi. Bu kontrol installer dosyası üretmez veya kurulum yapmaz.
O ilk aşamada FFmpeg full build'in `source_completeness: ffmpeg-only` engeli
ve temiz CUDA ortamı eksikti. Kalan sorunlar çalışması bunları yeni tam
kaynaklı LGPL bundle ve bağımsız CPU/CUDA ortamlarıyla kapattı. Eski Gyan
manifestini complete diye değiştirerek geçmeyin. Güncel EXE'ler
`build/release_dist_cpu` ve `build/release_dist_cuda` altında ayrı tutulur.

Kaynak materyali eksikken **yalnız yerel inceleme için**
`GHOSTKILLER_BUILD_PURPOSE=diagnostic` ve recovered FFmpeg dizini seçilebilir.
Bu artifact `Ghostkiller_Sound_Toolbox_Diagnostic_cpu` adıyla ayrı üretilir,
`build-info.json` içinde `release_eligible=false` taşır. Güncelleme manifest
üreticisi bu artifact'i kesin olarak reddeder; bu mod üretim kapısını açmaz.

## Güncelleme manifesti

EXE ve installer kaynak `version.json` sürümünü kullanır. Yayımlanmış bir
sürüme güncelleme göndermek için daha yüksek sürüm numarası belirlenip
**EXE ve installer yeniden derlenmelidir**; eski aday dosyasını yeniden
adlandırmak veya metadata ile etiketlemek kabul edilmez.
Yerel manifest gerçek iki adayın hash/receipt kontrolünden üretilir;
paketler yayımlanmadan kök version.json/packages alanına kopyalanmaz.

Eski `releases/latest`/hashsiz metadata'dan EXE kurulmaz. Uygulama yayın
sayfasını açıklayan güvenli bir mesaj gösterir. Yeni şema her backend için
`download_url`, `sha256`, `size` ister; URL aynı repo ve bildirilen sürümün
`releases/download/vX.Y.Z/Asset.exe` yolunda olmalıdır. GitHub'ın resmi
release-assets yönlendirmesi kabul edilir; başka host reddedilir. İndirme
boyutu/hash kontrol edilir, son doğrulama GUI thread dışında tekrar yapılır.
Varsayılan açık `auto_update` tercihi AppSettings'te saklanır. Kurulu uygulama
açılışta geliştirici bilgi penceresinden önce denetler ve yalnız yeni sürüm varsa
indirme onayı ister. **Evet** sonrasında indirip uygular; **Hayır**, ağ hatası
veya yeni sürüm bulunmaması normal açılışa devam ettirir. İndirme/kurulum devri
sırasında geliştirici penceresi açılmaz; iptal veya devir hatasında açılış sürer.
Ayarlar'dan kapatılırsa açılışta ağ kontrolü yapılmaz. Ayarlar düğmesi ve F5,
tercihten bağımsız elle denetler ve indirme onayı ister.
Kaynak geliştirme çalışması otomatik güncelleme uygulamaz. Ses/model/donanım işi
varsa açılış güncellemesi işi kesmeden bekler; beklerken kapatılan tercih korunur.

`update_helper.ps1` paketlenmesi ve kaynak SHA eşleşmesi installer gate'inde
zorunludur. Yardımcı, özel indirme dizinine kopyalanıp mevcut kullanıcının
yetkisiyle gizli PowerShell sürecinde çalışır; yalnız doğrulanmış Inno EXE'sini
`Start-Process -Verb RunAs` ile yükseltir. Boyut/header/SHA yeniden doğrulanır ve
salt okuma paylaşım kilidi installer bitene kadar tutulur. `/VERYSILENT`,
`/SUPPRESSMSGBOXES`, `/SP-`, `/NORESTART`, mevcut `/DIR` ve `/GKUPDATEPID`
parametreleriyle sihirbaz açılmaz. Inno `PrepareToInstall` eski süreç kapanmadan
dosyaları değiştirmez ve uygulamaları zorla kapatmaz. UAC iptalinde uygulama açık
kalır; kabul edilince wx çıkar, yardımcı installer sonucunu bekler, kurulan
sürüm/backend'i kontrol eder ve uygulamayı kendi kullanıcı yetkisiyle yeniden
açar. Program Files yazımı nedeniyle UAC gerekebilir; Windows onayı atlatılmaz.
Normal ilk kurulumda sözleşme ve ikonlar korunur.
Sistem PowerShell'ine geçerken özel DLL arama yolu geçici olarak sıfırlanır;
eski süreçte geri yüklenir. Yeniden açılan frozen uygulama eski bootloader
ortamını kullanmasın diye yardımcıya `PYINSTALLER_RESET_ENVIRONMENT=1` verilir.
[PyInstaller yeniden başlatma davranışı](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#using-sys-executable-to-spawn-subprocesses-that-outlive-the-application-process-implementing-application-restart).

Sonuç `%LOCALAPPDATA%/GhostkillerSoundToolbox/update-result.json`, Inno günlüğü
`update-logs/` altında saklanır; Ayarlar son sonucu gösterir. Aynı başarısız sürüm
açılışta tekrar uygulanıp yeniden başlatma döngüsü yaratmaz; elle yeniden
denetlenebilir. Windows yeniden başlatma gerektiren 3010 sonucu kullanıcıya
bildirilir ve program yeniden açılmaz. Başarılı/başlamış güncelleme yardımcıları
yalnız kendilerine ait geçici dosyaları temizler; modeller ve ayarlar silinmez.
[Inno komut satırı davranışı](https://jrsoftware.org/ishelp/topic_setupcmdline.htm).

```powershell
$version = (Get-Content version.json -Raw | ConvertFrom-Json).version
$date = Get-Date -Format 'yyyy-MM-dd'
build/release_cpu/Scripts/python.exe -m tools.release.make_update_manifest --version $version --package cpu "Setup/Ghostkiller_V2_Setup_cpu_$version.exe" build/release_dist_cpu/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --package cuda "Setup/Ghostkiller_V2_Setup_cuda_$version.exe" build/release_dist_cuda/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --release-date $date --changelog 'CHANGELOG.md ile eşleşen gerçek sürüm özeti' --output "build/version-$version.json"
```

Komut gerçek installer bytes'ından hash üretir, diagnostic veya derleme
kaydıyla uyuşmayan paket kabul etmez ve yalnız yerel JSON yazar. Yayımlama
yetkisi/işlemi içermez.
Yanında helper'ın ürettiği aynı adlı `.build.json` olmadan veya uygulama
sürümü/build-info/installer byte'ları bu kayıtla eşleşmeden manifest üretilmez.
Bu yerel derleme kaydı Authenticode yayıncı imzası değildir.
`version.json` 2.1.0 ve unpublished olarak kalır; gerçek yeni kurulum
hazır olmadığı için hash veya yayın tarihi uydurulmaz. SHA-256 trusted GitHub
manifest/HTTPS kaynağına dayanır; publisher Authenticode imzası ve yayıncı
sertifikası ayrıca alınmalı/doğrulanmalıdır.

Son kabul: temiz Windows normal kullanıcıda Python/FFmpeg kurulu olmadan
başlangıç, worker dispatch, sentetik ayrıştırma/cover/eğitim durdur-devam,
Program Files izinleri, UAC iptal/başarı, NVDA/JAWS ve fiziksel donanım matrisi.
Yerel diagnostic EXE testi temiz VM veya fiziksel AMD/Intel GPU testi değildir.

## Kaynak geliştirme tanısı

```powershell
build/release_cpu/Scripts/python.exe main.py --self-test build/source_native_smoke.json
```

Bu kaynak komutu EXE üretmez veya kurulum yapmaz. Model indirmeden gizli
native wx kontrollerini, CPU forward/backward, gerçek ORT CPU oturumunu,
Unicode ses adıyla FFmpeg/FFprobe ve MP3/WAV/FLAC/OGG kanal dönüşümlerini,
ayrı ses/eğitim worker süreçlerini sınar. Kaynak denemesi frozen EXE, UAC veya temiz Windows kabulü
yerine geçmez. Güncel sonuçlar [Son durum](SON_DURUM.md) içindedir.
