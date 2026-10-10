# Ghostkiller Sound Toolbox — Proje ve ajan rehberi

Bu belge projeyi devralan bir yapay zekâ ajanının uygulamanın amacını, çalışan akışlarını, dosya sorumluluklarını ve erişilebilirlik gereksinimlerini tek okumada anlaması için hazırlanmıştır. İlk inceleme: 8 Ekim 2026; düzeltme güncellemesi: 11 Ekim 2026. Kod ve mantık regresyonları otomatik testlerle kontrol edilir. İlk wxPython panel oluşturma kontrolü geçmiştir; gerçek ekran okuyucu, uçtan uca ses kalitesi ve paketli EXE testleri ayrı doğrulama gerektirir. Güncel düzeltme ayrıntıları `docs/HATA_DUZELTME_RAPORU.md` dosyasındadır.

## 1. Projenin amacı ve çalışma sınırları

Ghostkiller Sound Toolbox, Windows için geliştirilmiş, Türkçe arayüzlü ve ekran okuyucularla kullanımı hedefleyen bir Python/wxPython masaüstü ses işleme uygulamasıdır. Geliştirici: Yasin Talha Gençsoy. Kullanıcı üç sekmeden işlem yapar:

1. **Müzik ve Ses Temizleme:** Müziği ve vokali ayırma, arka vokalleri, yankıyı ve gürültüyü temizleme.
2. **Ses Değiştirme (AI Cover):** Bir ses dosyasını seçilen RVC ses modelleriyle sırayla dönüştürme.
3. **Ayarlar:** Ortak CPU/GPU tercihi, gerçek donanım testi, yedi temel model/paketin indirilmesi, dosya kontrolü ve onarımı.

Ses işleme yerel donanımda yapılır. Eksik modellerin indirilmesi ve güncelleme kontrolü internet kullanabilir. Aktif masaüstü akışında ses dosyalarını bir sunucuya yükleyen bir adım bulunmaz. Model eğitimi, canlı mikrofon dönüşümü, TTS ve dönüştürülmüş vokali müzikle otomatik birleştirme bu iki sekmenin sunduğu özellikler değildir. Kullanılmayan eğitim, realtime, TTS ve analiz altyapısı kaynak ağacından kaldırılmıştır.

Ürün adı arayüzde Sound Toolbox olsa da kaynak yorumları, EXE, kurulum, lisans ve sürüm metadatasında Sound Cleaner/V2 adları da vardır. `updater.CURRENT_VERSION` ve `version.json` şu anda `2.0.0` değerini kullanır.

## 2. Dosya haritası

| Dosya veya dizin | Görevi |
| --- | --- |
| `main.py` | Giriş noktası, FFmpeg PATH hazırlığı, ana pencere, sekmeler, F5 güncelleme menüsü ve global hata raporu. |
| `app_runtime.py` | Uygulama/veri dizinleri, ortak iş kilidi, güvenli UI gönderimi, dosya adı temizleme ve atomik model indirme. |
| `app_settings.py` | Tek CPU/GPU tercihini `settings.json` içinde atomik saklar; iki panelin cihaz ve model ön kontrolünü yapar. |
| `hardware.py` | CPU ve CUDA/ROCm cihazlarında gerçek FP32/konvolüsyon/FFT/attention/LSTM denemesi; uygun GPU seçimi ve CPU thread sınırı. |
| `model_manager.py` | Yerel SHA-256 kayıtları, checkpoint CRC/yapı kontrolü, model/yardımcı dosya bağımlılıkları, eski cache ve atomik onarım. |
| `separation_steps.py` | Motor bağımlılıklarını import etmeden kullanılan ortak beş adım tanımı. |
| `separator_backend.py` | `LocalSeparator` adaptörü. Cihazı ve model dizinini zorlar; ses işinde eksik dosya indirmez. |
| `ui_settings.py` | Standart wx kontrolleriyle donanım/model yönetimi; arka plan işi, iptal ve ortak kilit. |
| `test/test_settings.py` | Donanım seçimi, iki motora cihaz aktarımı, indirme/CRC/SHA-256/onarım, ayar kaydı ve yeni sekme regresyonları. |
| `test/test_workflows.py` | Gerçek model ağırlığı yüklemeden hata, iptal, çıktı koruma ve kayıt regresyonları. |
| `test/test_motor.py` | Gerçek motor bağımlılıklarıyla CPU/CUDA yapılandırması, CWD, cleanup ve FAISS regresyonları. |
| `test/test_ui.py` | Görünmeyen gerçek wxPython penceresinde erişilebilir adlar ve temel kontrol davranışı. |
| `ui_separator.py` | Ses ayrıştırma arayüzü, model dizini seçimi, işlem zinciri, çıktı adlandırma ve ilerleme yakalama. |
| `ui_cover.py` | Ses modeli kayıtları, erişilebilir çoklu model seçimi, RVC ön koşulları ve dönüşüm kuyruğu. |
| `updater.py` | GitHub sürüm kontrolü, indirme diyaloğu, kurulum dosyasını başlatma. |
| `version.json` | Uzak güncelleyicinin okuduğu sürüm, açıklama ve indirme adresleri. |
| `models.json` | Kullanıcının yerel RVC model kayıtları; Git tarafından yok sayılır. |
| `models/` | Uygulama/EXE yanındaki model indirme dizini. Ayrıştırma dosyaları kökte; RVC yardımcıları `predictors/` ve `embedders/` altında. Git ve kişisel model paketlemesi dışında. |
| `modeller/`, `rvc/models/` | Eski yerel model dizinleri. Mevcut veriler korunur; gerekli modeller yeni dizine kopyalanabilir. Git dışında. |
| `rvc/infer/infer.py` | `VoiceConverter`: model yükleme, ses okuma, dönüşüm çağrısı ve çıktı yazma. |
| `rvc/infer/pipeline.py` | F0, içerik özellikleri, FAISS harmanlama, parçalı işleme ve sentez akışı. |
| `rvc/configs/config.py` | Her dönüştürücüye ait `Config`, seçilen CPU/CUDA cihazı ve belleğe göre işleme parametreleri. |
| `rvc/infer/f0_utils.py` | Sessiz aralık sınırlarını koruyan, sesli bölümlere ayrı F0 filtreleme. |
| `rvc/configs/*.json` | 24/32/40/48 kHz motor yapılandırmaları; model ağırlığı değildir, Git'te kalır. |
| `rvc/lib/algorithm/` | Sentezleyici, kodlayıcı, attention ve jeneratör bileşenleri. |
| `rvc/lib/predictors/` | RMVPE, CREPE, FCPE ve F0 yardımcıları. |
| `rvc/lib/utils.py` | Ses yükleme, ContentVec/diğer embedder modellerini hazırlama ve yükleme. |
| `rvc/lib/tools/split_audio.py` | Motorun ses bölme/birleştirme yardımcıları. |
| `Ghostkiller_Sound_Cleaner_V2.spec` | PyInstaller paketleme tanımı. |
| `Ghostkiller_Kurulum.iss` | Inno Setup kurulum tanımı. |
| `logo.ico`, `lisans.txt` | Simge ve son kullanıcı lisans metni. |
| `build/`, `dist/`, `Setup/`, `__pycache__/` | Yerel üretim çıktıları; kaynak yerine geçmez ve Git dışında tutulur. |

