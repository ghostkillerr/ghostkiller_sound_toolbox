# Canlı AI Cover — deneysel özellik

26 Ekim 2026. Bu özellik yenilenmiş 2.1.0 CPU/CUDA kurulumlarında bulunur.
Önceki 2.1.0 kurulumunu kullananlar aynı backend paketini elle yeniden kurmalıdır. Dördüncü sekme **Canlı AI Cover**,
beşinci sekme **Ayarlar** olarak düzenlenmiştir.

## Kullanım

1. **Ses modeli ekle** ile kendi RVC `.pth` modelini ve varsa `.index` dosyasını
   ekle. Aynı form Canlı AI Cover ekranından da açılır.
2. Canlı AI Cover sekmesinde modeli, mikrofonu ve kulaklık aygıtını seç.
   Aygıtları değiştirirsen **Ses aygıtlarını yenile** düğmesini kullan.
   Dinlemeye başlamadan **Otomatik ayarla (10 saniye sessizlik)** düğmesine
   basıp 10 saniye konuşmadan bekleyebilirsin. Geri sayım biter, mikrofon
   kapanır ve **Dinleme tamamlandı** penceresi açılır. Pencerede **Ayarlandı.
   Mikrofon kapatıldı.** ve ölçülen eşikler görünür. Bu ölçümde model veya
   çıkış açılmaz; model hazır olmadan da mikrofon seçerek kullanılabilir.
3. Gerekiyorsa **Bu işlem için eksik modelleri hazırla** düğmesini kullan.
   CPU/ekran kartı tercihi 5. sekmedeki ortak Ayarlar'dan alınır.
4. **Canlı dinlemeyi başlat** düğmesine bas. Önce model ve yardımcı ağlar
   hazırlanır; ardından mikrofon açılır. Hazırlık ve seçilen aygıtların açılışı
   tamamlandığında seçilen çıkıştan kısa, yükselen bir hazır sesi gelir. Bundan
   sonra konuşabilirsin. Ses dönüştürülerek kulaklığa gönderilir.
   **Doğrulanmış ses yolu** alanında gerçekten açılan giriş ve çıkış görünür.
   Günlüğe yalnız bir kez **Mikrofon açıldı.** yazılır; tekrarlayan gecikme/
   eşik bilgileri yalnız durum alanını günceller.
5. **Canlı dinlemeyi durdur** ile kapat. Yanıt alınamıyorsa **Zorla durdur**
   seçeneği vardır. Dinleme bitmeden diğer ağır işler başlatılmaz.

Hoparlör sesi mikrofona geri girerek yankı/ıslık oluşturabilir; kulaklık kullan.
İlk dinleme düzeyi %50'dir. Canlı ses dosyaya kaydedilmez veya ağa gönderilmez.
Sanal mikrofon kurulmaz; amaç kendi dönüştürülmüş sesini seçilen çıkışta duymaktır.

## Ayarlar ve sınırlar

- Ses tonu: -24..24 yarım ses. 0 değişmez; pozitif inceltir, negatif kalınlaştırır.
- Index katkısı: 0..1; benzerlik ya da kalite puanı değildir. Yüksek her zaman daha iyi değildir.
- Güncel kaynakta index, RMVPE/CREPE yöntemi, parça süresi ve elle ses eşiği
  **Gelişmiş canlı ses ayarları** içindedir. Otomatik ölçüm temel ekranda kalır.
  Başlat/durdur ve durum özeti pencerenin altında sabittir; ses yolu ve günlük
  ayrı bir açılır bölümde gösterilir. Bu arayüz değişiklikleri 26 Ekim 2.1.0 yenilemesindedir.
- Parça süresi: 250, 500 veya 1000 ms; varsayılan 500 ms. Bu değer duyulan
  toplam gecikme değildir. Ses aygıtı, bağlam, dönüşüm süresi ve kuyruklar eklenir.
- CPU desteklenir; sürekli dönüşüme yetişeceği garanti edilmez. İşlem süresi
  parça süresini aştığında durum alanı bunu bildirir. Daha uzun parça veya
  kullanılabilir ekran kartı seçilebilir; kalite veya donanım kendiliğinden değişmez.
