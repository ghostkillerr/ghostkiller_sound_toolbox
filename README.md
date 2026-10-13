# Ghostkiller Sound Toolbox

Windows için Türkçe, klavye ve ekran okuyucuyla kullanımı hedefleyen masaüstü ses işleme uygulaması. Geliştirici: Yasin Talha Gençsoy.

- Müzik/vokal ayırma, arka vokal, yankı ve gürültü temizleme.
- Yerel RVC modelleriyle ses değiştirme; iki motor için ortak işlemci/ekran kartı tercihi.
- RVC V2 model eğitimi, kayıt analizi, durdur/devam, index ve AI Cover'a model kaydı.
- Ayarlar sekmesinde donanım testi, model indirme, çevrimdışı bütünlük kontrolü ve bozuk dosya onarımı.

Sesler yerel bilgisayarda işlenir. Eksik modelleri indirmek ve güncelleme kontrolü için internet kullanılabilir. Canlı mikrofon dönüşümü ve TTS içermez.

İlk kullanımda **Ayarlar** sekmesinden **İşlemci** veya **Ekran kartı** seçin. Donanım testi tamamlandıktan sonra seçili modeller için **Eksikleri indir** düğmesine basın. Ses işlemi sırasında model indirilmez; eksik veya değiştirilmiş dosyalar için Ayarlar açılır. **Dosyaları kontrol et** çevrimdışı çalışır; **Seçilenleri onar** eksik/bozuk dosyaları yeniden indirir. Eski yerel önbellekler bu ekranda kontrol edilerek kullanılabilir. Kişisel RVC ses modelleri AI Cover sekmesinden eklenir.

Intel/AMD işlemciler CPU yolunu, uygun NVIDIA kartları ayrı CUDA paketini kullanır. Intel GPU için ayrı XPU profili ve cihaz katmanı vardır; fiziksel kart/model doğrulaması yayın kabul koşuludur. AMD GPU native ROCm runtime ve doğrulanmış sürüm/kart profili gerektirir; CUDA paketi AMD runtime içermez. DirectML bu uygulamanın RVC/RoFormer zinciri için açılmaz. Paket profilleri ve doğrulama sınırları [yayın derleme rehberinde](docs/RELEASE_BUILD.md) açıklanır.

## Geliştirme

Mimari, dosya görevleri, erişilebilirlik ve işlem akışları için [oku.md](oku.md) dosyasını okuyun. Son senaryolar [senaryo raporunda](docs/SENARYO_TARAMASI.md), önceki düzeltmeler [düzeltme raporunda](docs/HATA_DUZELTME_RAPORU.md) açıklanır.

Mevcut doğrulama ortamı Python 3.12'dir. wxPython, audio-separator ve RVC/PyTorch bağımlılıkları kurulmuş bir ortamda:

```powershell
python main.py
python -m unittest discover -s test -v
```

Windows x64 / Python 3.12 bağımlılıkları `requirements/` altında CPU/CUDA/XPU için ayrı SHA-256 kilitleriyle sabitlenir. Aynı ortama birden fazla PyTorch backend'i veya ORT dağıtımı kurulmaz. Temiz venv, gerçek provider testi ve paketleme komutları [yayın derleme rehberinde](docs/RELEASE_BUILD.md) açıklanır.

## Windows kurulumu hazırlama

1. Kullanılacak backend'in hash kilidinden temiz venv hazırlayın ve preflight çalıştırın.
2. FFmpeg/FFprobe, bütün lisans/notices, eşleşen kaynak ve build reçetesini SHA-256 manifestli bir bundle olarak hazırlayın.
3. `GHOSTKILLER_BACKEND` ve `GHOSTKILLER_FFMPEG_DIR` seçerek PyInstaller spec'ini çalıştırın; paket içeriğini preflight ile kontrol edin.
4. Inno Setup ile `/DBackend=cpu` (veya doğrulanan diğer backend) vererek `Ghostkiller_Kurulum.iss` dosyasını derleyin.
5. Temiz Windows normal kullanıcı, fiziksel donanım, NVDA/JAWS ve güncelleme senaryolarını tamamlayın; gerçek installer'dan hashli yayın metadata'sı üretin.

EXE ağacı `dist/`, tek dosyalı kurulum `Setup/` altında oluşur. Bu klasörler yeniden üretilir ve Git'e eklenmez. Sürüm metadatası yeni kurulum gerçekten hazır olduğunda güncellenmelidir. Kaynak temizliği, yayımlanmış eski kurulum dosyalarını değiştirmez.

## Kaynak ve yerel veriler

`test/` geliştirme testlerini, `docs/` teknik raporları barındırır; ikisi setup'a eklenmez. `models/`, `models.json`, `settings.json`, eski `modeller/`, `rvc/models/` ve FFmpeg ikilileri yerel veridir; Git'e eklenmez. Kişisel test modelleri kurulum paketine alınmaz.

Modeller programın kurulu olduğu yerdeki `models/` klasörüne indirilir. Ayrıştırma ağırlıkları doğrudan burada, RVC yardımcıları `models/predictors/` ve `models/embedders/` altında tutulur. Inno Setup bu klasöre normal Windows kullanıcıları için yazma izni verir. Eski yerel modeller gerektiğinde kopyalanarak yeniden indirme önlenir. `models.json` kayıtları kaynak çalışmada proje kökünde, kurulu uygulamada `%LOCALAPPDATA%/GhostkillerSoundToolbox` altında tutulur.

Lisans metni [lisans.txt](lisans.txt) dosyasındadır. Üçüncü taraf bileşenler kendi lisanslarını korur; yayın paketi `THIRD_PARTY_NOTICES.md` ve `third_party/` materyalini içerir. Proje sitesi: [Ekransız Oyuncular](https://ekransizoyuncular.gen.tr/).