## 3. Açılış ve ana pencere

`python main.py` çalıştırıldığında kaynak dizini; paketlenmiş EXE çalıştırıldığında EXE dizini `app_dir` olarak seçilir. Paketli çalışmada `_MEIPASS` de PATH'e eklenir. Amaç FFmpeg/FFprobe gibi araçların bulunmasıdır.

`GhostkillerMainFrame`, bir `wx.Notebook` içine `SeparatorPanel`, `CoverPanel` ve `SettingsPanel` yerleştirir. Hepsi aynı `AppSettings` nesnesini kullanır. Başlangıç odağı notebook'a verilir. `wx.CallAfter` ile başlangıç bilgi diyaloğu, sessiz güncelleme kontrolü ve donanım testi planlanır. Araçlar menüsünde F5 ve Ayarlar bulunur. Ayarlar olmadan bağımsız panel pencereleri ses işi başlatmak için yeterli değildir; geliştirmede `main.py` kullanın.

Ana blokta `sys.excepthook`, `global_exception_handler` ile değiştirilir. Beklenmeyen hatalar kullanıcı veri dizinindeki `Ghostkiller_CrashLog.txt` dosyasına eklenir ve mesaj kutusu gösterilir. Günlük yazılamazsa hata yine bildirilir. Modül importları bu atamadan önce gerçekleşir; bu mekanizma bütün açılış veya worker hatalarını kapsayan bir garanti değildir. Paketli simge yolu `_MEIPASS` içinden çözülür.

## 4. Erişilebilirlik: korunması gereken temel davranışlar

Bu proje için ekran okuyucuyla ve yalnızca klavyeyle kullanım temel bir ürün gereksinimidir. Görsel tasarım değişiklikleri bu davranışları korumalıdır.

- Standart `wx.Button`, `wx.ToggleButton`, `wx.Notebook`, `wx.Choice`, `wx.SpinCtrl`, `wx.TextCtrl` ve yerel diyaloglar kullanılır. Özel çizilmiş kontrollerle değiştirirken erişilebilir ad, rol, durum ve klavye davranışı sağlanmalıdır.
- Seçim düğmelerinin durumu yalnızca renkle anlatılmaz: etikette `[AÇIK]`/`[KAPALI]`, yerel kontrolde basılı/basılı değil durumu vardır.
- `ModelToggleList`, `wx.ScrolledWindow` ve `wx.TAB_TRAVERSAL` kullanır. Yukarı/aşağı oklar komşu model düğmesine odak verir; diğer tuşlar `event.Skip()` ile normal işlenir. Tab/Shift+Tab ve Space davranışını koru.
- Sekme dolaşımı ve başlangıç odağı notebook üzerinden tasarlanmıştır. Ctrl+Tab, odak sırası ve menü erişimi gerçek Windows oturumunda denenmelidir.
- Dosya yolları, günlük ve durum metni salt okunur metin kutularında sunulur. Yüzde hem `wx.Gauge` hem durum metninde bulunur. Salt görsel gauge yeterli değildir.
- Başlatma, hata, iptal ve bitiş sonuçları anlaşılır Türkçe ile sunulmalıdır. Kullanıcı işlemin başarısını günlüğü taramak zorunda kalmadan anlayabilmelidir.
- Günlük ekleme veya ilerleme değişimi kullanıcının odağını zorla taşımamalıdır. Durumun otomatik seslendirilmesi mevcut kodla doğrulanmış değildir.
- İşlem bitişi, model listesi yenilenmesi, model silme ve diyalog kapanışı sonrasında odağın anlamlı yerde kalması test edilmelidir.

Kaynak yorumlarında “tam NVDA/JAWS uyumu” denmesi test kanıtı değildir. Kontrol adları, ayar etiketi bağlantıları, yüksek DPI, yüksek karşıtlık, dar pencere ve ekran okuyucu anonsları sonraki aşamada ayrıca doğrulanmalıdır.

## 5. Ses ayrıştırma akışı