- Ses eşiği varsayılan açık ve **-45 dB**'dir; **0 dB veya altında alt sınır
  olmadan** doğrudan yazılarak dinleme sürerken değiştirilebilir. **-100** veya
  **-120,5** gibi değerler kabul edilir; sayı sonlu olmalıdır. Daha fazla dip sesi kesmek için örneğin
  **-35 dB**, daha zayıf sesi almak için **-60 dB** seçilebilir.
  Durum alanı giriş seviyesini ve eşik altında beklemeyi gösterir. Eşik
  kapatılabilir. Tamamen eşik altında kalan parçada RVC/F0 çalıştırılmaz ve
  çıkış sessiz tutulur; ham mikrofon sesi çıkışa geçirilmez. Model RAM/VRAM'de
  hazır kalır; azaltılan kaynak kullanımı sürekli dönüştürme hesabıdır.
- Otomatik ayar yalnız düğmeye basınca 10 saniyelik ölçüm yapar; başarıdan
  sonra arka planda dinlemez ve canlı dönüşümü kendiliğinden başlatmaz.
  **Ölçümü iptal et** önceki eşiği korur. Ölçümde uzun süre değişen ses,
  çok yüksek/clip yapan giriş veya sessize alınmış mikrofon görülürse yeni
  eşik uygulanmaz. Ölçüm esnasında konuşmamak gerekir; yalnız gürültü ölçümü
  konuşmayı kesin olarak tanıyan bir model değildir. Sonrasında gerekirse
  eşik elle düzeltilebilir; mikrofon/kazanç/ortam değişince yeniden ölçülmelidir.
  Profil bu açılış için tutulur; kişisel ayar dosyası değiştirilmez. Mikrofon
  seçimi değişince önceki otomatik profil bırakılıp -45 dB varsayılanına dönülür.
- Ortak ses dosyası biçimi ve mono/stereo export tercihi canlı dinlemeye
  uygulanmaz. İlk Windows aygıt katmanı 48 kHz, 16 bit PCM mikrofon alır ve
  mono dönüştürülmüş sesi iki kulaklık kanalında çalar. RVC hesaplaması float'tır.
- Aygıt/model/perde ayarları başlamadan alınır; değiştirmek için dinlemeyi durdur.
  Ses eşiği bu kuralın istisnasıdır: dinleme sırasında atomik bir kontrol kaydıyla
  güncellenir; worker arayüz kontrolü okumaz.
- Windows varsayılan aygıtı veya numarasıyla listelenen aygıt seçilebilir.
  Yeniden bağlanan cihazı listeyi yenileyerek tekrar seçmek gerekebilir.
  Seçimler native öğe verisine bağlıdır. Açılan aygıtın numarası ve adı
  doğrulanır; seçilen Line 2 bulunamaz veya değişirse varsayılana geçilmez.
  Windows'un varsayılan aygıtı veya sanal kablonun kendi dinleme ayarları değiştirilmez.
- Bu sürüm dosya dönüşümünün RVC pipeline'ını bağlamlı pencerelerle kullanır.
  Özel bir düşük gecikmeli streaming ağ olduğu iddia edilmez; cümle sınırları,
  vibrato, uzun konuşma, Bluetooth/USB aygıtları ve gerçek gecikme denenmelidir.

## Uygulama sözleşmesi

`ui_live_cover.py` UI getter'larını ana thread'de okuyup değişmez `LiveOptions`
oluşturur. Ortak `JOB_LOCK` alınır; `NativeAudioSession` ayrı worker açar.
`audio_worker.py` içindeki `live_cover` isteği `live_cover.run_live` çalıştırır.

`main.py` sistem Python'u veya CPU ortamıyla doğrudan açıldığında, kayıtlı
ekran kartı tercihi ve hazır yerel CUDA ortamı varsa `source_runtime.py`
arayüzü bu ortamla başlatır. Hazır CUDA ortamı CPU tercihiyle de kullanılabilir.
Worker/self-test ve kurulu EXE yönlendirilmez; ortam kurulmaz ve kişisel
ayar dosyası değiştirilmez. Canlı dinleme özetinde algılanmış GPU adı gösterilir.

