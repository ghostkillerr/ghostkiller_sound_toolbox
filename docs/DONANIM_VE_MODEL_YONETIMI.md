# Donanım ve model yönetimi — 18 Ekim 2026

Yeni Ayarlar sekmesi, iki ses motorunun aynı işlemci/ekran kartı tercihini kullanmasını sağlar. Kullanıcı teknik backend seçmez; CPU ve GPU ağırlıkları aynıdır. Intel ve AMD işlemciler CPU yoluyla, uyumlu NVIDIA kartları CUDA yoluyla kullanılır. AMD GPU için uygun ROCm/PyTorch ortamı gereklidir; mevcut CUDA ortamında üretilen setup AMD GPU çalışma ortamını içermez.

## Ses dosyası biçimi

Ayarlar'daki **Ses dosyası biçimi** listesinden **MP3, WAV, FLAC veya OGG** seçin.
Bu tercih vokal temizleme, enstrüman ayırma, AI Cover ve eğitimde üretilen dinleme
örneklerine uygulanır; yeniden açılışta korunur. Varsayılan FLAC'tır. İşlem
sürerken biçim değiştirilemez. WAV ve FLAC dosyalar 24 bit kaydedilir;
MP3 ve OGG sıkıştırılmış ses biçimleridir. MP3'ün desteklemediği 40 kHz gibi
örnekleme hızları, ses süresi korunarak en yakın desteklenen hıza dönüştürülür.

**Ses kanalı düzeni** listesinde **Mono (tek kanal)** ve **Stereo (iki kanal)**
seçenekleri vardır. Bu tercih de bütün ses çıktılarına uygulanır ve kalıcıdır.
Varsayılan **İşlemin kanal düzenini koru** seçeneğidir. Mono seçiminde sol ve sağ
kanalın ortalaması alınır; mono bir ses stereo kaydedilirse aynı ses iki kanala yazılır.

## Kullanım

İşlem ekranlarında yalnız gereken modeller hazır değilse **Bu işlem için eksik
modelleri hazırla** düğmesi görünür. Bu düğme Ayarlar'ı açıp yalnız ilgili
eksikleri seçer; mevcut sağlam dosyaları kullanır, eksik/bozuk olanları hazırlar.
İsteğe bağlı modellerin kullanım koşulları yine onaylanır. Hazırlık tamamlanınca
düğme gizlenir; dosya biçimi, kanal ve donanım özeti görünür kalır.

1. Ayarlar'ı açın. Açılıştaki donanım kontrolünün bitmesini bekleyin veya Donanımı kontrol et düğmesini kullanın.
2. İşlemci veya Ekran kartı seçin. Kullanılamayan cihaz için açıklama gösterilir; kayıtlı GPU tercihi sessizce değiştirilmez.
3. Listede ayrıştırma modelleri, ContentVec/RMVPE yardımcıları ve eğitim modelleri vardır. Space ile model seçimi değiştirilir. Yukarı/aşağı oklarla ve Tab ile dolaşılır; güncel kaynakta seçimler onay kutusu rolü, işaretli/işaretsiz durumu ve açık/kapalı etiketiyle sunulur.
4. Eksikleri indir, Dosyaları kontrol et veya Seçilenleri onar düğmesini kullanın.
5. Modeller hazır olduğunda ses sekmesine dönün. Eksik/değişmiş model ses işini başlatmaz; Ayarlar açılır.

Kişisel RVC ses modelleri AI Cover sekmesinden eklenir. Bunların otomatik yeniden indirme kaynağı bilinmez. Programın yönetilen modelleri kurulumun yanındaki `models/` dizinine iner; kişisel veriler Git'e ve setup'a eklenmez.

## Gerçek destek sınırı

