# Senaryolarla ikinci kod ve mantık taraması

Tarih: 10 Ekim 2026. Kapsam: aktif masaüstü uygulaması, RVC motor API'si, model kayıtları ve indirmeleri, iş yaşam döngüsü, güncelleme ve kurulum yolları. Düzeltmeler yerel çalışma ağacındadır; yeni kurulum hazırlanmadı veya yayımlanmadı. Önceki temizlik ve kullanıcıya ait modeller korunmuştur.

## İnceleme yöntemi

Akışlar şu açılardan değerlendirildi: ilk kullanım ve tekrar kullanım; bir model ve çoklu model; bağımsız enstrümantal kol ve sıralı vokal zinciri; geçerli/geçersiz ses; iptalin başlangıç, hazırlık, dönüşüm ve sonuç aktarımındaki zamanlaması; dosya adları ve dosya kimliği; bozuk kayıt/önbellek; çevrimdışı veya kesilen ağ; worker başlatılamaması; pencere kapanışı; kaynak ve kurulu uygulama; klavye ve yerel kontrol durumları.

Bulgu ile test kanıtı ayrıdır. Sahte motor testleri dosya yönetimini ve hata akışlarını doğrular. Gerçek bağımlılık testleri sayısal işlemleri ve wx kontrollerini çalıştırır. Yerel ağırlıklarla yapılan CPU dönüşümü motor bütünleşmesini doğrular; işitsel kalite veya tüm donanımların doğrulandığı anlamına gelmez.

## Düzeltilen sorunlar

