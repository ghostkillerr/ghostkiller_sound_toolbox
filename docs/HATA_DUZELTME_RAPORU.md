# Kod ve mantık düzeltmeleri

Tarih: 10 Ekim 2026. Kapsam: aktif wxPython masaüstü uygulaması, ayrıştırma/cover iş akışları, bunların kullandığı RVC motoru, model kaydı, güncelleyici ve paketleme tanımları. Yerel test modelleri korunmuştur. Önceden yapılmış arayüz metni sadeleştirmeleri korunmuştur. Bu değişiklikler henüz GitHub'a gönderilmemiştir.

## Doğrulanan sorunlar ve düzeltmeler

| Sorun | Önceki davranış | Düzeltilen davranış |
| --- | --- | --- |
| CPU/CUDA seçimi | Seçim yalnızca günlüğe yazılıyordu; motor otomatik cihaz kullanıyordu. | `VoiceConverter(device=...)` ile seçim motor yapılandırmasına aktarılır. Her dönüştürücü ayrı config kullanır; CUDA yoksa açık hata verir. |
| F0 yöntem uyuşmazlığı | GUI `mangio-crepe` sunuyor, motor bu değeri tanımıyordu. | GUI iki seçeneğini koruyarak RMVPE/CREPE değerlerini sunar; motor bilinmeyen yöntemi açıkça reddeder. |
| Yanlış başarı bildirimi | Hata veya eksik model sonrası tüm işlemler başarılı gösterilebiliyordu. | Ayrıştırmada hata/iptal/başarı ayrılır; cover için başarılı ve başarısız model sayısı verilir. |
| İlgisiz çıktı silme | Çıktı klasörünün dosya farkından çıkan, beklenen etiketi taşımayan yeni dosyalar siliniyordu. | Her adım kendine ait geçici klasörde çalışır. Sadece motorun döndürdüğü, bu klasör içindeki çıktılar kabul edilir. |
| Tekrar ayrıştırma | Aynı isimli dosyanın üstüne yazılması klasör farkında görünmeyebiliyordu. | Motorun çıktı listesi esas alınır; aynı giriş tekrar işlenebilir. |
| Eski cover çıktısını başarı sayma | Önceden var olan çıktı, başarısız dönüşümde başarı kontrolünü geçirebiliyordu. | Dönüşüm ayrı geçici WAV'a yapılır; ancak tamamlanmış, dolu çıktı son hedefe taşınır. Eski çıktı hata durumunda korunur. |
| Birden fazla ses işi | İki panel aynı anda GPU kullanabiliyor ve global stderr üzerinden çakışabiliyordu. | Ortak, bloklamayan iş kilidi tek aktif ses işine izin verir. |
| Kilitli kalan UI | Worker ön koşul/dizin hataları sonunda kontroller açılmayabiliyordu. | Dış `try/finally` iş kilidini ve UI durumunu her durumda geri bırakır. Thread başlatma hatası da kilidi bırakır. |
| Worker'da UI okuma | Seçim ve log konumu getter'ları worker'da çalışıyordu. | İş seçimleri ana thread'de alınır; günlük/ilerleme güncellemeleri ana thread'de ve yaşayan pencerede uygulanır. |
| İşlem sırasında kapatma | Daemon işi sürerken uygulama normal şekilde kapatılabiliyordu. | Ana pencere normal kapatma isteğini işlem bitene kadar veto eder; kullanıcıya iptal/bekleme bilgisi verir. OS'nin zorunlu sonlandırmasına dair garanti yoktur. |
| Bozuk model kayıtları | Bozuk JSON boş listeye dönüşüyor ve sonradan üzerine yazılabiliyordu. | Şema doğrulaması ve erişilebilir hata bildirimi vardır. Mevcut bozuk dosyanın üzerine yazma reddedilir. |
| Kaydetme hatasına rağmen UI değişimi | Yazma hatası yalnızca print ediliyor; UI başarı gibi davranıyordu. | Kayıt atomik yazılır; başarısızlık bildirildiğinde model ekleme/silme UI verisini değiştirmez. |
| Model adı ve oran | Aynı model adı kaydı ezebiliyor; dosya adları geçersiz karakterler taşıyabiliyor; NaN/sonsuz/aralık dışı oran kabul ediliyordu. | Yinelenen ad reddedilir, dosya adları temizlenir, çıktı çakışmaları/girişin üzerine yazma engellenir ve oran 0–1 sonlu sayı olarak doğrulanır. |
| CWD bağımlılığı | Config, embedder ve predictor yolları çalışma dizinine bağlıydı. | Ana config modül konumundan, model yolları uygulama/veri dizininden çözülür. Göreli kullanıcı model yolu uygulama dizinine göredir. |
| Program Files'a yazma | Kayıt ve model indirmeleri için izin yönetimi yoktu. | Kişisel kayıtlar EXE çalışmada `%LOCALAPPDATA%/GhostkillerSoundToolbox` altında tutulur. Kullanıcının son tercihine göre modeller EXE yanındaki `models/` içine indirilir; Inno Setup yalnızca bu klasöre `users-modify` izni verir. Eski modeller korunur. |
| Kaynak temizliği | Motor cleanup'ı bazı alanları silip sonra yeniden silmeye çalışıyor, tekrar çağrıda hata verebiliyordu. | Referanslar `None` yapılır; temizleme tekrar çağrılabilir ve yüklenmiş model kimliği sıfırlanır. GUI her model sonunda cleanup çağırır. |
| F0 sessiz aralıkları | Bütün sesli örnekler birleştirildiğinden farklı cümlelerin uçları birlikte filtreleniyordu. | Kesintisiz sesli bölümler ayrı filtrelenir; sessiz bölgeler korunur. |
| Küçük/boş FAISS index | Her zaman sekiz komşu isteniyor; eksik komşu `-1` son vektöre erişebiliyordu. | Komşu sayısı index boyutuna sınırlanır; geçersiz kimlikler/mesafeler dışlanır. Geçerli komşusu olmayan örnek kendi özelliğini korur. |
| Yarım model indirmesi | Başarısız indirme nihai dosya adında yarım dosya bırakabiliyordu. | RMVPE ve embedder indirmeleri geçici dosyaya yazılır; başarıda atomik taşınır. Embedder indirmesinde timeout ve beklenen uzunluk kontrolü vardır. |
| Gereksiz RMVPE hazırlığı | Diğer F0 yöntemlerinde de RMVPE indirmesi zorunlu olabiliyordu. | RMVPE yalnızca RMVPE seçildiyse hazırlanır. |
| Güncelleme iptali | Diyalog iptali indirme döngüsünü durdurmuyordu. | İptal bayrağı indirmeye aktarılır; iptal edilen/eksik/boş indirme kurulum başlatmaz. Geçici dizin hata/iptalde temizlenir. |
| Güncelleme dosyası/çalıştırma | Sabit TEMP dosyası ve `shell=True` kullanılıyordu. | İşe özel TEMP dizini ve `shell=False` kullanılır. EXE başlığı kontrol edilir; aktif ses işi varken kurulumla uygulama kapatılmaz. |
| Sürüm karşılaştırma | `2.0` ile `2.0.0` farklı sayılabiliyordu. | Sürümler en az üç parçaya normalize edilir; negatif parçalar reddedilir. |
| Model paketleme | Spec kişisel `models.json`, `modeller/` ve tüm RVC dizinini veri olarak paketliyordu. | Kişisel model/kayıt girdileri kaldırıldı; config JSON dosyaları ayrı toplanır. |
| Kurulum taşınabilirliği | Tanımda geliştirici bilgisayarına ait mutlak yollar ve disk parçalı kurulum vardı. | Proje yolları `SourcePath` üzerinden çözülür; FFmpeg dizini derleme parametresiyle değiştirilebilir; yeni kurulum tek EXE olarak tanımlıdır. |
| Erişilebilir adlar | Bazı ayar/metin kontrollerinde açık bir erişilebilir ad yoktu. | Ayar, dosya yolu, günlük, durum ve ilerleme kontrollerine anlaşılır `SetName` değerleri verildi; standart kontroller ve açık/kapalı metinleri korundu. |

