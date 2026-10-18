# Ghostkiller Sound Toolbox

Windows için Türkçe, klavye ve ekran okuyucuyla kullanımı hedefleyen masaüstü ses işleme uygulaması. Geliştirici: Yasin Talha Gençsoy.

Geliştiriciler ve yapay zekâ ajanları için başlangıç: **[oku.md](oku.md)**.

**[Programı tanı ve kurulumları indir](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/)**
· [GitHub yayınları](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases)
· [Sürüm notları](CHANGELOG.md)

**2.1.0 yayımlandı.** Windows x64 için [CPU ve NVIDIA CUDA kurulumlarını](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0)
indirebilirsiniz. CPU paketi yaklaşık **374 MB**, CUDA paketi **2,14 GB**.
Python ve FFmpeg paketlerin içindedir; ilk kullanımda gerekli modelleri programdan hazırlayın.
Kurulum dosyaları henüz dijital yayıncı sertifikasıyla imzalanmamıştır.

- Müzik/vokal ayırma, arka vokal, yankı ve gürültü temizleme.
- [Enstrüman ayırma](docs/ENSTRUMAN_AYIRMA.md): dört kanallı SCNet ve bilimsel kullanım için deneysel altı kanallı HTDemucs; ayrı ses dosyaları.
- Arka vokal temizliğinden sonra isteğe bağlı [kısa vokal onarımı](docs/VOKAL_ONARIMI.md);
  standart ve onarılmış çıktılar ayrı saklanır.
- Yerel RVC modelleriyle ses değiştirme; iki motor için ortak işlemci/ekran kartı tercihi.
- RVC V2 model eğitimi, kayıt analizi, durdur/devam, index ve AI Cover'a model kaydı.
- Eğitim öncesi kayıt/bölüm inceleme, ara modelleri aynı seslerle karşılaştırma,
  oturum ve deney sırası, kayıtlı ayarlar, ek epoch ve önceki eğitimden yeni model.
- Ayarlar sekmesinde donanım testi, model indirme, çevrimdışı bütünlük kontrolü ve bozuk dosya onarımı.

Sesler yerel bilgisayarda işlenir. Eksik modelleri indirmek ve güncelleme kontrolü için internet kullanılabilir. TTS içermez.

**Yayımlanmamış kaynak geliştirmesi:** 4. sekmeye deneysel
[Canlı AI Cover](docs/CANLI_AI_COVER.md) eklendi; Ayarlar 5. sekmeye taşındı.
Mikrofon sesini kayıtlı RVC modeliyle dönüştürüp seçilen kulaklıkta dinleme,
aygıt seçimi ve başlat/durdur akışı geliştiriliyor. Bu özellik yayımlanmış
2.1.0 kurulumlarında bulunmaz; gerçek ses ve gecikme kabulü henüz tamamlanmadı.
Canlı ses eşiği dinlerken ayarlanabilir; eşik altında dönüştürme bekler.
**Otomatik ayarla (10 saniye sessizlik)** ile ortam gürültüsü ölçülür;
eşik ayarlanınca mikrofon kapanır. Dinlemeyi ayrıca başlatın.
Günlükte yalnız mikrofon açılışı bir kez yazılır. Doğrudan `main.py` açılışı,
kayıtlı ekran kartı tercihi için hazır yerel CUDA ortamını kullanır.

**Ayarlar → Ses dosyası biçimi** bölümünden **MP3, WAV, FLAC veya OGG** seçin.
Vokal temizleme, enstrüman ayırma, AI Cover ve eğitim test sesleri aynı tercihle
kaydedilir. Tercih kalıcıdır; varsayılan FLAC'tır. Ses sonuçlarının yanına
`separation.json` dosyası yazılmaz.
Aynı sekmedeki **Ses kanalı düzeni** bölümünden **Mono (tek kanal)** veya
**Stereo (iki kanal)** seçebilirsiniz. Bu tercih de bütün ses çıktılarına
uygulanır. Varsayılan **İşlemin kanal düzenini koru** seçeneğidir.

Ses çıktılarına program adı eklenmez. Aynı ad zaten varsa yeni sonuç
`sarki_1_Ayrilmis_Vokal (2).mp3`, ardından `(3)` olarak kaydedilir; önceki
sonuç değiştirilmez. Enstrüman klasörleri de `sarki_Enstrumanlar (2)` gibi
numaralanır. İşlem sonucu mesajı kapatılınca sonuçların bulunduğu klasör açılır.