| Senaryo / tetikleyici | Önceki sorun | Mevcut davranış |
| --- | --- | --- |
| Dönüştürücü 44 bayttan büyük bozuk WAV yazar | Dosya boyutu başarı sayılması için yeterliydi; eski sonuç ezilebilirdi. | Ses çözümlenir; dolu, sonlu ve tamamıyla okunabilir örnekler doğrulanmadan sonuç aktarılmaz. |
| Ayrıştırıcı bozuk veya boş FLAC döndürür | Dosya varlığı yeterliydi. | Tutulacak stem'in ses verisi doğrulanır; eski sonuç korunur. |
| Giriş adı `song_(Vocals).wav` | İki motor çıktısı da `(Vocals)` metni içeriyordu; vokal seçimi belirsizleşiyordu. | Son stem etiketi eşleştirilir. Vokal ve enstrümantal doğru ayrılır. |
| Enstrümantal + ana vokal + arka vokal seçilir | Kol sırası kritik bir regresyon noktasıydı. | İlk iki adım orijinal girdiden, sonraki vokal adımı önceki vokal çıktısından çalışır; testle korunur. |
| Cover sürerken iptal edilir | Bitmekte olan modelin sonucu iptalden sonra eski dosyanın üzerine aktarılabiliyordu. | Mevcut çağrı döndükten sonra iptal kontrol edilir; geçici çıktı atılır ve sonraki model başlamaz. |
| `cleanup_model` veya geçici dosya silme hata verir | Kalan kuyruk durabiliyordu. | Temizleme hatası uyarı olur; diğer modeller işlenir. Dönüştürücü referansı GC öncesinde bırakılır. |
| İş tamamlanırken yeni başlangıç tetiklenir | Kilit bırakıldıktan sonra eski son durum veya UI açma çağrıları bekleyebiliyordu. | `finish_job` kilidi ana thread'deki UI tamamlanmasına kadar tutar. İç kuyruktaki yinelenen UI açma kaldırıldı. |
| Başlat düğmesi ve diğer kontroller aynı olay döngüsünde kullanılır | UI kilitleme `CallAfter` ile gecikiyordu. | `post_ui` ana thread'deyken doğrudan uygular; kontroller hemen devre dışı kalır. |
| `Thread` oluşturucusu veya `start` hata verir | Oluşturucu, kilit kurtarma kapsamının dışındaydı. | Başlatma hazırlığı tamamıyla korunur; kilit bırakılır ve UI tekrar kullanılabilir olur. |
| İş sırasında panel yolları/kayıtları değişir | Worker canlı panel verilerine bağımlıydı. | Başlangıçta alınan girdi, çıktı, model ve ayar kopyaları kullanılır. |
| Çıktı girişin başka yol veya dosya kimliğiyle aynı dosyasıdır | Yalnızca metinsel mutlak yol karşılaştırılıyordu. | `realpath` ve `samefile` ile kontrol edilir; giriş ve model dosyalarının üzerine çıktı yazılmaz. |
| Model farklı bilgisayardan taşınır, aynı adlı iki ağırlık bulunur | İlk bulunan dosya rastgele seçilebiliyordu; dizin de dosya sayılabiliyordu. | Yalnızca dosyalar kabul edilir; belirsizlikte tam yol istenir. Bir modelin hatası diğerlerini engellemez. |
| Seçilen ses modeli mevcut değildir | Yardımcı model indirmeleri gereksiz yere başlayabiliyordu. | Ses ağırlığı kontrolü hazırlıktan önce yapılır. |
| Eski kayıt taşınırken yol/izin hatası olur | Hata, kayıt okuma/yazma yakalayıcısının dışında kalıyordu. | Yol çözümü ve atomik kopyalama hata kapsamına alındı; kayıt korunur, hata bildirilir. |
| Yerel model kopyası disk dolduğu için yarım kalır | Nihai model adında eksik kopya kalabiliyordu. | `.part` dosyasına kopyalanır; tamamlandıktan sonra değiştirilir. |
| RMVPE indirmesi yarıda kesilir veya iptal edilir | `urlretrieve` zaman aşımı/uzunluk/iptal sözleşmesini karşılamıyordu. | Ortak atomik indirme yordamı, timeout, uzunluk ve iptal kontrolü kullanılır. |
| Varsayılan cihaz CUDA, bilgisayarda CUDA yok | Kullanıcı ilk denemede gereksiz cihaz hatası alıyordu. | GUI kullanılabilirliğe göre CPU seçer; açıkça istenen kullanılamayan CUDA hâlâ hata üretir. |
| Autotune, sessiz F0 örnekleri ve pitch birlikte kullanılır | Sessizlik düşük notaya çevriliyordu; pitch kaydırması atlanıyordu. | Sessizlik sıfırda kalır, pitch autotune sonrasında uygulanır. |
| F0 ve içerik özellikleri farklı uzunluktadır | Pitch koruma harmanlamasında tensör boyutları çakışabiliyordu. | F0 konturu uygun uzunluğa getirilir; özellik/F0 uzunlukları eşitlenir. |
| FAISS vektörü NaN içerir veya farklı boyuttadır | Sonlu mesafe kontrolü tek başına yeterli değildi; özellikler bozulabiliyordu. | Bozuk komşu vektörler dışlanır; uyumsuz boyut açık hata verir. |
| Aynı dönüştürücüde farklı `resample_sr` değerleriyle tekrar çağrı | Model hedef hızı değiştiriliyor; ses yeniden örneklenmeden yanlış hızla etiketleniyordu. | Çıktı yeniden örneklenir; model/pipeline hızları sabit kalır. |
| Uzun/kısa dönüştürülmüş parçalar yeniden birleştirilir | Fazla uzunluk daha da büyüyordu; sondaki sessizlik kayboluyordu. | Parçalar orijinal zaman çizelgesine yerleştirilir; fazla bölüm kırpılır, eksik bölüm ve sessizlik korunur. Tam sessiz girdi de desteklenir. |
| Format dönüşümü stereo girdi alır veya hata verir | Mono yükleme, gereksiz örnekleme hızı değişimi ve yutulan hata vardı. | Kanal sayısı/hız korunur; format hatası çağırana iletilir. Çıktı uzantısı yalnızca son uzantıdan üretilir. |
| Yeni checkpoint yüklenemez veya ağırlıklar eksiktir | Önceki model kimliği/nesneleri kalabiliyordu; eksik parametreler rastgele ağda sessizce kalabiliyordu. | Eski durum önce temizlenir; sürüm/config/vocoder ve eksik ağ parametreleri doğrulanır; başarısızlık sonrası yüklenmiş model işareti kalmaz. |
| Custom embedder bulunamaz | Varsayılan modele dönülüyor fakat eksik varsayılan dosyalar hazırlanmıyordu. | ContentVec hazırlık/indirme yoluna geçilir. Boş yardımcı dosya da hazır model sayılmaz. |
| Model listesi yenilenir veya oklarla uzun listede dolaşılır | Önceki seçimler kayboluyordu; odaktaki model görünür alana kaydırılmıyordu. | Seçimler korunur; odaklanan öğe görünür alana alınır. |
| Motor `%100` üstünde ilerleme yazar | Gauge aralığı dışına çıkılabiliyordu. | UI yüzdesi 0–100 arasında sınırlandırılır. |
| F5 tekrar tekrar basılır; sunucu `{}` veya bozuk sürüm döndürür | Çakışan kontroller/diyaloglar; bozuk kayıt “güncel” sayılabiliyordu. | Tek kontrol kilidi ve katı metadata doğrulaması vardır. Sondaki sıfır sürüm parçaları normalize edilir. |
| Setup indirmesinde `Content-Length` yoktur | İndirme sırasında iptal durumu kontrol edilmek üzere UI'a aktarılmıyordu. | Bilinmeyen uzunlukta `Pulse` kullanılır; iptal indirme döngüsüne aktarılır. |
| Güncelleme sırasında ses işlemi başlatılır veya thread başlayamaz | Güncelleme aynı iş koordinasyonunda değildi; geçici dosya/kilit kalabiliyordu. | İndirme ortak kilidi tutar. Başlatma hatası temp dizinini temizler ve kilidi bırakır. |
| Pencere kapanır, ardından bekleyen UI bildirimi gelir | Açılış callback'leri pencere ömrü kontrolü olmadan çalışabiliyordu. | Açılış dahil bildirimler yaşayan pencereye gönderilir. Gerçek wx pencere silme davranışı test edilmiştir. |
| Paketli uygulamanın simgesi/kurulum kısayolu | PyInstaller içindeki simge EXE yanındaymış gibi aranıyordu. | Pencere simgesi kaynak dizininden, kurulum kısayolu simgesi EXE'den alınır. |
| Desktop yönlendirilmiştir veya crash log yazılamaz | Hata bildirimi de günlük yazma hatasıyla kaybolabiliyordu. | Günlük kullanıcı veri dizinindedir; yazma başarısızlığı asıl hata bildirimini engellemez. |

