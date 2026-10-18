# Ghostkiller Sound Toolbox — ajan ve geliştirici rehberi

Son doğrulama: **18 Ekim 2026**. Bu dosya projeye giriş noktasıdır; günlük veya
görev geçmişi değildir. Kullanıcının güncel talimatı burada yazanlardan önceliklidir.

## 1. Proje ve güncel durum

Türkçe, erişilebilir bir Windows masaüstü ses uygulaması. Geliştirici:
**Yasin Talha Gençsoy**. Windows x64, Python 3.12 ve wxPython kullanır.
Sesler yerel işlenir; internet model indirme ve sürüm denetimi içindir.

| Konu | Durum / kaynak |
| --- | --- |
| Uygulama sürümü | `version.json`: **2.1.0**, `unpublished`, `packages: {}` |
| Dağıtım | Güncel kaynak için CPU ve NVIDIA CUDA installer'ları yeniden üretilecek; indirilebilir yeni Release henüz yok |
| Kaynak doğrulaması | CPU ve CUDA ortamlarında ayrı ayrı **363 test** geçti; ayrıntı: [Son durum](docs/SON_DURUM.md) |
| Yerel ortamlar | `build/release_cpu`, `build/release_cuda`; bağımsız Python **3.12.15** ortamları |
| Paket desteği | CPU ve NVIDIA CUDA; XPU kaynak/CI profili vardır. Doğrulanmış Windows ROCm yayın kilidi yok |
| Kullanıcı kabulü | Enstrüman düğmelerinin açık/kapalı okunması kabul edildi; bütün uygulamanın ses kalitesi ve NVDA/JAWS kabulü tamamlanmadı |

GitHub'a kaynak göndermek kurulu programları güncellemez. Test geçmişi, eski
setup veya eski frozen sonuçlar bugünkü kaynak için yayın kabulü sayılmaz.
Durum değişirse önce kod/paket kanıtını kontrol et, ardından bu tabloyu güncelle.

## 2. Kullanıcının gördüğü dört alan

- **Müzik ve Ses Temizleme:** enstrümantal çıkarma ve seçilen vokal temizleme
  adımları; aynı sekmede SCNet dört kanal veya deneysel HTDemucs altı kanal
  enstrüman ayırma. Arka vokal temizliğinde isteğe bağlı A2SB kısa vokal onarımı.
- **Ses Değiştirme (AI Cover):** yerel RVC `.pth` modeli ve isteğe bağlı `.index`
  ile ses dönüşümü; seçilen modeller sırayla çalışır.
- **Model Eğitimi:** kayıt inceleme, bölüm seçme, RVC V2 eğitimi, durdur/devam,
  ara model karşılaştırma, oturumlar, deney sırası ve eğitilen modeli kaydetme.
- **Ayarlar:** donanım kontrolü, CPU/GPU tercihi, model hazırlama/onarım,
  ses dosyası biçimi, kanal düzeni, tema ve güncelleme denetimi.

### Korunacak ürün davranışları

- Ortak çıktı biçimi **MP3/WAV/FLAC/OGG**, varsayılan **FLAC**. Kanal düzeni
  **mevcut düzeni koru/mono/stereo**, varsayılan mevcut düzen. Tercihler kalıcıdır
  ve vokal/enstrüman/cover/eğitim dinleme çıktılarına uygulanır.
- İşlem zincirindeki geçici sesler kayıpsızdır; MP3/OGG çıktısı sonraki temizleme
  adımına girdi yapılmaz. WAV/FLAC 24 bit kaydedilir.
- Ses çıktılarına Ghostkiller eki veya `separation.json` eklenmez. Ad çakışırsa
  `(2)`, `(3)` ile yeni dosya/klasör oluşturulur; önceki sonuç korunur. Sonuç
  mesajı kapatılınca çıktı klasörü açılır.
- Biçim/kanal/donanım kısa özeti klavyeyle odaklanabilir. **Eksik modelleri
  hazırla** düğmesi yalnız seçili işlemin modelleri hazır değilse görünür ve
  yalnız o eksikleri hazırlar. Ses işlemi kendiliğinden model indirmez.
- Model indirmelerinde boyut ve disk alanı kontrol edilir. Sunucu destekliyorsa
  Range ve ETag/Last-Modified ile yarım indirme sürer; değişmiş veya bozuk parça
  kullanılmaz. Kısmi dosyalar `models/.downloads` içindedir.
- Açılışta otomatik güncelleme **denetimi** varsayılan açıktır. Geliştirici bilgi
  penceresinden önce kontrol edilir; yalnız yeni doğrulanmış sürüm varsa indirme
  onayı çıkar. **Evet** indirme/kurulumu başlatır; Hayır, hata veya iptal normal
  açılışa döner. İndirme/kurulum devrinde geliştirici penceresi açılmaz.
- Kapalı otomatik denetim açılışta ağ isteği yapmaz. Ayarlar/F5 elle denetler ve
  onay ister. Kaynak çalışması kendisini installer ile değiştirmez.

## 3. Kod haritası