| Yol | Algılama ve davranış | Doğrulama |
| --- | --- | --- |
| Intel/AMD CPU | FP32 konvolüsyon, FFT, attention ve LSTM testi. Ses işi worker'ında CPU thread sayısı en fazla 8, mantıksal çekirdeklerin yarısı. | AMD Ryzen 5 7500F üzerinde test edildi. Intel marka seçimi aynı yolu kullanır; fiziksel Intel makine testi yapılmadı. |
| NVIDIA CUDA | Kurulu PyTorch ve sürücünün gerçekten hesaplama yapması gerekir. Birden fazla uygun kart varsa en çok belleği olan seçilir. | RTX 5060 Ti, PyTorch 2.11.0+cu128 üzerinde donanım ve kısa RVC dönüşümü başarılı. |
| AMD ROCm | `torch.version.hip` algılanır; CUDA API'sini kullanan ROCm ortamında hesaplama testi geçerse seçilir. | Fiziksel AMD GPU/ROCm ortamında denenmedi. Bu kaynak yolu, mevcut CUDA setup'ını AMD GPU için hazır hale getirmez. |
| DirectML | RVC ve tüm RoFormer zinciri için etkinleştirilmez. | audio-separator'ın [resmî belgesinde](https://github.com/nomadkaraoke/python-audio-separator#windows-amd--intel-gpu-with-directml-experimental) RoFormer için GPU allocator sınırlaması ve Demucs için eksik LSTM operatörü açıklanır. |

AMD'nin Windows PyTorch desteği belirli cihaz/sürücü/çalışma ortamlarına bağlıdır; [resmî AMD sürüm notları](https://www.amd.com/en/resources/support-articles/release-notes/RN-AMDGPU-WINDOWS-PYTORCH-7-2-1.html) ve [destek matrisi](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html) esas alınmalıdır. Sadece “AMD/NVIDIA kart var” bilgisi, modellerin çalışabileceğinin kanıtı değildir. Donanım testi de bütün büyük modellerin belleğe sığacağını veya her şarkının başarıyla işleneceğini garanti etmez.

## Dosya kontrolü ve onarım

- İndirme HTTP süre sınırı ve uzunluk kontrolü kullanır; `.part` dosyası boş/eksik veya iptal edilmişse hedefe geçirilmez.
- Hazırlama öncesi eksik dosyaların sunucudan alınabilen boyutları gösterilir.
  İndirilecek dosya için boş disk alanı kontrol edilir. Boyut alınamayan dosyalar
  ayrıca belirtilir; bu bilgi dosya doğrulamasını değiştirmez.
- İndirilen JSON/YAML dosyası en çok **1 MiB**, diğer model dosyaları en çok
  **4 GiB** olabilir. Sınır hem HTTP başlığında hem okunan toplam baytta uygulanır.
  Boyutu bildirilmemiş akışta her blok öncesi disk alanı denetlenir; en az
  **64 MiB** boşluk payı bırakılır. Aşırı büyük metadata yerelden alınsa da
  parser'a verilmeden reddedilir.
- Desteklenen sunucularda ETag/Last-Modified ve Range ile yarım indirme sürer.
  Sunucu dosyası değişmişse veya Range desteklenmiyorsa dosya baştan indirilir.
  Kısmi dosyalar özel `.downloads` önbelleğinde tutulur; doğrulanan tamamlanmış
  dosya hedefe atomik geçirilir. Bozuk parçalar yeniden kullanılmaz.