`OnFileSelect` WAV/FLAC/MP3 seçtirir; çıktı klasörü daha önce seçilmediyse giriş dosyasının klasörü atanır. Kullanıcı beş işlem düğmesinden istediğini açar. Varsayılan olarak yalnızca ana vokal ayırma açıktır.

`OnStart`, giriş/çıktı varlığını ve en az bir işlem seçimini kontrol eder, kontrollerin değerlerini ana thread'de toplar ve ortak `JOB_LOCK` alındığında `ProcessChain` için daemon thread başlatır. Aynı anda cover ve ayrıştırma çalıştırılamaz. Zincir iki kola ayrılır:

1. Enstrümantal seçiliyse **orijinal girişten** müzik çıkarılır. Bu çıktı vokal zincirinin girdisi yapılmaz.
2. Vokal temizleme adımları sabit sırayla yürür. Her açık adım bir önceki açık adımın tuttuğu çıktıyı kullanır. Ana vokal ayırma kapalıysa sonraki ilk açık adım doğrudan orijinal sesi işler.

| Adım | Model dosyası | Tutulan çıktı anahtarı / son ad |
| --- | --- | --- |
| Enstrümantal | `melband_roformer_inst_v2.ckpt` | `(Instrumental)` → `_Ghostkiller_Enstrumantal.flac` |
| Ana vokal | `model_bs_roformer_ep_317_sdr_12.9755.ckpt` | `(Vocals)` → `_Ghostkiller_1_Ayrilmis_Vokal.flac` |
| Arka vokal | `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` | `(Vocals)` → `_Ghostkiller_2_ArkaSes_Silinmis.flac` |
| Yankı | `UVR-DeEcho-DeReverb.pth` | `(No Reverb)` → `_Ghostkiller_3_Yankisiz_Vokal.flac` |
| Gürültü | `UVR-DeNoise.pth` | `(No Noise)` → `_Ghostkiller_4_Gurultusuz_Vokal.flac` |

Son adların önüne giriş dosyasının uzantısız adı eklenir. `RunSeparatorCommand`, `LocalSeparator` örneği oluşturur; FLAC çıktı, ortak ayardan alınmış cihaz ve programın model dizinini verir; `load_model` ardından `separate` çağırır. CPU seçimi yapılmışsa CUDA kullanılabilir olsa bile ayrıştırma CPU'da çalışır. Kütüphane import edilemezse `Separator = None` olur ve işlem günlükte hata döndürür.

`get_model_directory` daima uygulamanın/EXE'nin yanındaki `models/` yolunu döndürür. İndirme ve eski önbelleklerin kontrol/kopyası Ayarlar'daki `ModelManager` işidir. Ses işi öncesinde seçilen modellerin kayıtlı dosya boyutu/mtime bilgileri kontrol edilir; tam içerik kontrolü Ayarlar'dan yapılır. Eksik veya değiştirilmiş dosya için işlem başlamaz, Ayarlar açılır. Eski `prepare_separator_model` uyumluluk yardımcısı ses işinde çağrılmaz. `AUDIO_SEPARATOR_MODEL_DIR` ortam değişkeni uygulamanın model klasörünü değiştiremez. Inno Setup yalnız `{app}/models` için `users-modify` izni verir.

İlerleme için süreç genelindeki `sys.stderr` geçici bir `StderrCatcher` ile değiştirilir; metindeki yüzde yakalanır. `finally` eski akışı geri koyar, separator referansını siler ve `gc.collect()` çağırır.

Her adım çıktı dizininin altında kendine ait geçici klasörde çalışır. Motor yolları gerçek dosya yolu çözümüyle bu klasöre sınırlanır. Son stem etiketi beklenen değere eşit olan tek çıktı seçilir; giriş adındaki `(Vocals)` gibi metinler seçimi bozmaz. Çıktının dolu ve sonlu ses örnekleri içerdiği çözümlenerek doğrulanır, ardından `os.replace` ile hedefe taşınır. Girişle aynı dosya kimliğine sahip hedef de reddedilir. Yalnızca işe ait geçici klasör temizlenir. Hata, iptal ve başarı sonuçları ayrıdır; `finish_job` UI güncellemelerinin ardından kontrolleri açıp kilidi ana thread'de bırakır.

İptal bir bayraktır. Devam eden kütüphane çağrısını zorla kesmez; mevcut adımın dönüşünde zincir durur.

## 6. AI Cover ve RVC akışı

Model ekleme, bir görünen ad, zorunlu `.pth` ve isteğe bağlı `.index` seçtirir. `models.json` yapısı şöyledir; örnek gerçek kullanıcı yolları içermez:

```json
{
  "Örnek Ses": {
    "pth": "models/ornek_ses.pth",
    "index": "models/ornek_ses.index"
  }
}
```

Göreli model yolları uygulama dizinine göre çözülür. `load_models`, dosya yoksa boş liste döndürür; bozuk JSON/şema için hata bildirir. `save_models`, geçici dosyaya yazıp atomik değiştirir; mevcut bozuk dosyayı ezmez ve yazma başarısızsa UI kaydını değiştirmez. Kaynak çalışmada kayıt proje dizinindedir; EXE çalışmada `%LOCALAPPDATA%/GhostkillerSoundToolbox/models.json` kullanılır. Eski EXE yanındaki kayıt mevcutsa ilk kullanımda kopyalanır. Model silme fiziksel ağırlığı silmez; yalnızca kaydı kaldırır. Liste yenilenirken mevcut model seçimleri korunur; yeni modeller kapalı oluşturulur.

