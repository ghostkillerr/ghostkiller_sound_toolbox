# Native Windows yayın derlemesi

14 Ekim 2026. Kullanıcı kurulum hazırlığını yeniden açtı; **CPU ve NVIDIA CUDA
için ayrı paketler** istiyor. Bu talimat önceki EXE çalışmasını durdurma kararının
yerine geçer. CPU/CUDA setup adayları Inno Setup 7.1.0 ile üretildi; ayrı
temiz ortamların her birinde 260 test ve gerçek frozen/yerel kurulum testleri
geçti. [Önceki doğrulama raporu](DAGITIM_DOGRULAMA_2026-10-14.md) o adayların
çıktı/hash/kabul sınırlarını gösterir. Daha sonra Ayarlar'dan yönetilen otomatik
sessiz güncelleme eklendi; [277 testlik kaynak doğrulaması](GUNCELLEME_DOGRULAMA_2026-10-14.md)
bu değişikliği kapsar. Eski iki setup bu özelliği içermez; güncel kaynakla
yeniden üretilmelidir. Temiz Windows/UAC/uninstall kabulü kullanıcı tarafından
sonra yapılacak. Güncel iki-setup ve yayın sırası [oku.md](../oku.md) içindedir.

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
runner'da CUDA/XPU adımı gerçek GPU kullanımı iddia etmez. Kaynak ortamının
Python'u 3.12.0'dır; bu sürüm artık frozen build için reddedilir. Yayın
paketinde güvenlik düzeltmeleri güncel olan bir 3.12 patch sürümü seçilip
yeniden derlenmelidir.

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

Önceki geçici `build/release_venv_cpu_py31215`, yeni interpreter ile oluşturuldu ve
`locked_cpu_dependencies.pth` üzerinden zaten hash-locked kurulmuş mevcut
CPU venv'in site-packages dizinini kullanır. Bu, ikinci bağımsız dependency
download/install kanıtı değildir; runtime 3.12.15 ve aynı sabit CPU
bağımlılıklarıyla test/derleme ortamıdır. Metadata/runtime/gerçek ORT ve
CPU forward/backward preflight geçti. Yeni üretim ortamları yine yukarıdaki
hash-locked kurulum reçetesiyle hazırlanmalıdır. Derleme/test için bu
makinedeki güncel Python yolu `build/release_venv_cpu_py31215/Scripts/python.exe`.

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
Son kaynak haliyle her ortamda **260 test** geçti. Geçici .pth ortamı yayın
ortamı olarak kullanılmaz.

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

### Eski Gyan full build araştırma kaydı

