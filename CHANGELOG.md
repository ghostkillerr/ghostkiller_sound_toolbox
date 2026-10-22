# Sürüm notları

Ghostkiller Sound Toolbox'ın kullanıcıya yansıyan önemli değişiklikleri burada
toplanır. Küçük teknik düzeltmeler ilgili özelliğin altında birleştirilir.

## Yayımlanmamış kaynak değişiklikleri

- **Güvenli eğitim temizliği:** başarısız fakat devam edilebilir bağlı eğitimler,
  oturum içindeki özgün/test kayıtları ve AI Cover listesinin kullandığı dosyalar
  temizliği engeller. Yarım kalan temizlik ayrı durumla gösterilir ve yeniden
  denenebilir; temizlenen oturum yanlışlıkla eğitime devam ettirilemez.
- **Eğitim oturumu sahipliği:** devam kontrolü çalışan oturumun ayarlarını
  değiştirmez; iptal işaretini yalnız oturum kilidini alan denetleyici yönetir.
- **Model indirme sınırları:** JSON/YAML için 1 MiB, model dosyası için 4 GiB
  üst sınır uygulanır. Boyutu bildirilmemiş indirmelerde de disk boşluğu
  kontrol edilir; başarısız indirme önceki dosyayı değiştirmez.
- **Doğru model ve cihaz:** RVC seçilen index yolunu ad benzerliğine göre
  başka bir dosyaya çevirmez. ONNX ayrıştırması seçilen CUDA kartının numarasını
  da alır; çok kartlı sistemde varsayılan karta yönelmesi giderildi.
- **RVC çıktı hassasiyeti:** ara WAV sesi artık float saklanır; AI Cover ve
  eğitim dinleme örnekleri kullanıcıya WAV/FLAC kaydedilirken önce 16 bite düşmez.
- **Canlı AI Cover:** deneysel 4. sekmede kayıtlı ses modeli, mikrofon ve kulaklık
  seçimi, perde/benzerlik/dinleme düzeyi, parça süresi ve başlat/durdur kontrolleri.
  Bellekte dönüşüm, sınırlı ses kuyruğu ve tahmini gecikme bildirimi eklendi.
  Gerçek mikrofon ve donanımla ses/gecikme kabulü henüz tamamlanmadı.
- **Sekme sırası:** Ayarlar 5. sekmeye taşındı.
- **Canlı ses eşiği:** varsayılan -45 dB; dinlerken ayarlanabilir. Eşik altındaki
  parçalarda model çalışmaz; çıkış sessiz kalır. Günlükte tekrarlayan ilerleme
  satırları kaldırıldı; yalnız mikrofon açılışı bir kez bildirilir.
- **Otomatik gate ayarı:** seçili mikrofonu konuşmadan 10 saniye ölçüp açılma ve
  kapanma eşiklerini ortam gürültüsüne göre ayarlar. Ölçüm sonunda mikrofon kapanır
  ve **Ayarlandı** görünür; dinleme ayrıca başlatılır. Ayrı eşikler, 5 ms açılma,
  150 ms bekleme ve 120 ms yumuşak kapanma konuşma sonlarının kesilmesini azaltır.
  İptal, değişken/yüksek gürültü veya sessizdeki mikrofonda önceki eşik korunur.
- **Gate eşik girişi ve sonuç:** -80 dB alt sınırı kaldırıldı; daha düşük ve
  ondalıklı değerler doğrudan yazılabilir. Başarılı otomatik ölçümde mikrofon
  kapandıktan sonra **Dinleme tamamlandı** sonuç penceresi açılır.
- **Canlı aygıt seçimi:** seçilen öğe aygıt kimliğini taşır; açılan giriş/çıkış
  adı ve numarası doğrulanır. Eksik aygıtta varsayılana geçilmez; doğrulanmış yol
  ekranda gösterilir. Model hazırlığı ve aygıt açılışı tamamlanınca seçilen
  çıkıştan kısa bir hazır sesi çalınır. Sistem Python'uyla açılan kaynak,
  kayıtlı GPU tercihini hazır yerel CUDA ortamıyla karşılar.
- **Ekran okuyucu seçim durumları:** işlem, enstrüman ve model seçimleri NVDA/
  JAWS'a basılı düğme yerine onay kutusu olarak sunulur. İşaretli/işaretsiz
  durumu kontrolün gerçek değeriyle birlikte değişir; normal onay kutuları da
  aynı canlı durum sözleşmesini kullanır.
- **Düzenli eğitim çıktıları:** kayıt aralığı ve tutulacak son epoch modeli sayısı
  ana eğitim ekranında açıkça seçilir. En yeni istenen sayı kadar model, model
  adına ait temiz klasöre `Ad_Epoch_010.pth` biçiminde kaydedilir ve tek bir
  `Ad.index` paylaşır; mevcut klasörler numaralanarak korunur.