`OnStart` açık modelleri ve ayarları toplar: pitch -24/+24 yarım ses, ortak Ayarlar'dan cihaz, F0 (`rmvpe`, `crepe`) ve varsayılan 0.75 index oranı. AI Cover içindeki ayrı CUDA/CPU seçimi kaldırılmıştır; yerinde Ayarlar düğmesi vardır. Motor ayrıca `crepe-tiny` ve `fcpe` tanır; bunlar GUI'de sunulmaz. Oran sonlu ve 0–1 aralığında olmalıdır. Girdi/çıktı varlığı, temizlenen model adlarının çakışması ve girişin üzerine yazılmaması kontrol edilir. Ortak iş kilidini alan `run_inference_queue` daemon thread'de modelleri sırayla işler.

1. Dosya yolları, model kayıtları ve ayarlar başlangıçta kopyalanır. Model yolları uygulama dizinine göre çözülür. Eksik yol için `models/` ve eski `modeller/` alt dizinleri aranır. Aynı adlı birden fazla dosya varsa rastgele seçim yapılmaz, tam yol istenir.
2. Başlatmadan önce ContentVec ve seçiliyse RMVPE için `ModelManager.require_ready` çalışır. RMVPE `models/predictors/rmvpe.pt`, ContentVec `models/embedders/contentvec/` içindedir. Worker'daki `ensure_rvc_prerequisites` GUI için yalnız yerel varlık kontrolü yapar. `VoiceConverter.allow_model_download=False` kullanılır; embedder eksikse internet erişimi yerine hata verir. Motor API'sinde eski indirme yolu `allow_model_download=True` / `allow_download=True` ile korunur; GUI bu yolu kullanmaz.
3. Her model için `VoiceConverter(device=...)` oluşturulur. Geçici WAV yalnızca boyutuyla değil çözümlenen ses örnekleriyle doğrulanır; doğrulama sonrasında iptal yeniden kontrol edilir ve iptal edilmediyse `<temizlenmiş_girdi_adı>_<temizlenmiş_model_adı>.wav` hedefine atomik taşınır. Başarısız veya iptal edilen dönüşüm önceki çıktıyı korur.
4. Eksik `.pth` başarısız sayılır ve yardımcı model indirmesine yol açmaz. Eksik index uyarıyla devre dışı bırakılır. Başarı/başarısızlık sayıları raporlanır. Geçici dosya veya model temizleme hatası sonraki modeli engellemez; `finish_job` UI tamamlanırken ortak kilidi tutar.

GUI çağrısı `protect=0.33`, `volume_envelope=1.0`, `embedder_model="contentvec"`, WAV çıktı kullanır. `split_audio`, autotune, önerilen pitch, gürültü temizliği ve post-process kapalıdır. Motorun daha fazla seçeneği olması bunların GUI'de açık olduğu anlamına gelmez. Cover işlemi ayrı bir Applio uygulaması veya servis başlatmaz; gömülü RVC kodunu aynı Python sürecinde kullanır.

Motorun ana zinciri:

```text
Giriş → 16 kHz ses okuma → 80 Hz high-pass ön işleme
      → ContentVec içerik özellikleri + F0 tahmini
      → pitch kaydırma + medyan/Savitzky–Golay F0 filtreleme
      → isteğe bağlı FAISS özellik harmanlama → checkpoint sentezleyicisi
      → modelin hedef örnekleme oranında WAV çıktı
```

80 Hz filtre `infer.py` içindedir; ayrıca `pipeline.py` 48 Hz high-pass tanımlar. F0 filtreleme kesintisiz sesli bölümlere ayrı uygulanır, sessiz aralıkların iki yanı harmanlanmaz. FAISS komşuluk ağırlığı `1 / max(score, 1e-5)` karesiyle normalize edilir; arama sayısı mevcut vektör sayısına sınırlanır, geçersiz komşu kimlikleri dışlanır ve boş index özellikleri değiştirmez. Checkpoint'in sürümü, F0 bilgisi, örnekleme oranı ve vocoder bilgisi ağ kurulumunu belirler. BigVGAN v2 ve Seed-VC bu uygulamaya entegre edilmiş değildir.

Cover iptali bayrakla çalışır; mevcut model dönüşümü biter, sonucu hedefe geçirilmez ve sonraki modele geçilmez. İki panel ve güncelleme indirmesi ortak iş kilidiyle koordine edilir. Ana pencerede işlem sürerken normal kapatma isteği veto edilir. `post_ui`, ana thread'deyken doğrudan uygular (kontroller hemen kilitlenir), worker'dayken `CallAfter` kullanır; silinmiş pencereye uygulanmaz.

Motor API'sinde farklı `resample_sr` istenirse ses gerçekten yeniden örneklenir; model/pipeline örnekleme hızı değiştirilmez. Bölünmüş ses birleştirmesi orijinal zaman çizelgesini ve sondaki sessizliği korur. Autotune sessiz F0 değerlerini sıfırda tutar ve pitch kaydırmasını uygular. F0/özellik uzunlukları koruma harmanlamasından önce eşitlenir. Okunamayan FAISS index dosyası dönüşümü açık hatayla durdurur; panel günlüğü ve başarısız model sayısı bunu gösterir. Uyumsuz FAISS boyutları veya eksik checkpoint ağırlıkları açık hata üretir; geçersiz FAISS vektörleri özelliğe NaN bulaştırmaz.

## 7. Güncelleme ve hata bildirimi

### Ayarlar, donanım ve model yönetimi

Kullanıcı donanım için yalnız **İşlemci / Ekran kartı** seçer. `detect_hardware`, CPU ve PyTorch'un CUDA API'sinde görülen her GPU için küçük FP32 konvolüsyon, FFT, attention ve LSTM işlemleri yapar. ROCm'li PyTorch da CUDA API'si üzerinden çalışır; `torch.version.hip` ile adı ayrılır. Birden fazla uygun GPU varsa en çok belleği olan seçilir. Kart adı tek başına destek sayılmaz. NVIDIA için CUDA, AMD için uyumlu ROCm çalışma ortamı gerekir; CUDA ortamında üretilmiş EXE AMD GPU kütüphanelerini içermez. DirectML, RVC ve tüm RoFormer zinciri için sunulmaz. GPU seçeneği kullanılamazsa nedeni gösterilir, CPU seçimi kullanıcıya bırakılır.