## Doğrulama

İlk kontrol: **18/18 test başarılı**. İkinci tarama ve genişletilen senaryolar [SENARYO_TARAMASI.md](SENARYO_TARAMASI.md) dosyasındadır. Python sözdizimi kontrolü ve `git diff --check` hatasızdır. `test/test_ui.py` gerçek, görünmeyen wxPython pencereleri kullanır; bu test canlı ekran okuyucu anonslarını ölçmez.

`python -m unittest discover -s test -v` ile model ağırlıklarını yüklemeyen regresyon testleri çalıştırılır. Senaryolar: tekrar ayrıştırma, ilgisiz dosyaların korunması, iş dışındaki çıktı yolunun reddi, iptal, yanlış başarı bildirimi, dış hata sonrası kilidin bırakılması, başarısız cover'da eski çıktının korunması ve CPU parametresinin aktarılması, atomik kayıt, bozuk JSON/şema koruması, göreli yol çözümü, sürüm/dosya adı, F0 sessiz sınırı, eksik model indirmesi ve güncelleme iptali.

Python sözdizimi derleme kontrolü ve `git diff --check` ayrıca çalıştırılır. Gerçek wxPython panel oluşturma ve gerçek RVC motorunda CPU yapılandırması/tekrar kaynak temizliği kontrolü yapılmıştır. `test/test_motor.py`, gerçek bağımlılıklarla config yol çözümü, CUDA yokken açık hata, tekrar cleanup ve küçük/boş/geçersiz komşulu FAISS senaryolarını kapsar. Numba'nın test ortamındaki salt okunur paket dizinlerine önbellek yazma denemesini önlemek için motor testleri `NUMBA_CACHE_DIR` değerini proje içindeki `__pycache__/numba` olarak verir; bu model dosyalarını değiştirmez.