İşlem ekranındaki kısa özet seçili dosya biçimini, kanal düzenini ve donanımı
gösterir. Gereken modeller hazır değilse **Bu işlem için eksik modelleri hazırla**
düğmesi görünür; yalnız o işlemin eksikleri seçilip hazırlanır. Modeller hazır
olduğunda düğme gizlenir. Model indirmeleri sunucu destekliyorsa kaldığı yerden
sürer; tamamlanan dosyalar doğrulanmadan kullanılmaz.

Kurulu uygulama varsayılan olarak açılışta, geliştirici bilgi penceresinden önce
yeni sürümü denetler. Güncelleme varsa **“Güncellemeyi indirmek ister misiniz?”**
onayı gösterilir. **Evet** ile indirilip kurulum sihirbazını göstermeden aynı
klasöre uygulanır; ardından program yeniden açılır. **Hayır** ile normal açılış
devam eder. **Ayarlar → Açılışta güncellemeleri otomatik denetle** seçeneği
kapatılabilir. **Güncellemeleri denetle** düğmesi veya F5 ile elle de denetlenip
onayla indirilebilir. Windows yönetici izni isteyebilir; iptal edilirse program
açık kalır. Kişisel model/ayarlar güncelleme paketine dahil edilmez.

İlk kullanımda **Ayarlar** sekmesinden **İşlemci** veya **Ekran kartı** seçin. Donanım testi tamamlandıktan sonra seçili modeller için **Eksikleri indir** düğmesine basın. Ses işlemi sırasında model indirilmez; eksik veya değiştirilmiş dosyalar için Ayarlar açılır. **Dosyaları kontrol et** çevrimdışı çalışır; **Seçilenleri onar** eksik/bozuk dosyaları yeniden indirir. Eski yerel önbellekler bu ekranda kontrol edilerek kullanılabilir. Kişisel RVC ses modelleri AI Cover sekmesinden eklenir.

Ses temizleme ve ses değiştirme için gereken modeller başlangıçta seçilidir.
Eğitim modellerini ve yaklaşık 2,26 GB boyutundaki isteğe bağlı vokal onarım
modelini ihtiyaç duyduğunuzda ayrıca seçin. Dosya durumları yenilenirken
yaptığınız seçimler korunur.

İsteğe bağlı A2SB modeli ticari olmayan kullanım, altı kanallı HTDemucs
ağırlıkları bilimsel kullanım koşullarıyla sunulur. İndirme ve kullanım
öncesinde açıklama ve üreticinin koşullarına bağlantı gösterilir; kabul
etmezseniz işlem başlamaz. Dört kanallı SCNet ayrı bir modeldir.

Intel/AMD işlemciler CPU yolunu, uygun NVIDIA kartları ayrı CUDA paketini kullanır. Intel GPU için ayrı XPU profili ve cihaz katmanı vardır; fiziksel kart/model doğrulaması yayın kabul koşuludur. AMD GPU native ROCm runtime ve doğrulanmış sürüm/kart profili gerektirir; CUDA paketi AMD runtime içermez. DirectML bu uygulamanın RVC/RoFormer zinciri için açılmaz. Paket profilleri ve doğrulama sınırları [yayın derleme rehberinde](docs/RELEASE_BUILD.md) açıklanır.

## Geliştirme

Eğitime başlamak ve sonuçları karşılaştırmak için [adım adım eğitim rehberini](docs/MODEL_EGITIMI.md) okuyun.

Mimari, dosya görevleri, erişilebilirlik ve işlem akışları için [oku.md](oku.md)
dosyasını okuyun. Güncel testler ve kalan yayın işleri [Son durum](docs/SON_DURUM.md),
kullanım rehberleri [belgeler dizininde](docs/README.md) toplanır.

Mevcut doğrulama ortamı Python 3.12'dir. wxPython, audio-separator ve RVC/PyTorch bağımlılıkları kurulmuş bir ortamda:

```powershell
python main.py
python -m unittest discover -s test -v
```

Windows x64 / Python 3.12 bağımlılıkları `requirements/` altında CPU/CUDA/XPU için ayrı SHA-256 kilitleriyle sabitlenir. Aynı ortama birden fazla PyTorch backend'i veya ORT dağıtımı kurulmaz. Temiz venv, gerçek provider testi ve paketleme komutları [yayın derleme rehberinde](docs/RELEASE_BUILD.md) açıklanır.