- **Daha sade eğitim ekranı:** devam, sonuç, ek epoch, önceki eğitimden başlatma
  ve geçmiş işlemleri **Eğitim oturumlarım** altında bağlama göre sunulur. Ayar
  karşılaştırması gelişmiş bölüme taşındı; teknik oturum klasörü tamamlanınca
  kendiliğinden açılmaz.
- **Eğitim diski temizliği:** kalıcı epoch modelleri kaydedilirken teknik oturumun
  boyutu gösterilir ve önerilen temizlik onayı sunulur. Onaydan sonra checkpoint,
  hazırlanmış parçalar/özellikler ve test sesleri silinir; özgün kayıtlarla kalıcı
  modeller korunur. Tamamlanan oturumlar daha sonra oturum menüsünden de
  temizlenebilir; yarım veya bağımlı eğitimler sessizce silinmez.

## 2.1.0 — 18 Ekim 2026

Windows x64 için CPU ve NVIDIA CUDA kurulumları [GitHub Release'te](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/tag/v2.1.0)
yayımlandı. Her iki kurulumun SHA-256 değerleri, boyutları ve derleme kayıtları
yayında bulunur. Kurulum dosyaları henüz dijital yayıncı sertifikasıyla imzalanmamıştır.

### Ses araçları ve model eğitimi

- **Sonuçları koruma:** ses adlarındaki Ghostkiller eki kaldırıldı. Aynı ad
  varsa yeni dosya/klasör numaralanır; eski sonucun üzerine yazılmaz. İşlem
  sonucu mesajı kapatılınca sonuç klasörü açılır.
- **Daha kolay hazırlık:** eksik model düğmesi yalnız gerektiğinde görünür ve
  seçili işlemin modellerini hazırlar. Biçim/kanal/donanım özeti, çözüm öneren
  hata mesajları, Türkçe ondalık girişi, indirme boyutu ve yarım indirme desteği eklendi.
- **Ortak ses dosyası biçimi:** Ayarlar'dan seçilen MP3, WAV, FLAC veya OGG;
  vokal temizleme, enstrüman ayırma, AI Cover ve eğitim test seslerine uygulanır.
  Aynı yerden mono veya stereo kayıt seçilebilir. Enstrüman sonuçlarının yanına
  JSON raporu yazılmaz.
- **Enstrümanları ayrı kaydetme:** dört kanallı SCNet ve bilimsel kullanım
  koşullarına tabi deneysel altı kanallı HTDemucs ile ayrı stereo ses
  çıktıları. Gitar/piyano kalitesi deneyseldir; ses seviyesi düzenleme ekranı içermez.
- **İsteğe bağlı kısa vokal onarımı:** arka vokal temizliğinde kaybolan kısa
  bölümler A2SB ile ayrıca onarılabilir. Standart ve onarılmış sonuçlar
  ayrı kaydedilir. Özellik varsayılan kapalıdır; model araştırma/değerlendirme
  içindir. [Kullanım ve sınırlar](docs/VOKAL_ONARIMI.md).
- **Eğitim verisini önceden inceleme:** kayıtları dinleyin, kullanılacak bölümü
  belirleyin ve gerçek eğitim/kontrol dağılımını eğitim başlamadan görün.
- **Sonuçları karşılaştırma:** sınırlı ara model arşivi, ortak test kayıtları,
  index açık/kapalı dinleme, tercih/not ve erişilebilir değerlendirme geçmişi.
- **Eğitim denemelerini yönetme:** oturum listesi ve ayar karşılaştırması,
  kişisel ayar şablonları, sıralı deneyler ve doğrulanmış hazırlığı yeniden kullanma.
  Mevcut eğitime ek epoch veya önceki eğitimden ayrı yeni oturum başlatılabilir.

- **Vokal ve müzik ayrıştırma:** ana vokal, enstrümantal, arka vokal, yankı ve
  gürültü temizleme adımları aynı iş akışında kullanılabilir.
- **Yerel RVC ile ses değiştirme:** kişisel ses modeli ve isteğe bağlı index
  dosyası eklenebilir. Pitch, index ve perde işlemlerinin hata denetimleri
  geliştirildi; ses dosyaları yerel işlenir.
- **RVC V2 model eğitimi:** kayıt hazırlama ve analiz, eğitim, durdurma/devam,
  değerlendirme ve index oluşturma tek sekmede toplandı. Eğitilen model ses
  değiştirmede kullanılabilir.

### Kullanım ve güvenilirlik

- **İptal ve disk temizliği:** kayıt incelemesinin son dosya kontrolü iptali
  dikkate alır. Enstrüman ayırmada zorla durdurma veya worker çöküşü sonrası
  geçici dosyalar temizlenir; tamamlanmış sonuçlar korunur.
- **Model kullanım koşulları:** A2SB ve altı kanallı HTDemucs için kullanım
  sınırları indirmeden ve çalıştırmadan önce açıklanır. Üreticinin koşulları
  açılabilir; kabul edilmeden işlem başlamaz.
- **Ortak model ve donanım yönetimi:** işlemci/ekran kartı seçimi, eksik modelleri
  indirme, çevrimdışı dosya kontrolü ve bozuk dosyaları onarma Ayarlar'da toplandı.
  Eğitim ve isteğe bağlı vokal onarımı modelleri kendiliğinden seçilmez;
  kullanıcı gerektiğinde ayrıca seçer. Durum yenileme mevcut seçimleri korur.
- **Erişilebilir arayüz:** Türkçe native kontroller, klavye ile gezinme ve eğitim
  alanlarının açıklamaları düzenlendi. Enstrüman kanal düğmeleri de vokal
  işlemedeki gibi açık ve kapalı durumu adlarında bildirir.
  Açık/koyu görünüm tercihi kalıcı saklanır.
- **Daha dayanıklı işlemler:** ses ve eğitim işleri ayrı süreçlerde çalışır;
  hata ve iptal durumlarında önceki başarılı çıktılar ve kişisel veriler korunur.

### Kurulum ve güncellemeler

- **İki Windows x64 paketi:** CPU ve NVIDIA CUDA ayrı hazırlanır. Python,
  FFmpeg, uygulama ikonu, kullanım sözleşmesi ve bağımlılık lisansları paketlenir.
- **Program içinden güncelleme:** kurulu uygulama açılışta varsayılan olarak
  geliştirici bilgi penceresinden önce denetler; yeni sürüm varsa indirme onayı
  ister. Evet denildiğinde doğrulanmış güncellemeyi aynı klasöre uygular.
  Hayır veya iptal ile normal açılış devam eder. Otomatik denetim
  Ayarlar'dan kapatılabilir; elle denetleme düğmesi ve F5 kullanılabilir.
  Güncelleme kişisel model ve ayarları korur; Windows yönetici izni isteyebilir.
- **Tanıtım ve indirme sayfası:** programın özellikleri, paket seçimi ve ilk
  kullanım bilgileri [proje sitesinde](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/)
  yer alır. CPU ve CUDA indirme bağlantıları açıktır.

İki ortamda 363 kaynak testi, yerel frozen testleri ve GitHub Windows üzerinde
kurulum/yeniden kurulum/kaldırma testleri geçti. CUDA paketi gerçek NVIDIA
kartında da sınandı. Gerçek ses kalitesi, uzun eğitim, canlı NVDA/JAWS ve
etkileşimli UAC/güncelleme kabulü ayrı kullanıcı denemeleriyle sürmektedir.

## Önemli geliştirme aşamaları

Bu tarihler kaynak geliştirme aşamalarını gösterir; ayrı dağıtım sürümleri veya
yayımlanmış güncellemeler değildir. Küçük düzeltmeler ve tekrar eden arayüz
çalışmaları ilgili aşamada birleştirilmiştir.

| Tarih | Kayda değer gelişme |
| --- | --- |
| 2–3 Ağustos 2026 | Modüler ses ayrıştırma ve gömülü RVC dönüşümünün temeli; pitch/index düzeltmeleri ve ses işleme iyileştirmeleri. |
| 8–11 Ekim 2026 | Ortak Ayarlar, donanım ve model yönetimi; erişilebilir model seçimi, güvenli iptal ve yerel verilerin paketlerden ayrılması. |
| 13 Ekim 2026 | Uygulama içi RVC V2 eğitimi, ayrı ses/eğitim süreçleri, model bütünlüğü denetimleri ve doğrulanan yayın paketlerinin altyapısı. |
| 14 Ekim 2026 | Açık/koyu görünüm ve eğitim erişilebilirliği; bağımsız CPU/CUDA kurulum hazırlığı, program içinden güncelleme ve GitHub tanıtım sayfası. |

## Sonraki yayınlar

Her kod değişikliği ayrı bir sürüm oluşturmaz. Birbiriyle ilgili geliştirmeler
test edilen tek sürümde toplanır. Her yayımlanmış sürüm için gerçek tarih,
kullanıcıya etkisi olan kısa yenilik/düzeltme listesi ve iki kurulum bağlantısı
eklenir. Ayrıntılı derleme ve yayın adımları [oku.md](oku.md) dosyasındadır;
indirilebilir sürümlerin kaydı [GitHub Releases](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases)
sayfasıdır.
