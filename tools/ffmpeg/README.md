# FFmpeg araçları

Kurulum derlemesi burada `ffmpeg.exe` ve `ffprobe.exe` bekler. Yerel geliştirme ortamında mevcut araçlar bu klasöre kopyalanmıştır; büyük ikili dosyalar Git'e eklenmez.

Kaynak çalıştırmada Windows x64 FFmpeg araçları bu klasörde olabilir. Yayın
derlemesinde `GHOSTKILLER_FFMPEG_DIR` ile tam bir bundle seçilir: EXE/DLL,
gerçek SHA-256 `manifest.json`, lisanslar, eşleşen kaynak arşivleri ve build
reçetesi. PyInstaller bu materyali toplar; Inno Setup bütün EXE ağacını kurar.
Yalnız iki EXE içeren klasör yayın derlemesinden geçmez.

`main.py` bu klasörü PATH'e ekler. Mevcut 8.1.1 full build'in resmi provenance,
lisansları ve sabit FFmpeg commit kaynağı `tools.release.fetch_ffmpeg_material`
ile `build/ffmpeg_material` altında doğrulanabilir. Bu full build'in bağlı
kütüphane kaynakları henüz tamam değildir; yayımlanabilir kabul edilmez.
Tam akış için [yayın derleme rehberini](../../docs/RELEASE_BUILD.md) okuyun.