Mevcut yerel modelle bir saniyelik 220 Hz sentetik ses CPU/RMVPE üzerinden gerçekten dönüştürüldü. İnternet indirmesi test sırasında yasaklandı. Çıktı 48 kHz, 47.040 örnekli, sonlu değerlerden oluşan dolu WAV olarak doğrulandı; motor dönüşümü yaklaşık beş saniye sürdü. Geçici giriş/çıktılar test sonunda temizlendi. Kullanıcının gerçek ses dosyaları kullanılmadı. Bu çalışma testi gerçek vokalde kalite ölçümü değildir.

## Kalan doğrulama sınırları

- NVDA/JAWS ile canlı klavye, odak, durum ve diyalog anonsları test edilmedi. Standart kontrol kullanımı ve isimler tek başına tam ekran okuyucu uyumunun kanıtı değildir.
- Gerçek bir vokalin CPU/GPU üzerinde tam dönüşümü ve işitsel kalite karşılaştırması ayrıca yapılmalıdır. F0 filtre matematiği testi ses kalitesi ölçümü yerine geçmez.
- Yeni PyInstaller EXE ve Inno Setup kurulum henüz oluşturulmadı. Python/CUDA bağımlılıklarının sürüm sabitlemesi ve temiz makine testi hâlâ gerekir.
- FFmpeg/FFprobe derleme kaynağı varsayılan olarak proje içindeki `tools/ffmpeg` dizinidir; başka makinede `FFmpegDir` verilmelidir.
- Eski yayımlanmış disk parçalı kurulum yeni tanımla otomatik değişmez. Güncel kaynaklarla yeni tek EXE üretilip yayımlanmalıdır.
- Güncelleme EXE başlığı/uzunluk kontrolü, imza veya SHA-256 doğrulaması değildir; manifestte doğrulanmış bir hash bulunmuyor.
- Kullanılmayan eğitim, TTS ve realtime modülleri temizlik aşamasında kaldırılmıştır.
- Sabit geliştirici Applio yolları ikinci taramada kaldırılmıştır; eski yerel dosyalar ve kullanıcı cache dizinleri gerektiğinde kullanılır.
- Çalışan motor çağrısını ortasından zorla kesme eklenmedi: iptal mevcut adım/model sonunda uygulanır.