Model, ContentVec, F0 helper'ı ve güvenli parser ile okunan index oturum boyunca
saklanır. Normal RVC kalite politikası ve 160 örneklik hop korunur. Sesler
NumPy dizileridir; her parça için WAV veya JSON ses dosyası yazılmaz. Kontrol/
durum IPC'si ve worker günlükleri uygulamanın mevcut geçici oturum alanındadır.

Mikrofon polling'i ayrı thread'de ilerler; en fazla iki dönüştürülmemiş parça
tutulur. Geri kalınırsa en eski parça atlanır, bağlam sıfırlanır ve sayaç
bildirilir. Sol bağlam 500 ms, ortak zaman aralığında crossfade 20 ms'dir.
Çıkış kuyruğu da sınırlıdır; ses gecikmesi sınırsız büyütülmez.

Ses eşiği 10 ms RMS aralıklarıyla, 6 dB histerezis, 150 ms bekleme,
5 ms açılma ve 120 ms kapanma zarfıyla uygulanır. Açılma/kapanma zarfı
kosinüsle yumuşatılır; bekleme kısa kelime aralarında gate'in kapanmasını
azaltır. Tam kapalı parça model
çağrısını atlar; kısmen konuşmalı parçadaki sessiz aralıklar da dönüştürülmüş
çıkışta 20 ms zaman hizası korunarak susturulur. Böylece modelin sessiz
aralıklarda üretebileceği dip sesi çıkışa taşınmaz.

`live_gate.py` ölçüm geçmişi olarak 1000 RMS seviyesi ve en fazla bir 10 ms ses
aralığını bellekte tutar; ses dosyası veya gürültü kaydı üretmez. 48 kHz'de tam
480.000 örnek alındıktan sonra mikrofon kapanır. Tekil tıklamaları eşik yapmamak
için RMS seviyelerinin yüzde 95 değeri gürültü tabanı sayılır; 0,1 dB'ye
yuvarlanıp +10 dB açılma payı eklenir, tam dB'ye yukarı yuvarlanır ve en fazla
0 dB olur; -80 dB alt sınırı uygulanmaz. Kapanma açılmanın 6 dB altıdır; dolayısıyla normalde
gürültünün en az 4 dB üzerindedir. Bu marjlar uygulamanın başlangıç politikasıdır;
yalnız sessizlik ölçerek kullanıcının en kısık konuşmasını bilmek mümkün değildir.
Ölçümün iptal/okuma/hata yolları mikrofonu kapatır; stall için süre sınırı ve
ayrı worker'ın zorla durdurma desteği vardır. `Ayarlandı` ancak native aygıt ve
worker oturumu kapandıktan sonra **Dinleme tamamlandı** penceresinde gösterilir.
Geçersiz/iptal edilen ölçümde başarı penceresi açılmaz. Çok düşük eşikler
dB alanında karşılaştırılır; sayısal alt-taşma yüzünden sıfır ses gate'i açmaz.
Windows varsayılan mikrofonu
ölçüldüyse sonraki dinleme gerçekten ölçülen aygıta bağlanır.