Mevcut FFmpeg/FFprobe **8.1.1 Gyan full build** EXE'leri resmi
[8.1.1 yayın arşivi](https://github.com/GyanD/codexffmpeg/releases/tag/8.1.1)
ile byte/hash olarak eşleştirildi. Yayın kaydının belirttiği FFmpeg commit'i
`239f2c733de417201d7ad3b3b8b0d9b63285b2b1`dir. İkililer değiştirilmedi.
`python -m tools.release.fetch_ffmpeg_material` resmi arşivi doğrular ve
`build/ffmpeg_material/8.1.1` altında EXE kopyaları, orijinal lisans metinleri,
configure satırı, provenance manifesti ve tam bu FFmpeg commit'inin kaynak
arşivini hazırlar. Bu dizin Git/paketli kişisel model verisi değildir.

Full build GPLv3 ve çok sayıda bağlı kütüphane içerir. Resmi binary arşivi
bağlı kütüphanelerin **tam sürüm/patch/build kaynaklarını sağlamıyor**; eldeki
manifest dürüstçe `source_completeness: ffmpeg-only` yazar. Yalnız FFmpeg
kaynak bağlantısını bütün kaynak yükümlülüğünün tamamlandığı gibi sunmuyoruz.
Dağıtılacak full build için bu materyal tamamlanmalı veya soxr ve kullanılan
WAV/FLAC/MP3/AAC codec'lerini karşılayan, kaynakları ve build reçetesi tam
başka bir native x64 build hazırlanmalıdır. [FFmpeg dağıtım rehberi](https://www.ffmpeg.org/legal.html).

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
$env:GHOSTKILLER_BACKEND='cpu'
$env:GHOSTKILLER_BUILD_PURPOSE='release'
$env:GHOSTKILLER_FFMPEG_DIR='C:\tam\dogrulanmis\ffmpeg-bundle'
build/release_cpu/Scripts/python.exe -m PyInstaller --noconfirm --clean --distpath build/release_dist_cpu --workpath build/release_work_cpu Ghostkiller_Sound_Cleaner_V2.spec
build/release_cpu/Scripts/python.exe -m tools.release.preflight --package-dir build/release_dist_cpu/Ghostkiller_Sound_Cleaner_V2
# Inno Setup 7/6 kurulu olan makinede; önce paketi doğrulayın:
build/release_cpu/Scripts/python.exe -m tools.release.build_installer --backend cpu --package-dir build/release_dist_cpu/Ghostkiller_Sound_Cleaner_V2 --check-only
build/release_cpu/Scripts/python.exe -m tools.release.build_installer --backend cpu --package-dir build/release_dist_cpu/Ghostkiller_Sound_Cleaner_V2
# Standart yollar dışında kurulmuşsa --compiler ile ISCC.exe'nin tam yolunu verin.
```

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
`Ghostkiller_V2_Setup_cpu_2.0.0.exe` (gerçek paket sürümüne ve backend'e göre)
olur. CUDA için kendi hash-locked venv'inde aynı akış `--backend cuda` ile yapılır.
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

Üretilen yerel adaylar kaynak sürümünü (**2.0.0**) korur. Önceki 2.0.0
kullanıcılarına otomatik güncelleme yayımlamak için yeni sürüm numarası
belirlenip **EXE ve installer yeniden derlenmelidir**; eski aday dosyasını
2.1.0 diye yeniden adlandırmak/metadata ile etiketlemek kabul edilmez.
`build/release_candidate_manifest.json` yalnız gerçek iki adayın hash/receipt
kontrolünden hazırlanmış yerel metadata'dır; kaynak version.json/packages
ve GitHub Release değiştirilmedi.

Eski `releases/latest`/hashsiz metadata'dan EXE kurulmaz. Uygulama yayın
sayfasını açıklayan güvenli bir mesaj gösterir. Yeni şema her backend için
`download_url`, `sha256`, `size` ister; URL aynı repo ve bildirilen sürümün
`releases/download/vX.Y.Z/Asset.exe` yolunda olmalıdır. GitHub'ın resmi
release-assets yönlendirmesi kabul edilir; başka host reddedilir. İndirme
boyutu/hash kontrol edilir, son doğrulama GUI thread dışında tekrar yapılır.
Varsayılan açık `auto_update` tercihi AppSettings'te saklanır. Kurulu uygulama
açılışta otomatik indirip uygular; Ayarlar'dan kapatılırsa ağ kontrolü yapılmaz.
Ayarlar düğmesi ve F5, tercihten bağımsız elle denetler ve indirme onayı ister.
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
python -m tools.release.make_update_manifest --version 2.1.0 --package cpu Setup/Ghostkiller_V2_Setup_cpu_2.1.0.exe dist/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --release-date 2026-10-14 --output build/version-2.1.0.json
```

Komut gerçek installer bytes'ından hash üretir, diagnostic veya derleme
kaydıyla uyuşmayan paket kabul etmez ve yalnız yerel JSON yazar. Yayımlama
yetkisi/işlemi içermez.
Yanında helper'ın ürettiği aynı adlı `.build.json` olmadan veya uygulama
sürümü/build-info/installer byte'ları bu kayıtla eşleşmeden manifest üretilmez.
Bu yerel derleme kaydı Authenticode yayıncı imzası değildir.
`version.json` bugün 2.0.0 ve unpublished olarak kalır; gerçek yeni kurulum
hazır olmadığı için hash veya yayın tarihi uydurulmaz. SHA-256 trusted GitHub
manifest/HTTPS kaynağına dayanır; publisher Authenticode imzası ve yayıncı
sertifikası ayrıca alınmalı/doğrulanmalıdır.

Son kabul: temiz Windows normal kullanıcıda Python/FFmpeg kurulu olmadan
başlangıç, worker dispatch, sentetik ayrıştırma/cover/eğitim durdur-devam,
Program Files izinleri, UAC iptal/başarı, NVDA/JAWS ve fiziksel donanım matrisi.
Yerel diagnostic EXE testi temiz VM veya fiziksel AMD/Intel GPU testi değildir.

## 14 Ekim düzeltme sonrası yerel doğrulama

- İlk global CUDA geliştirme ortamı ve ayrı CPU 3.12.0 ortamında 255 test
  geçti. Python/runtime ve TorchScript kaynak kontrolleri eklendikten sonra
  Python **3.12.15 / torch 2.11.0+cpu / ORT 1.29.0** ile son **257 test**
  28.238 saniyede geçti (`build/dagitim_fix_jit_tests.log`).
- Güncel spec'ten fresh diagnostic_cpu EXE üretildi:
  `build/dagitim_fix_dist_jit/Ghostkiller_Sound_Toolbox_Diagnostic_cpu`.
  `--self-test` **31.063 s**, `frozen=true`, `ok=true`: gerçek CPU
  forward/backward, ORT CPU, hidden native wx, Türkçe isimli FFmpeg/FFprobe
  dönüşümü, ayrı audio/training worker probe'ları. Kanıt
  `build/dagitim_fix_frozen_final_smoke.json`.
- Aynı frozen audio worker ile **4 s** sentetik kayıt işlendi:
  UVR-DeEcho-DeReverb iki **44100 Hz / 176400 frame / PCM_24 FLAC** çıktısı
  verdi (16.796 s). Korunan `private_model/latest.pth` ve voice.index ile
  cover **40000 Hz / 160000 frame WAV** verdi (12.907 s). Helper modeller
  yalnız test süresince artifact'in owned models dizinine kopyalandı; bu
  dizin temizlendi. Kaynak helper/voice/index/separator dosyalarının SHA-256
  değerleri değişmedi. Kanıt `build/dagitim_fix_frozen_real_audio.json`.
  Bu işlem süreleri tek cold testtir; hız/kalite benchmark'ı değildir.
- Eski geçersiz codec EXE'leri CWD/PATH'te olan frozen yol benzetiminde,
  gerçek FFmpeg/FFprobe ile analiz ve 40000 Hz decode geçti; kaynak ses
  değişmedi (`build/dagitim_fix_codec_upgrade_probe.json`).
- Inno Setup **7.1.0**, CPU/CUDA .iss için Output=no kontrollerinde geçti.
  Güncel helper ayrıca küçük sentetik fixture'ı gerçek ISCC ile derledi;
  `.build.json` ve manifest hash/boyut bağları eşleşti. Fixture installer
  çalıştırılmadı; oluşturulan geçici installer ve fixture temizlendi.
  Kanıt `build/dagitim_fix_inno_receipt_probe.json` ve aynı adlı log.
- Son artifact kaynak kimliği:
  `35683817e7fdd7237876b771be23f5904b7c9d8ec58e76c355e9b363091f88c0`.
  Diagnostic/release_eligible=false işareti korunur; gerçek installer veya
  update asset diye kullanılamaz. FFmpeg complete-source engeli, ayrı CUDA
  build ve temiz Windows kurulum/yükseltme/UAC kabulü açık kalır.

Değişiklikler yerelde; GitHub'a gönderilmedi. Kullanıcı sesleri, kayıtları,
ayarları, eğitim oturumları ve korunan model byte'ları değiştirilmedi.

## Kaynak geliştirme tanısı

```powershell
build/release_venv_cpu/Scripts/python.exe main.py --self-test build/source_native_smoke.json
```

Bu kaynak komutu EXE üretmez veya çalıştırmaz. Model indirmeden gizli native
wx kontrollerini, CPU forward/backward, gerçek ORT CPU oturumunu, Unicode ses
adıyla FFmpeg/FFprobe FLAC dönüşümünü ve ayrı Python audio/training worker
process'lerini sınar. Yerel denemede **34.312 saniyede geçti**;
[JSON kanıtı](YAYIN_DUZELTME_KAYNAK_NATIVE_KANITLARI.json) `frozen: false`
ile kapsamı belirtir. Kişisel model veya kayıt kullanılmadı. Güncelleyici ve
release ön kontrollerinin 27 regresyonu, eski workflow'ların 37 testi temiz
CPU venv'inde geçti. UAC/installer launch testleri ikame API'lerle çalışır;
Windows dosya paylaşım kilidi ve küçük ONNX oturumu gerçekten çalıştırılmıştır.