`settings.json` yalnız donanım tercihini tutar: kaynakta proje kökü, kurulu sürümde kullanıcı veri dizini. Git ve setup dışında kalır. Tercih atomik kaydedilir; yazma hatası mevcut tercihi değiştirmez. Cihaz ses işi başlangıcında kopyalanır ve iki motora da aktarılır. CPU'da thread sayısı mantıksal çekirdeklerin yarısı ile en fazla 8 olarak sınırlanır; GPU worker'ında seçili cihaz etkinleştirilir. FP32 korunur; quantization/FP16 tüm modellere zorlanmaz.

Model listesi beş ayrıştırma ağırlığı ile ContentVec/RMVPE paketlerini içerir; başlangıçta tümü seçilir. Kişisel ses modelleri AI Cover'dan eklenmeye devam eder ve kaynak URL'leri bilinmediğinden otomatik indirilmeye/onarılmaya çalışılmaz. Donanım testi indirme/onarım öncesinde geçmelidir; dosya kontrolü donanımdan bağımsız ve çevrimdışıdır.

- **Eksikleri indir:** Eksik dosyaları ve gereken JSON/YAML yardımcılarını indirir; bozuk mevcut dosya için Onar ister.
- **Dosyaları kontrol et:** Yapılandırma şemasını, checkpoint arşiv CRC'sini, güvenli PyTorch ağırlık okumasını ve tam dosya SHA-256 özetini denetler. İnternet çağrısı yapmaz; eski yerel cache bulunduğunda kontrol edip yeni klasöre kopyalayabilir.
- **Seçilenleri onar:** Eksik veya doğrulamada bozulan dosyayı kaynağından indirir. Geçici dosya kontrol geçmeden hedefin üzerine geçirilmez. Önceden kayıtlı ağırlığın SHA-256 değeri varsa yeni indirme de onunla eşleşmelidir.

`models/.integrity.json`, her paketin dosya yollarını, SHA-256, boyut ve mtime bilgilerini tutar. İlk sağlam yerel/download kopyasının özeti başlangıç kaydıdır; upstream imza veya tüm dosyalar için bağımsız yayımlanmış hash doğrulaması değildir. Ayrıştırma için kütüphanenin mimari/config eşlemesi de çalışır. Ses işi başındaki hızlı kontrol boyut/mtime ve son kayıt sonucuna bakar; stat bilgisi değişmeden içerik bozulmuşsa bunu tam dosya kontrolü bulur. Tam kontrolü her ses işi başında yeniden yapma.

Worker ana thread'deki kontrol değerlerini okumaz. İndirme/kontrolde iptal bayrağı, süre sınırı, `.part` dosyası ve atomik değiştirme kullanılır. Aktif ses/kontrol işi varken donanım değiştirilmez. Kilit UI sonuçları işlendikten sonra bırakılır. Gerçek motor çağrısı zorla kesilmez.

Numba/Librosa importlarından önce `configure_runtime_cache` çalışır. Varsayılan cache kaynakta `__pycache__/numba`, kurulu EXE'de kullanıcı veri dizininin `cache/numba` klasörüdür. Böylece kütüphane/Program Files dizinine cache yazılması önlenir. Kullanıcının mevcut `NUMBA_CACHE_DIR` değeri korunur.

11 Ekim düzeltmelerinden sonra 82 test başarılıdır (bkz. docs/HATA_DUZELTME_RAPORU.md). Önceki 75 test, gerçek CPU/CUDA RVC ve CUDA UVR-DeNoise denemeleri ile AMD/EXE sınırları [docs/DONANIM_VE_MODEL_YONETIMI.md](docs/DONANIM_VE_MODEL_YONETIMI.md) içindedir.

`updater.py`, GitHub `ghostkillerr/ghostkiller_sound_toolbox` deposunun `master/version.json` dosyasını arka plan thread'inde okur. Sayısal noktalı sürüm parçaları tuple olarak karşılaştırılır. Sessiz kontrolde yalnızca yeni sürüm varsa diyalog açılır; F5 kontrolünde güncel/bağlantı hatası da bildirilir.

Kullanıcı indirmeyi kabul ederse kurulum TEMP altında işe özel klasöre indirilir. İptal düğmesi indirme bayrağını ayarlar; iptal/başarısız indirme kurulum başlatmaz. Boş/eksik yanıt ve Windows EXE başlığı kontrol edilir. Bu kontrol kriptografik bütünlük doğrulaması değildir. Kurulum `shell=False` ile başlatılır; ses işi sürerken program kapatılıp kurulum başlatılmaz. Yeni kurulum tanımı tek EXE üretir; eski disk parçalı yayımlanmış kurulumlar bu değişiklikle yeniden paketlenmiş sayılmaz.

GUI günlükleri `wx.CallAfter` ile metin kutularına aktarılır. RVC içindeki birçok tanılama ise `print` kullanır; `console=False` EXE'de bunların kullanıcıya görünmesi garanti değildir. Global çökme raporu, panel günlükleri ve motor çıktıları ayrı mekanizmalardır.

## 8. Çalıştırma, bağımlılıklar ve paketleme

Depoda sürümleri sabitlenmiş `requirements.txt`, `pyproject.toml` veya CI tanımı bulunmuyor. Otomatik regresyon testleri `test/` altındadır. Aşağıdaki komutlar mevcut dosya yapısına göre giriş noktalarıdır; temiz ortamda doğrulanmış kurulum reçetesi değildir:

