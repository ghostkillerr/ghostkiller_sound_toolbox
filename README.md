# Ghostkiller Sound Toolbox

Windows için Türkçe, klavye ve ekran okuyucuyla kullanımı hedefleyen masaüstü ses işleme uygulaması. Geliştirici: Yasin Talha Gençsoy.

**[Programı tanı ve kurulumları indir](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/)**
· [GitHub yayınları](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases)
· [Sürüm notları](CHANGELOG.md)

Kurulumlar şu anda kabul testi/yayın hazırlığındadır. Doğrulanmış CPU ve CUDA
sürümü yayımlandığında tanıtım sayfasındaki indirme bağlantıları otomatik açılır.
GitHub kaynak kodu, hazır installer yayını anlamına gelmez.

- Müzik/vokal ayırma, arka vokal, yankı ve gürültü temizleme.
- [Enstrüman ayırma](docs/ENSTRUMAN_AYIRMA.md): dört kanallı SCNet ve bilimsel kullanım için deneysel altı kanallı HTDemucs; ayrı stereo FLAC dosyaları.
- Arka vokal temizliğinden sonra isteğe bağlı [kısa vokal onarımı](docs/VOKAL_ONARIMI.md);
  standart ve onarılmış mono çıktılar ayrı saklanır.
- Yerel RVC modelleriyle ses değiştirme; iki motor için ortak işlemci/ekran kartı tercihi.
- RVC V2 model eğitimi, kayıt analizi, durdur/devam, index ve AI Cover'a model kaydı.
- Eğitim öncesi kayıt/bölüm inceleme, ara modelleri aynı seslerle karşılaştırma,
  oturum ve deney sırası, kayıtlı ayarlar, ek epoch ve önceki eğitimden yeni model.
- Ayarlar sekmesinde donanım testi, model indirme, çevrimdışı bütünlük kontrolü ve bozuk dosya onarımı.

Sesler yerel bilgisayarda işlenir. Eksik modelleri indirmek ve güncelleme kontrolü için internet kullanılabilir. Canlı mikrofon dönüşümü ve TTS içermez.

Kurulu uygulama varsayılan olarak açılışta yeni sürümü denetler, indirir ve kurulum
sihirbazını göstermeden aynı klasöre uygular; ardından program yeniden açılır.
**Ayarlar → Açılışta güncellemeleri denetle ve otomatik güncelle** seçeneği
kapatılabilir. Kapalıyken **Güncellemeleri denetle** düğmesi veya F5 ile elle
denetlenip onayla indirilebilir. Windows yönetici izni isteyebilir; iptal edilirse
program açık kalır. Kişisel model/ayarlar güncelleme paketine dahil edilmez.

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
