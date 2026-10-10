# Ghostkiller Sound Toolbox

Windows için Türkçe, klavye ve ekran okuyucuyla kullanımı hedefleyen masaüstü ses işleme uygulaması. Geliştirici: Yasin Talha Gençsoy.

- Müzik/vokal ayırma, arka vokal, yankı ve gürültü temizleme.
- Yerel RVC modelleriyle ses değiştirme; iki motor için ortak işlemci/ekran kartı tercihi.
- Ayarlar sekmesinde donanım testi, model indirme, çevrimdışı bütünlük kontrolü ve bozuk dosya onarımı.

Sesler yerel bilgisayarda işlenir. Eksik modelleri indirmek ve güncelleme kontrolü için internet kullanılabilir. Eğitim, canlı mikrofon dönüşümü ve TTS içermez.

İlk kullanımda **Ayarlar** sekmesinden **İşlemci** veya **Ekran kartı** seçin. Donanım testi tamamlandıktan sonra seçili modeller için **Eksikleri indir** düğmesine basın. Ses işlemi sırasında model indirilmez; eksik veya değiştirilmiş dosyalar için Ayarlar açılır. **Dosyaları kontrol et** çevrimdışı çalışır; **Seçilenleri onar** eksik/bozuk dosyaları yeniden indirir. Eski yerel önbellekler bu ekranda kontrol edilerek kullanılabilir. Kişisel RVC ses modelleri AI Cover sekmesinden eklenir.

Intel/AMD işlemciler CPU yolunu, uygun NVIDIA kartları CUDA yolunu kullanır. AMD GPU seçimi uyumlu ROCm/PyTorch ortamında hesaplama testi geçerse açılır; mevcut CUDA ortamından üretilen setup, AMD GPU çalışma ortamını içermez. DirectML bu uygulamanın RVC/RoFormer zinciri için açılmaz. Destek ve doğrulama sınırları [donanım/model raporunda](docs/DONANIM_VE_MODEL_YONETIMI.md) açıklanır.

## Geliştirme

Mimari, dosya görevleri, erişilebilirlik ve işlem akışları için [oku.md](oku.md) dosyasını okuyun. Son senaryolar [senaryo raporunda](docs/SENARYO_TARAMASI.md), önceki düzeltmeler [düzeltme raporunda](docs/HATA_DUZELTME_RAPORU.md) açıklanır.

Mevcut doğrulama ortamı Python 3.12'dir. wxPython, audio-separator ve RVC/PyTorch bağımlılıkları kurulmuş bir ortamda:

```powershell
python main.py
python -m unittest discover -s test -v
```

Bağımlılık sürümleri henüz bir manifestte sabitlenmemiştir; temiz ortam kurulumunu doğrulanmış bir komut olarak sunmuyoruz. Ana bağımlılıklar ve paketleme bilgileri `oku.md` içindedir.

## Windows kurulumu hazırlama

1. Windows x64 `ffmpeg.exe` ve `ffprobe.exe` dosyalarını `tools/ffmpeg/` içine yerleştirin.
2. Uygulamanın bağımlılıklarını ve PyInstaller'ı hazırlayın.
3. `python -m PyInstaller Ghostkiller_Sound_Cleaner_V2.spec` ile EXE ağacını üretin.
4. Inno Setup ile `Ghostkiller_Kurulum.iss` dosyasını derleyin.
5. Yeni kurulumu temiz kullanıcı ortamında doğruladıktan sonra yayınlayın.

EXE ağacı `dist/`, tek dosyalı kurulum `Setup/` altında oluşur. Bu klasörler yeniden üretilir ve Git'e eklenmez. Sürüm metadatası yeni kurulum gerçekten hazır olduğunda güncellenmelidir. Kaynak temizliği, yayımlanmış eski kurulum dosyalarını değiştirmez.

## Kaynak ve yerel veriler

`test/` geliştirme testlerini, `docs/` teknik raporları barındırır; ikisi setup'a eklenmez. `models/`, `models.json`, `settings.json`, eski `modeller/`, `rvc/models/` ve FFmpeg ikilileri yerel veridir; Git'e eklenmez. Kişisel test modelleri kurulum paketine alınmaz.

Modeller programın kurulu olduğu yerdeki `models/` klasörüne indirilir. Ayrıştırma ağırlıkları doğrudan burada, RVC yardımcıları `models/predictors/` ve `models/embedders/` altında tutulur. Inno Setup bu klasöre normal Windows kullanıcıları için yazma izni verir. Eski yerel modeller gerektiğinde kopyalanarak yeniden indirme önlenir. `models.json` kayıtları kaynak çalışmada proje kökünde, kurulu uygulamada `%LOCALAPPDATA%/GhostkillerSoundToolbox` altında tutulur.

Lisans metni [lisans.txt](lisans.txt) dosyasındadır. Proje sitesi: [Ekransız Oyuncular](https://ekransizoyuncular.gen.tr/).