`oku.md` güncel mimari ve davranışlarla birlikte okunmalıdır. Yeni özellik geliştirme aşamasına geçmeden önce gerçek ses, ekran okuyucu ve paketli uygulama doğrulamaları tamamlanmalıdır.

## Kaynak temizliği

Kullanılmayan eğitim/realtime/TTS ve analiz kaynakları, eski derleme/kurulum çıktıları, eski mimari öneri raporu ve motorun kullanılmayan eğitim/toplu klasör yardımcıları kaldırıldı. Rapor `docs/` altına taşındı. Yerel modeller korundu. FFmpeg/FFprobe proje içindeki `tools/ffmpeg` dizininde toplandı; ikili dosyalar Git dışında tutulur. Aktif motorun tüm iç importları temizlenen kaynak ağacına göre doğrulandı.

## 11 Ekim 2026 — ek regresyon düzeltmeleri

- Cover ve ayrıştırmada ses doğrulaması sırasında gelen iptal, hedefe aktarım öncesinde yeniden kontrol edilir. Önceki çıktı korunur; geçici çıktı temizlenir.
- ContentVec metadata alanları/boyutları ve ContentVec/RMVPE beklenen ağ ağırlık anahtarları/şekilleri kontrol edilir. Ağlar meta cihazında oluşturulur. RoFormer YAML bölümleri, temel boyutlar ve hedef stem ile ayrıştırma ağırlık katman grupları denetlenir. Bu, tüm ayrıştırma parametrelerinin eksiksizliğinin veya ses kalitesinin doğrulandığı anlamına gelmez. Eski kayıtlar schema_version=1 doğrulamasına geçmeden Hazır sayılmaz; kullanıcı Dosyaları kontrol et işlemini bir kez yeniden çalıştırır.
- FAISS dosyası okunamazsa ilgili dönüşüm açık hata verir; hata GUI günlüğüne ve başarısız model sayısına yansır. Index olmadan kullanmak isteyen kullanıcı kaydı index olmadan yeniden ekleyebilir.
- Beş adımın tanımı separation_steps.py içine taşındı. Ayrıştırma backend import edilemediğinde model kataloğu ve paneller kullanılabilir kalır. Yeni modül paketleme tanımına eklendi.

Doğrulama: **81/82 test başarılı**. Yeni testler iki panelde doğrulama sırasında iptal, bozuk index, ilgisiz metadata/checkpoint, eksik/yanlış şekilli helper ağırlıkları, eski kontrol kaydı ve eksik separator backend ile gerçek wx panel oluşturmayı kapsar. Küçük checkpoint kullanan dört mevcut dosya/indirme testinde yalnız mimari kontrolü taklit edilir; gerçek mimari kontrolleri ayrı testlerde çalıştırılır. Yeni setup/ekran okuyucu/ses kalitesi doğrulaması yapılmadı.

11 Ekim ek kontrol: mevcut beş ayrıştırma ağırlığı, üç RoFormer YAML dosyası ve ContentVec/RMVPE dosyaları yeni yapı/CRC kontrollerinden salt okunarak geçti. Kişisel model veya kayıtlar değiştirilmedi. UVR modellerinin ikinci aşamadaki ayrı düşük/yüksek bant katmanları için regresyon eklendi. Bu dosya kontrolü uçtan uca ses kalitesi testi değildir.