## Model klasörü: kullanıcının son tercihi

İndirilen modeller **programın kurulu olduğu yerdeki `models/`** dizinine gider:

```text
Kurulum dizini/
  Ghostkiller_Sound_Cleaner_V2.exe
  models/
    <ayrıştırma ağırlıkları ve JSON/YAML yardımcıları>
    predictors/rmvpe.pt
    embedders/contentvec/{config.json,pytorch_model.bin}
```

Kaynak çalışmada aynı düzen proje kökünde kullanılır. `models/` Git tarafından her seviyede dışlanır; kişisel modeller setup girdisi değildir. Inno Setup model klasörünü `users-modify` izniyle oluşturur; uygulamanın diğer klasörlerinin izinleri genişletilmez. Eski `modeller/` ve `rvc/models/` dosyaları silinmez, gerektiğinde yeni konuma atomik kopyalanır. `models.json` kişisel kayıtlarının yeri ayrı kalır: kaynakta kök, kurulu sürümde kullanıcı veri dizini.

## Doğrulama ve sınırlar

- Son otomatik kontrol: **55/55 test başarılı**. Python sözdizimi ve `git diff --check` kontrolü hatasızdır.
- Test komutu: `python -m unittest discover -s test -v`. Testler `test/` altındadır; ağırlık indirme ve gerçek Setup başlatma testlerde yapılmaz.
- Motor matematiği gerçek NumPy/SciPy/librosa/PyTorch ile, arayüz davranışı gerçek görünmeyen wxPython pencereleriyle kontrol edilir. Dosya kimliği testi, sandbox Windows hard link oluşturmayı reddettiği için `samefile` cevabını taklit eder; fiziksel hard link oluşturulduğu iddia edilmez.
- Bir saniyelik sentetik 220 Hz ses mevcut yerel ağırlıklarla CPU/RMVPE üzerinden dönüştürüldü. İnternet çağrıları yasaklandı. Yeni `resample_sr=32000` yolu **32 kHz / 31.360 sonlu örnek / 0,98 saniye** çıktı verdi. Test, büyük önbellekleri çoğaltmamak için eski yerel yardımcı model dizinini okuyarak çalıştı; yeni dizin sözleşmesi ayrıca otomatik yol/indirme testleriyle kontrol edildi.
- Kullanıcı ses dosyaları veya model ağırlıkları değiştirilmedi; geçici sesler temizlendi. Git ignore kontrolü yeni `models/` altındaki config ve ağırlıkları da dışladığını doğruladı.
- NVDA/JAWS anonsları, CUDA üzerinde uçtan uca dönüşüm, gerçek şarkılarda kalite ve tüm ayrıştırma modellerinin gerçek sesi bu turda doğrulanmadı.
- Yeni PyInstaller/Inno Setup derlemesi ve temiz normal kullanıcı hesabında kurulum/ACL kontrolü yapılmadı. Tanımdaki klasör izni kurulumun çalıştırılıp doğrulandığı anlamına gelmez.
- Ses kütüphanesinin çalışan çağrısı zorla kesilmez. Ağda devam eden tek okuma çağrısı timeout'a kadar sürebilir. Embedder hazırlığı ve büyük yerel kopya bitene kadar iptal bekleyebilir.
- Updater HTTPS, dosya uzunluğu ve EXE başlığı kontrol eder; yayımlanmış manifestte doğrulanmış SHA-256/imza kontrolü yoktur. Bağımlılık sürümleri/CI henüz sabitlenmemiştir. Çok uzun Windows yolları ve tüm yüksek DPI/odak senaryoları ayrıca ürün testi gerektirir.
