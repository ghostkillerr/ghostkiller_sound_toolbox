# Native Windows yayın derlemesi

13 Ekim 2026. Bu akış kurulum yüklemez, sürüm yayınlamaz veya installer çalıştırmaz.
Mevcut çalışma kaynak geliştirme ve hata düzeltmesidir; kullanıcı talebiyle
yeni EXE derleme/çalıştırma işi durdurulmuştur. Aşağıdaki paketleme adımları
ilerideki yayın hazırlığı için saklanır.

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
python -m venv build/release_venv_cpu
build/release_venv_cpu/Scripts/python.exe -m pip install --no-deps --require-hashes -r requirements/bootstrap.lock
build/release_venv_cpu/Scripts/python.exe -m pip install --require-hashes --no-build-isolation -r requirements/cpu.lock
build/release_venv_cpu/Scripts/python.exe -m pip check
build/release_venv_cpu/Scripts/python.exe -m tools.release.preflight --backend cpu --hardware-check
```

Kilitler temiz CPU venv'inde gerçekten kuruldu; `pip check`, PyTorch
forward/backward ve gerçek küçük ONNX MatMul oturumu geçti. Aynı komutların
CUDA/XPU profillerinde fiziksel GPU testleriyle geçmesi ayrıca gerekir.
`.github/workflows/native-validation.yml` üç temiz ortamı kurar; hosted
runner'da CUDA/XPU adımı gerçek GPU kullanımı iddia etmez. Kaynak ortamının
Python'u 3.12.0'dır; yayın paketinde güvenlik düzeltmeleri güncel olan bir
3.12 patch sürümü seçilip yeniden derlenmelidir.

`tools.release.generate_locks` sadece resmi PyPI/PyTorch metadata'sını okur.
Sürüm güncellemesi `requirements/versions.json` ve ilgili profil değişikliği
olarak incelenir. Bazı XPU index kayıtlarında SHA-256 bulunmadığı için
bu wheel'in resmi HTTPS akışı kurmadan/diske kaydetmeden hash'lenmiştir.
Kilit üretimi bağımlılık kurmaz. Kaynak/sdist yeniden derlemesi bit düzeyinde
aynı binary garantisi vermez; yayın kullanılan wheel'leri arşivlemelidir.

## FFmpeg, lisanslar ve kaynaklar

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
build/release_venv_cpu/Scripts/python.exe -m PyInstaller --noconfirm --clean Ghostkiller_Sound_Cleaner_V2.spec
build/release_venv_cpu/Scripts/python.exe -m tools.release.preflight --package-dir dist/Ghostkiller_Sound_Cleaner_V2
# Inno Setup kurulu olan makinede:
ISCC.exe /DBackend=cpu Ghostkiller_Kurulum.iss
```

`GHOSTKILLER_BACKEND` zorunludur. EXE'de `build-info.json` gerçek backend,
Python/PyTorch, lock hash'leri ve FFmpeg bilgilerini taşır. XPU derlemesi
oneAPI wheel'lerinin native DLL/resource düzenini ve erken DLL search path
hook'unu içerir. UPX kapalıdır. Kullanıcı modelleri, sesleri, model kayıtları,
ayarlar ve eğitim oturumları paket kontrolünde reddedilir. CREPE/FCPE'nin
wheel ile gelen sabit yardımcı ağırlıkları ve audio-separator'un mixer
checkpoint/catalog kaydı açık izin listesindedir.

Inno Setup normal kullanıcıdan yönetici kurulumu için UAC ister. Ürün adı
Sound Toolbox'dır; önceki installer'ın AppId ve hedef dizini korunmuştur,
böylece yükseltme mevcut `models` dizinini kullanır. Backend installer adı
`Ghostkiller_V2_Setup_cpu.exe` (cuda/xpu/rocm karşılıkları) olur.

Kaynak materyali eksikken **yalnız yerel inceleme için**
`GHOSTKILLER_BUILD_PURPOSE=diagnostic` ve recovered FFmpeg dizini seçilebilir.
Bu artifact `Ghostkiller_Sound_Toolbox_Diagnostic_cpu` adıyla ayrı üretilir,
`build-info.json` içinde `release_eligible=false` taşır. Güncelleme manifest
üreticisi bu artifact'i kesin olarak reddeder; bu mod üretim kapısını açmaz.

## Güncelleme manifesti

Eski `releases/latest`/hashsiz metadata'dan EXE kurulmaz. Uygulama yayın
sayfasını açıklayan güvenli bir mesaj gösterir. Yeni şema her backend için
`download_url`, `sha256`, `size` ister; URL aynı repo ve bildirilen sürümün
`releases/download/vX.Y.Z/Asset.exe` yolunda olmalıdır. GitHub'ın resmi
release-assets yönlendirmesi kabul edilir; başka host reddedilir. İndirme
boyutu/hash kontrol edilir, son doğrulama GUI thread dışında tekrar yapılır.
Windows read-only paylaşım kilidi doğrulama ile UAC başlatma arasında dosyanın
değiştirilmesini/silinmesini önler ve süreç başlatıldığında serbest bırakılır.
Yalnız doğrulanmış dosya Windows `ShellExecuteExW(runas)` ile başlatılır.
UAC iptalinde uygulama açık kalır ve geçici kurulum temizlenir.

```powershell
python -m tools.release.make_update_manifest --version 2.1.0 --package cpu Setup/Ghostkiller_V2_Setup_cpu.exe dist/Ghostkiller_Sound_Cleaner_V2/_internal/build-info.json --release-date 2026-10-13 --output build/version-2.1.0.json
```

Komut gerçek installer bytes'ından hash üretir, fake/diagnostic paket
kabul etmez ve yalnız yerel JSON yazar. Yayımlama yetkisi/işlemi içermez.
`version.json` bugün 2.0.0 ve unpublished olarak kalır; gerçek yeni kurulum
hazır olmadığı için hash veya yayın tarihi uydurulmaz. SHA-256 trusted GitHub
manifest/HTTPS kaynağına dayanır; publisher Authenticode imzası ve yayıncı
sertifikası ayrıca alınmalı/doğrulanmalıdır.

Son kabul: temiz Windows normal kullanıcıda Python/FFmpeg kurulu olmadan
başlangıç, worker dispatch, sentetik ayrıştırma/cover/eğitim durdur-devam,
Program Files izinleri, UAC iptal/başarı, NVDA/JAWS ve fiziksel donanım matrisi.
Yerel diagnostic EXE testi temiz VM veya fiziksel AMD/Intel GPU testi değildir.

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