```powershell
# Proje kökünde, uygun Python ortamı etkinleştirildikten sonra:
python main.py

# Model indirmeden regresyon kontrolü:
python -m unittest discover -s test -v

# Gerekli paketler ve yerel kaynaklar hazırsa:
python -m PyInstaller Ghostkiller_Sound_Cleaner_V2.spec
```

Ana bağımlılık grupları: wxPython; audio-separator; PyTorch/torchaudio/torchvision; NumPy/SciPy/librosa/soundfile/soxr; FAISS; transformers; torchcrepe/torchfcpe; pydub/FFmpeg; pedalboard/noisereduce; model indirme yardımcıları. Bu liste kesin ve tamamlanmış bir paket manifestosu değildir; değiştirilen akışın importları ve paketleme hook'ları birlikte kontrol edilmelidir.

Kaynak çalıştırma için proje kökünü tercih et. Ana RVC config yolları modül konumundan, indirilen modeller uygulamanın/EXE'nin yanındaki `models/` dizininden çözülür. `Config(device=...)` seçilen CPU/CUDA cihazını uygular; CUDA yoksa açık hata verir. GPU çalışması PyTorch/CUDA ve donanım uyumuna bağlıdır. Inno Setup yalnızca model klasörüne kullanıcı yazma izni sağlar. Eski yerel modeller otomatik silinmez.

PyInstaller tanımı motor Python modüllerini import analiziyle, `rvc/configs/*.json`, sürüm, simge ve lisansı veri olarak toplar; büyük kütüphaneler için `collect_all` ve hidden import listesi kullanır. EXE adı `Ghostkiller_Sound_Cleaner_V2`, konsol kapalıdır. Inno Setup `.iss`, `dist` ağacını ve FFmpeg/FFprobe dosyalarını toplar. Proje yolları `SourcePath` temellidir; FFmpeg dizini `FFmpegDir` derleme tanımıyla değiştirilebilir, varsayılan proje içindeki `tools/ffmpeg` klasörüdür. `DiskSpanning=no` tek EXE üretir. Güncel kaynaklardan yeni kurulum henüz üretilmemiştir.

**Git ignore ile dağıtım içeriği farklıdır:** Spec artık kişisel `models.json`, `modeller/` ve tüm `rvc` dizinini veri olarak toplamaz. Yerel test modelleri paket girdisi değildir. Yeni bağımlılık hook'ları eklenirken model içeriklerini yanlışlıkla yeniden paketlememeye dikkat et.

### Temizlenen proje yapısı

Kaynak ağacı aktif masaüstü uygulaması ve kullandığı RVC dönüşüm bileşenleriyle sınırlandırılmıştır. `rvc/train/`, `rvc/realtime/`, TTS, analiz/TensorBoard/model eğitim yardımcıları, yinelenen kullanılmayan predictor dosyaları, eğitim discriminator'ı ve eski platform/ZLUDA yardımcıları kaldırılmıştır. Motorun kullanılmayan klasör-toplu-dönüşüm yöntemi ve eğitim GPU bilgi yardımcıları da çıkarılmıştır. Model checkpoint uyumluluğu için aktif sentezleyiciler/jeneratörler korunur.

- Kök: `main.py`, `ui_cover.py`, `ui_separator.py`, `app_runtime.py`, `updater.py`, `version.json`, simge, lisans, build tanımları, `README.md` ve bu rehber.
- `rvc/`: dönüşüm motoru, config, sentez ağları, aktif F0 ve ses yardımcıları.
- `test/`: regresyon testleri. Komut: `python -m unittest discover -s test -v`.
- `docs/`: hata düzeltme raporu; setup'a girmez.
- `tools/ffmpeg/`: yerel FFmpeg/FFprobe araçları; EXE dosyaları Git'e girmez, setup'a alınır.
- `models/`, `models.json`, eski `modeller/`, `rvc/models/`: yerel model verileri; korunur, Git ve kişisel model paketlemesi dışında kalır.

Eski `build/`, `dist/` ve `Setup/` çıktıları temizlendi. Bunlar yeniden derlemede oluşur ve Git'e eklenmez. Klasörler oluşmadan Inno Setup çalıştırılmaz; önce PyInstaller EXE ağacı hazırlanır. Site veya GitHub için bu temizlik sırasında yeni kurulum oluşturulmadı/yayımlanmadı.

## 9. Yerel modeller ve Git kuralları

Depo: `https://github.com/ghostkillerr/ghostkiller_sound_toolbox`, ana dal: `master`.

Kullanıcının açık tercihi: test modelleri ve kişisel model kayıtları yalnızca yerelde kalmalıdır. `.gitignore`, her seviyedeki `models/` ve `modeller/` klasörlerini, kökteki `models.json` dosyasını ve `.pth`, `.ckpt`, `.index`, `.bin`, `.pt` uzantılarını dışlar. Ses dosyaları ve üretim çıktıları da dışlanır. Ajan bunları `git add -f` ile eklememelidir.

`e4b432f` commit'i, `models.json` ile `rvc/models/embedders/contentvec/config.json` dosyalarını takipten çıkardı; yerel dosyalar korundu ve değişiklik GitHub'a gönderildi. İncelenen Git geçmişinde model ağırlığı yoktu. Eski commitlerde kayıt/config metni bulunabilir; geçmiş yeniden yazılmadı.

`models.json` yeni klonda yoktur. Uygulama boş model listesiyle açılabilir; kullanıcı model ekleyince kayıt oluşur. Model dosyalarının yerel varlığını test ederken içeriklerini, özel dosya yollarını veya ağırlıkları gereksiz yere rapora/Git'e taşıma.

