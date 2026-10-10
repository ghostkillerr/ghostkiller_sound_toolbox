# FFmpeg araçları

Kurulum derlemesi burada `ffmpeg.exe` ve `ffprobe.exe` bekler. Yerel geliştirme ortamında mevcut araçlar bu klasöre kopyalanmıştır; büyük ikili dosyalar Git'e eklenmez.

Yeni bir kaynak klonunda Windows x64 FFmpeg araçlarını bu klasöre yerleştirin. Inno Setup derlemesinde `/DFFmpegDir=...` verilerek farklı bir dizin de seçilebilir. Kurulum tanımı iki aracı EXE'nin yanına kurar; bu klasörün README dosyası setup'a dahil edilmez.

Kaynak koddan çalıştırırken FFmpeg/FFprobe sistem PATH'inde olmalıdır. `main.py` ayrıca bu klasörü PATH'e ekler. Dağıtımda kullanılan FFmpeg derlemesinin lisans/dağıtım belgeleri, ilgili derlemenin gerektirdiği şekilde pakete eklenmelidir.