Gate tasarımında [OBS Noise Gate](https://obsproject.com/kb/noise-gate-filter)
belgesindeki ayrı açılma/kapanma eşikleri, [OBS Expander](https://obsproject.com/kb/expander-filter)
belgesindeki 10 ms RMS ve yumuşak geçiş yaklaşımı ile
[ReaGate kılavuzundaki](https://www.reaper.fm/guides/ReaEffectsGuide.pdf)
hold/release/histerezis davranışları incelendi. Yukarıdaki süre ve otomatik
gürültü marjı bu uygulama için seçildi; başka bir ürünün preset'i kopyalanmadı.

Durdurma işareti worker'a iletilir. İleri/GPU çağrısı durmaya yanıt vermiyorsa
denetleyici 1,5 saniye sonra kendi worker işlem grubunu sonlandırır; bu akışta
kaydedilecek checkpoint veya ses çıktısı yoktur. Son UI callback'i sonrasında
işlem kilidi bırakılır. Native tamponlar reset/unprepare tamamlanmadan
serbest bırakılmaz. Fiziksel aygıtlar yalnız kullanıcı başlatınca açılır.
Hazır sesi bellekte üretilir, dosyaya kaydedilmez ve RVC modelinden geçirilmez.

Windows aygıt sözleşmeleri Microsoft'un [waveInOpen](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveinopen),
[WAVEHDR](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-wavehdr),
[waveInAddBuffer](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveinaddbuffer),
[waveOutWrite](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutwrite)
ve [waveOutReset](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutreset)
belgelerine dayanır. Ek ses paketi veya üçüncü taraf capture DLL'i eklenmedi.
Gerçek açılan aygıt [waveOutGetID](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutgetid)
ve [waveInGetID](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveingetid)
ile doğrulanır.

## Doğrulama

`test/test_live_cover.py`: seçenek doğrulama, ABI/tampon sahipliği, sonlu ses,
aynı zaman aralığında crossfade, kuyruk sınırı, yavaş dönüşüm, model/index'in
bir defa yüklenmesi ve hata/durdurma temizliği. Fiziksel ses aygıtları taklit edilir.

`test/test_live_cover_ui.py`: beş sekme sırası, Ayarlar/model ekleme navigasyonu,
Türkçe ondalık, ayar snapshot'ı, model yenileme ve işlem kilidinin UI sonuna
kadar tutulması. `test/test_audio_service.py` gerçek ayrı fixture sürecinde
yanıt vermeyen canlı worker'ın normal durdurmayla kapanmasını sınar.

`test/test_live_gate.py`: tam 10 saniye, sınırlı bellek, tekil tıklamalar,
ölçüm geçerliliği, eşik marjları, histerezis ve gain zarfı. Kalibrasyonun
başarı/iptal/hata kapanışı, model/çıkış açmaması, UI başarı sırası ve yanlış
mikrofonda eski profilin kullanılmaması da regresyonlarla sınanır.

26 Ekim yenilemesinin kaynağında CPU ve CUDA ortamlarında ayrı ayrı **472 test**
geçti; fiziksel donanımla yayın preflight, pip check, iki frozen EXE ve temiz
Windows kurulum kabulü de başarılıdır. Güncel kayıtlar `build/release_20261026/`,
internet üzerinden izlenebilen kanıtlar [Son durum](SON_DURUM.md) içindedir.
Paket self-test'i yeni canlı modüllerin yüklenmesini, çok düşük eşiği,
sentetik 10 saniye ölçümünü ve kapanışı fiziksel mikrofon/çıkış açmadan sınar.
Önceki eşik ve otomatik ölçüm regresyonları `build/gate_threshold_checks/`
ve `build/auto_gate_checks/` altındadır.
Ses eşiği ve canlı ayar
güncellemesi, kapalı eşikte sıfır model çağrısı, konuşma aralarında çıkışın
susturulması, aygıt kimliği uyuşmazlığında durma, sessiz günlük ve kaynak
Python/CUDA yönlendirmesi regresyonlarla sınandı. Line 2'nin gerçek çıkış
kimliği sessiz açılışla doğrulandı; mikrofon açılmadı ve ses gönderilmedi.

Mevcut yerel bir RVC modeliyle, model/index dosyalarının hash'leri korunarak,
mikrofon açmadan iki saniyelik sentetik sinyal dört 500 ms parçada işlendi.
CPU dönüşümü parça başına 1,50–1,64 s, NVIDIA CUDA dönüşümü 0,36–0,55 s sürdü.
Çıktı örnek sayıları ve sonluluk kontrolleri geçti. Bu yalnız bu model ve
donanımdaki işlem süresidir; mikrofondan kulağa toplam gecikme ölçümü değildir.
Ölçüm ve betik Git dışındaki `build/live_cover_checks/model_smoke.json` ve
`model_smoke.py` dosyalarındadır. Bu CPU denemesi 500 ms akışa yetişmedi;
kalite ve cihaz kendiliğinden değiştirilmedi.

Gerçek mikrofon/modelle dinleme, akustik gecikme, kalite, cihaz çıkarma/yeniden
bağlama ve NVDA/JAWS kabulü kullanıcı denemesi olarak açıktır. Bu testler
gecikmesiz ses veya gerçek donanımda sorunsuz dinleme kanıtı sayılmaz.