Bu rehber hazırlanırken `main.py`, `ui_cover.py` ve `ui_separator.py` dosyalarında daha önce yapılmış, commit edilmemiş arayüz sadeleştirmeleri vardır. Bunları eski sürümle ezme. Yeni işe başlarken `git status` ve diff'i tekrar kontrol et; bu bilgi bir anlık durumdur.

## 10. İlk taramanın bulguları ve doğrulama başlıkları

Aşağıdaki tablo ilk incelemenin tarihsel problem listesidir; satırlar mevcut davranışın tamamını anlatmaz. Cihaz/F0 sözleşmesi, yanlış başarı mesajı, klasör farkıyla çıktı silme, worker UI getter'ları, ortak iş kilidi, dış finally, kayıt doğrulama/atomik yazma, çıktı adı/oran doğrulama, ana RVC yol çözümü, kaynak temizliği, indirme iptali ve model paketleme başlıkları kodda düzeltilmiştir. Ayrıntılı güncel durum ve test sınırları `docs/HATA_DUZELTME_RAPORU.md` içindedir. Ekran okuyucu ve gerçek ses/EXE doğrulaması ayrıca yapılmalıdır.

| Öncelik | Konum | Bulgu ve yapılacak inceleme |
| --- | --- | --- |
| Yüksek | `ui_cover.OnStart`, `run_inference_queue`, `Config` | Cihaz seçimi ayarlarda tutulup günlüğe yazılıyor, fakat motorun cihazına aktarılmıyor; `Config` otomatik seçiyor. CPU/CUDA seçimini gerçekten uygulayacak bir sözleşme kur. |
| Yüksek | `ui_cover.InitUI`, `Pipeline.get_f0` | GUI `mangio-crepe` sunuyor; motor dalları `crepe`, `crepe-tiny`, `rmvpe`, `fcpe` değerlerini tanıyor. Geçersiz yöntem dönüşüm hatasına yol açabilir. |
| Yüksek | `ProcessChain`, `run_inference_queue` | Hata/atlama sonrası genel bitiş mesajı başarı olarak gösterilebiliyor. Başarılı, başarısız, iptal ve kısmi sonuçları ayrı izle. |
| Yüksek | `GetNewFiles`, `ProcessChain`, `RenameAndKeep` | Klasör farkı çıktı tespitinde kullanılıyor; beklenmeyen yeni dosyalar silinebiliyor, eski isimlerin üstüne yazılması farkta görünmüyor. Yalnızca ilgili işin ürettiği dosyaları yönet. |
| Yüksek | Worker başlangıcı/sonu | Kontrol okuma çağrıları worker içinde; bazı getter'lar `CallAfter` argümanı hazırlanırken worker'da çalışıyor. UI verilerini ana thread'de al, tüm UI erişimini ana thread'e taşı. |
| Yüksek | İki panel ve `StderrCatcher` | Paneller birbirinden bağımsız başlayabiliyor; GPU belleği ve global stderr çakışabilir. Uygulama çapında iş koordinasyonunu incele. |
| Yüksek | `ProcessChain`, `run_inference_queue` | Dış kapsayıcı `try/finally` yok; ön koşul/dizin hatası arayüzü kilitli bırakabilir. Worker yaşam döngüsü, çift başlatma, kapanış ve iptal yarışlarını test et. |
| Orta | `load_models`, `save_models` | Bozuk JSON sessizce boş liste oluyor; kaydetme hatası yalnızca print ediliyor. Şema doğrulaması, atomik yazma ve erişilebilir hata bildirimi gerekli. |
| Orta | Model kayıtları ve çıktı adları | Aynı model adı eski kaydı değiştirebilir; model adındaki Windows geçersiz karakterleri çıktı yolunu bozabilir. Index oranı için aralık/sonlu sayı kontrolü yok. |
| Orta | `ensure_rvc_prerequisites` | Sabit Applio yolları, indirme sonrası doğrulama eksikliği ve başarısız hazırlıkta devam etme davranışı var. Kısmi indirmeyi geçerli model sayma. |
| Orta | `Config`, `rvc.lib.utils`, paketli çalışma | RVC yolları CWD'ye bağlı; kaynak ve EXE kaynak dizinleri ile yazılabilir kullanıcı veri dizini ayrılmalı. Program Files altında kayıt/indirme izinlerini test et. |
| Orta | Kaynak temizliği | GUI kuyruğundaki `gc.collect()` GPU kaynaklarının kesin boşaltıldığı anlamına gelmez. Motorun cleanup yöntemleri ve canlı referansların yaşam süresini incele. |
| Orta | `updater.py`, `.iss` | Dialog iptali indirme döngüsüne aktarılmıyor. Sabit TEMP dosyası, yalnızca EXE indirilmesi ile disk-spanning kurulumun uyumu ve bütünlük kontrolü incelenmeli. |
| Orta | `main.py` | Import hataları global handler kurulmadan oluşabilir; thread hataları ayrı ele alınmalı. Kapanan pencereye gecikmiş `CallAfter` erişimini kontrol et. |
| Orta | `.spec`, `.iss`, metadata | Test model paketleme, temiz klon build'i, mutlak yollar ve ürün/sürüm adlarındaki tutarsızlıklar giderilmeli. |
| Doğrulama | Erişilebilirlik | NVDA/JAWS, klavye dolaşımı, odak dönüşü, etiketler, ilerleme ve hata anonsları canlı test gerektirir. |

## 11. Düzeltme ve geliştirme çalışma sırası

İkinci taramanın senaryo tablosu, test kanıtları ve sınırları [docs/SENARYO_TARAMASI.md](docs/SENARYO_TARAMASI.md) içindedir. Model indirme hedefi kullanıcının son isteğiyle EXE yanındaki `models/` olarak belirlenmiştir; sonraki ajan bunu kullanıcı veri dizinine geri çevirmemelidir.