Frozen EXE derlemesi için Python 3.12.0 kullanılmaz; `code.replace()` hatası
paketli SciPy'nin açılışını bozabilir. Build en az 3.12.1 ister; yayın için
güncel 3.12 güvenlik patch'i seçilmelidir. Bu makinedeki düzeltme/test runtime'ı
proje içinde hazırlanan Python 3.12.15'tir.

## Windows kurulumu hazırlama

1. Kullanılacak backend'in hash kilidinden temiz venv hazırlayın ve preflight çalıştırın.
2. `tools.release.build_ffmpeg` ile tam kaynaklı FFmpeg/libsoxr bundle'ını hazırlayın; `tools.release.fetch_runtime_material` ile seçilen CPython runtime'ın özgün lisans/provenance materyalini ekleyin. Bütün arşivler ve ikililer SHA-256 ile doğrulanır.
3. `GHOSTKILLER_BACKEND` ve `GHOSTKILLER_FFMPEG_DIR` seçerek PyInstaller spec'ini çalıştırın; paket içeriğini preflight ile kontrol edin.
4. Aynı venv'de `python -m tools.release.build_installer --backend cpu --check-only`, ardından `python -m tools.release.build_installer --backend cpu` çalıştırın; CUDA için kendi venv/paketini kullanın. Helper Inno Setup 7/6'yı standart kurulum yollarında bulur; gerekirse `--compiler` verin.
5. Temiz Windows normal kullanıcı, fiziksel donanım, NVDA/JAWS ve güncelleme senaryolarını tamamlayın; gerçek installer'dan hashli yayın metadata'sı üretin.

EXE ağacı `dist/`, tek dosyalı kurulum `Setup/` altında oluşur. Bu klasörler yeniden üretilir ve Git'e eklenmez. Sürüm metadatası yeni kurulum gerçekten hazır olduğunda güncellenmelidir. Kaynak temizliği, yayımlanmış eski kurulum dosyalarını değiştirmez.

Uygulama ve setup sürümü paketli `version.json` dosyasından gelir. Helper,
installer yanında sürüm/backend/build-info ve gerçek installer SHA-256/boyutunu
bağlayan `.build.json` kaydı üretir; güncelleme manifesti bu eşleşen kaydı ister.
Frozen sürüm FFmpeg/FFprobe'u `_internal` içinden mutlak yolla çalıştırır;
yükseltmede eski installer'ın kökte bıraktığı iki codec EXE'si kaldırılır.

## Kaynak ve yerel veriler

`test/` geliştirme testlerini, `docs/` teknik raporları barındırır; ikisi setup'a eklenmez. `models/`, `models.json`, `settings.json`, eski `modeller/`, `rvc/models/` ve FFmpeg ikilileri yerel veridir; Git'e eklenmez. Kişisel test modelleri kurulum paketine alınmaz.

Kişisel model adları, yerel dosya yolları ve cihaz/ayar dökümleri içerebilen
doğrulama raporları `build/local_reports/` altında Git dışında tutulur.
Değişiklikleri `git add` ile hazırladıktan sonra `python tools/check_public_tree.py`
çalıştırın. CI de Git'e hazırlanmış dosyaları kontrol eder. `rvc/configs/`,
`training/vendor/config_*.json` ve model mimarisi config'leri ortak uygulama
varsayılanlarıdır; kişisel ayar veya model kayıt listesi içermez.

Modeller programın kurulu olduğu yerdeki `models/` klasörüne indirilir. Ayrıştırma ağırlıkları doğrudan burada, RVC yardımcıları `models/predictors/` ve `models/embedders/` altında tutulur. Inno Setup bu klasöre normal Windows kullanıcıları için yazma izni verir. Eski yerel modeller gerektiğinde kopyalanarak yeniden indirme önlenir. `models.json` kayıtları kaynak çalışmada proje kökünde, kurulu uygulamada `%LOCALAPPDATA%/GhostkillerSoundToolbox` altında tutulur.

Lisans metni [lisans.txt](lisans.txt) dosyasındadır. Üçüncü taraf bileşenler kendi lisanslarını korur; yayın paketi `THIRD_PARTY_NOTICES.md` ve `third_party/` materyalini içerir. Proje sitesi: [Ekransız Oyuncular](https://ekransizoyuncular.gen.tr/).