| Dosya / dizin | Sorumluluk |
| --- | --- |
| `main.py` | Dört sekme, ortak ayarlar, açılış sırası, tek uygulama örneği, worker dispatch |
| `ui_separator.py`, `separation_steps.py` | Vokal/enstrüman seçimleri, temizleme zinciri ve çıktı adları |
| `ui_cover.py` | Kişisel RVC model listesi ve sıralı dönüşüm |
| `ui_training.py`, `ui_training_tools.py` | Eğitim, oturum, karşılaştırma ve deney sırası arayüzü |
| `ui_settings.py`, `ui_operation.py` | Tercihler, model hazırlama, koşullu düğme, sonuç klasörü ve hata yönlendirmesi |
| `ui_common.py`, `ui_model_terms.py` | Native tema, erişilebilir kontrol/açıklamalar ve model koşulları |
| `app_runtime.py`, `app_settings.py`, `registry_store.py` | Dizinler, `JOB_LOCK`, UI dispatch, atomik ayarlar/kayıt kilitleri |
| `audio_export.py` | Akışla kodlama, kanal dönüşümü, doğrulama ve çakışmasız çıktı yayını |
| `audio_service.py`, `audio_worker.py`, `native_process.py` | Ayrı ses motoru süreci, IPC/heartbeat, Windows Job Object ve iptal |
| `separator_backend.py`, `separation_audio.py` | Yerel ayrıştırma modeli/cihaz adaptörü ve ses bütünlüğü |
| `instruments/`, `restoration/` | SCNet/HTDemucs ayırma ve isteğe bağlı A2SB onarımı |
| `rvc/infer/`, `rvc/lib/`, `rvc/configs/` | RVC dönüşümü, F0/helper cache, model/index kontrolü ve ağlar |
| `training/` | Analiz/dataset, FP32 GAN, checkpoint/resume, değerlendirme/index/model kaydı |
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
   sunulur; indirme/kullanım onayını koru. Yeniden miksleme ekranı, TTS ve canlı
   mikrofon dönüşümü mevcut ürün kapsamında değildir.

## 5. Çalıştırma ve doğrulama

Önce `git status` ve ilgili kod/testleri oku. Hazır CPU/CUDA ortamlarını
kontrol etmeden yeniden kurma. Kaynak açılışı için uygun ortamın
`Scripts/python.exe main.py` komutu veya yerel `Setup/Yeni_Ozellikleri_Ac.cmd`
kullanılır. Kullanıcı programı kullanırken ikinci arayüz açma veya UI girişi gönderme.

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

Bağımlılık/derleme değişikliğinde aynı ortamda `pip check` ve
`python -m tools.release.preflight --backend <cpu|cuda>` çalıştır. Fiziksel GPU
kabulünü ayrı `--hardware-check` ile yap; GPU'suz hosted CI sonucu buna eşit değildir.
Temiz ortam ve iki gerçek setup reçetesi [Yayın derlemesinde](docs/RELEASE_BUILD.md).

Site değişikliğinde `node --test test/test_site.mjs` ve
`python -m tools.build_site` çalıştır. Çıktı yalnız `build/site` içinde olmalıdır.
Göndermeden önce stage edilmiş ağaçta `python tools/check_public_tree.py` ve
`git diff --cached --check` çalıştır. Kişisel yollar/ayarlar/raporlar gönderilmez.

## 6. Git, setup ve güncelleme yayını

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
- Yayın sırası: yerel sürüm → iki gerçek setup → kabul testleri → eşleşen
  receipt'lerden manifest → sabit tag ve iki asset'li Release → yayımlanmış
  dosyalar doğrulandıktan sonra `master/version.json` duyurusu.
- Setup'lar Git ağacına zorla eklenmez; Release asset olarak yüklenir. Legacy
  `AppId` ve kurulum dizini korunur. Güncelleme aynı backend'i seçer, UAC'yi
  atlatmaz; helper sonucu doğrulayıp yeniden açar ve kendi geçici setup'ını temizler.
- Kullanıcı ayrıca istemeden üretim installer'ını veya Windows Sandbox'ı
  geliştirici bilgisayarında başlatma. Kabul araçları disposable VM içindir.

## 7. Sıradaki iş ve belge seçimi

Güncel kaynak doğrulandı; yayın için **iki yeni installer**, gerçek sesle uzun
işlem/eğitim, NVDA/JAWS ve eski kurulumdan yükseltme kabulü tamamlanmalıdır.
Kullanıcıdan kod/hash/derleme komutu beklenmez; ses ve kullanım geri bildirimi alınır.

- Güncel kanıt ve açık işler: [SON_DURUM.md](docs/SON_DURUM.md)
- Kullanıcı denemeleri: [KULLANICI_KABULU.md](docs/KULLANICI_KABULU.md)
- Derleme ve yayın ayrıntıları: [RELEASE_BUILD.md](docs/RELEASE_BUILD.md)
- Kullanıcıya sunulacak sürüm notları: [CHANGELOG.md](CHANGELOG.md)
- Kullanım ve teknik konu dizini: [docs/README.md](docs/README.md)

Bu rehberi değiştirirken geçmiş temizlik sayıları, silinmiş rapor yolları,
yerel kişisel model adları ve tek kullanımlık görev talimatları ekleme.