Kullanıcının istediği sıra: önce bu rehber; ardından hata ve sorun taraması/düzeltmeleri; sonrasında ek özellik geliştirmeleri. Hata düzeltmeleri ve kullanıcının istediği Ayarlar/donanım/model yönetimi özelliği yerel çalışma ağacındadır. Yeni setup henüz üretilmemiştir.

Sonraki ajan önce mevcut diff'i koruyarak yüksek öncelikli bulguları yeniden doğrulamalı. Motor sözleşmeleri, iş yaşam döngüsü ve çıktı güvenilirliği düzeltilmeden yeni özellik eklemek sorunların izlenmesini zorlaştırır. Düzeltmede ilgili akışın anlamlı regresyon kontrollerini ekle; model gerektirmeyen mantığı sahte motorlarla, ses kalitesini gerçek yerel modellerle ayrı doğrula. Her değişiklikten sonra bu rehberi gerçek davranışla güncelle.

Asgari doğrulama senaryoları:

1. Model kaydı bulunmayan temiz açılış; model ekleme, seçme, kayıt silme ve yeniden açılışta kalıcılık.
2. Tüm temel işlemlerin yalnızca klavyeyle kullanılması; NVDA/JAWS ile ad, rol, durum ve sonuçların anlaşılması.
3. Yalnızca enstrümantal, yalnızca vokal, çok adımlı temizlik, hiçbir adım seçilmeme ve aynı dosyayı tekrar işleme.
4. Çoklu RVC modeli, eksik PTH, eksik index, desteklenen her F0 yöntemi ve CPU/GPU seçimleri.
5. İzin hatası, bozuk kayıt, geçersiz index oranı, indirme hatası ve çıktı yazma hatasında doğru sonuç ve tekrar kullanılabilir UI.
6. İşlem sırasında iptal, tekrar başlatma, diğer sekmede başlatma ve pencere kapatma.
7. Farklı çalışma dizininden ve paketli EXE'den açılış; yazılamayan kurulum dizini; çevrimdışı ve eksik model koşulları.
8. Git'e model/kayıt/ses dosyası eklenmediğinin ve dağıtıma kişisel test modelleri karışmadığının kontrolü.

Test edilmemiş bir düzeltmeyi veya ses kalitesini doğrulanmış gibi raporlama. Ekran okuyucu testini yapamıyorsan hangi kontrollerin yapıldığını ve canlı doğrulamanın eksik kaldığını belirt. Erişilebilirlik davranışını ve yerel model verilerini korumak her aşamada önceliklidir.

## 12. 11 Ekim 2026 ek düzeltmeleri

Cover ve ayrıştırmada çıktı sesi doğrulandıktan sonra iptal yeniden kontrol edilir; bu aşamada iptal edilen iş eski sonucu değiştirmez. Model kataloğu separation_steps.py içindedir; audio-separator eksik olsa da iki ses paneli ve Ayarlar açılır, ayrıştırma çağrısı açıklayıcı hata verir.

Model kontrolünde ContentVec konfigürasyon alanları, konvolüsyon/attention boyutları ve ContentVec/RMVPE ağlarının bütün beklenen ağırlık anahtarları/şekilleri kontrol edilir. Kontrol için ağlar meta cihazında oluşturulur; gerçek ağırlık belleği ayrılmaz. Eski ContentVec weight_norm anahtarları desteklenir. RoFormer YAML bölümleri ve temel boyutları, hedef stem, ayrıştırma checkpoint katman grupları denetlenir. Ayrıştırma katman grubu denetimi her parametrenin eksiksizliğini veya ses kalitesini garanti etmez. schema_version=1 olmayan eski bütünlük kaydı yeniden tam dosya kontrolü ister; model dosyaları otomatik değiştirilmez veya indirilmez.

Okunamayan FAISS index sessizce devre dışı bırakılmaz; ilgili dönüşüm başarısız sayılır ve sonraki model işlenebilir. Eğitim özelliği henüz eklenmedi; araştırma/geliştirme promptu docs/EGITIM_OZELLIGI_PROMPT.md içindedir.

11 Ekim ek kontrol: mevcut beş ayrıştırma ağırlığı, üç RoFormer YAML dosyası ve ContentVec/RMVPE dosyaları yeni yapı/CRC kontrollerinden salt okunarak geçti. Kişisel model veya kayıtlar değiştirilmedi. UVR modellerinin ikinci aşamadaki ayrı düşük/yüksek bant katmanları için regresyon eklendi. Bu dosya kontrolü uçtan uca ses kalitesi testi değildir.

## Ayarlar model seçimi ve sekme adı — 11 Ekim 2026

Ayarlar model listesi artık standart wx.ToggleButton kullanır. İlk sekmedeki seçim mantığı gibi basılı/basılı değil durumu ve [AÇIK]/[KAPALI] etiketi vardır. Başlangıçta yedi model de açıktır; Space ile açılıp kapatılır, yukarı/aşağı ok ve Tab ile dolaşılır. Dosya durumları yenilenirken model kimlikleri, seçimler ve mevcut düğmeler korunur.

İlk sekmenin adı “1. Müzik ve Ses Temizleme” oldu. Eski addaki & işaretinin ardından boşluk gelmesi, yerel notebook kontrolünün Alt+Aralık kısayolu üretmesine neden oluyordu. Gereksiz mnemonic kaldırıldı; Windows sistem menüsü ve ilk sekmenin günlük/ilerleme kontrolleri korunur. Gerçek NVDA/JAWS anonsu bu ortamda ölçülmedi.