- JSON/YAML boş/geçersiz olmamalıdır. Resmî RoFormer YAML tuple alanları desteklenir; Python nesnesi çalıştıran YAML etiketleri kabul edilmez.
- Checkpoint ZIP arşivlerinin CRC'si ve `torch.load(weights_only=True)` ile ağırlık yapısı kontrol edilir. İlk kayıt öncesindeki bozuk arşivler de yakalanır.
- Tam dosyanın SHA-256 özeti `models/.integrity.json` içinde tutulur. İlk sağlam kopya başlangıç kaydıdır; bu kayıt upstream imza doğrulaması değildir.
- Önceden kontrol edilmiş ağırlık değişmişse tam kontrol SHA-256 farkını bulur. Onarım indirmesi eski sağlam hash ile eşleşmeden önceki dosya değiştirilmez.
- İş başında boyut/mtime üzerinden hızlı kontrol yapılır. Aynı stat bilgileriyle bozulmuş içeriği tam dosya kontrolü yakalar.
- Kontrol çevrimdışı çalışır; model ve JSON/YAML bağımlılıkları yerel dosyalardan okunur. Eski cache dosyaları yalnız Ayarlar'dan kontrol edilip kullanılabilir.
- Kütüphanenin `AUDIO_SEPARATOR_MODEL_DIR` değişkeni veya otomatik CUDA tercihi, uygulamanın klasör/CPU seçimini geçersiz kılamaz.
- Donanım kontrolü, indirme, onarım ve ses işleri ortak `JOB_LOCK` ile koordine edilir. Worker oluşturma hatasında kontroller ve kilit eski durumuna döner.

## Test kanıtları

- İlk model yönetimi geliştirmesinde **75 test başarılıydı**. Güncel tam test
  sayısı ve kaynak/kurulum ayrımı [Son durum](SON_DURUM.md) içindedir. Testlerde
  küçük gerçek PyTorch checkpoint'leri, sahte ağ yanıtları ve görünmeyen gerçek
  wxPython kontrolleri kullanılır.
- Çok kartlı sistemde ONNX sağlayıcısına PyTorch ile aynı CUDA cihaz numarası
  iletilir. `cuda:1` aktarımı gerçek ONNX seçenek normalleştiricisiyle sınanır;
  bu regresyon testi iki fiziksel GPU üzerinde çalışma kabulü değildir.
- CPU/GPU seçimi ve kalıcılık, başarısız GPU kernel testi, iki motora aynı cihazın aktarılması, eksik modelde Ayarlar'a yönlendirme, bozuk tercih/bütünlük kaydı, CRC/SHA-256 farkları, atomik onarım, iptal ve yola taşma senaryoları kontrol edildi.
- Beş mevcut ayrıştırma ağırlığı ve ContentVec/RMVPE yardımcıları çevrimdışı CRC/yapı/hash kontrolünden geçti. Büyük modeller çoğaltılmadan eski yerel cache konumları salt okunarak test edildi; geçici bütünlük kayıtları temizlendi.
- 1 saniyelik sentetik 220 Hz ses, mevcut kişisel RVC ağırlığıyla hem CPU hem `cuda:0` üzerinden dönüştürüldü. İnternet yasaklandı; iki çıktı da **32 kHz, 31.360 sonlu örnek, 0,98 saniye**. Bu kısa işlev testi kalite veya karşılaştırmalı performans benchmark'ı değildir.
- Gerçek UVR-DeNoise ayrıştırması RTX 5060 Ti üzerinde çalıştı; ağ cihazı `cuda:0` olarak doğrulandı. İki FLAC çıktı **44,1 kHz, 43.680 sonlu örnek** içerdi. Diğer dört ayrıştırma modelinin bu turdaki kontrolü dosya/metadata kontrolüdür.
- Bu gerçek denemede Librosa/Numba'nın kütüphane dizinine cache yazarken beklediği görüldü. Numba import edilmeden önce `NUMBA_CACHE_DIR` ayarlanıyor: kaynakta `__pycache__/numba`, EXE'de kullanıcı veri dizininin `cache/numba` klasörü. Düzeltmeden sonra aynı GPU ayrıştırması tamamlandı; EXE cache yolu ayrıca regresyon testiyle kontrol edildi.
- NVDA/JAWS anonsları, AMD GPU, fiziksel Intel CPU, tüm GPU modellerinde gerçek şarkı ve yeni PyInstaller/Inno Setup dağıtımı ayrıca doğrulanmalıdır.

Sürüm numarası ve yayımlanmış eski setup değiştirilmedi. Yeni modüller PyInstaller tanımına eklendi; yeni setup bu kaynaklardan yeniden üretilmelidir.
