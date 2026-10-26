# Kullanılabilirlik incelemesi — 25 Ekim 2026

## Düzeltme durumu — 26 Ekim 2.1.0 paketleri

Kullanıcının “hepsini düzelt” isteğiyle aşağıdaki 15 bulgu için kaynak kodu ve
ilgili kullanım belgeleri güncellendi. Aşağıdaki eski gözlemler ilk incelemenin
kanıtı olarak korunmuştur; düzeltilmiş ekranların güncel tarifi değildir.

| Bulgu | Uygulanan değişiklik |
| --- | --- |
| 1 | Seçili adayı kaydetme; toplu kayıtta notla tercih edilen adayı koruma; oturumu varsayılan saklama; kaydedilmemiş tercihte temizliği engelleme. |
| 2 | Koyu temayı izleyen native radyo seçenekleri; normal/üzerine gelinen düğmelerde sistemin okunur yazı ve zemin renkleri. |
| 3 | Vokal girdisi ve otomatik miksleme yapılmadığı açıklaması; ayrıştırma sonucunu AI Cover’a aktarma. |
| 4 | Sabit başlat/durdur/durum alanı; F6 ile doğrudan erişim; canlı teknik ayarların gelişmiş bölüme alınması. |
| 5 | Standart dört çıkışın varsayılan olması; altı çıkışın adında deneysel/gitar/piyano açıklaması. |
| 6 | İndirme öncesi boyut ve onay; bilinmeyen boyut açıklaması; dosya/seçimleri koruyarak işe dönüş. |
| 7 | Kaydedilecek çıktılar ve isteğe bağlı temizlik ayrımı; seçime göre vokal zinciri/ayrı enstrümantal özeti. |
| 8 | Eksik form gereksinimlerinin durum alanında gösterilmesi ve ilgili alana odak; boş eğitimde kullanılamayan eylemlerin kapanması. |
| 9 | Her iki cover ekranından tek model ekleme formu; ad/PTH/isteğe bağlı index ve açık vazgeçme davranışı. |
| 10 | Model araması, daha yüksek liste, seçili sayısı; kayıt kaldırmanın dönüşüm seçiminden ayrılması; Hazır ile bakım seçiminin açıklanması. |
| 11 | Yarım ses, artı/eksi yönü ve index katkısının açıklanması; canlı otomatik ölçümün temel görünümde kalması. |
| 12 | Yalnız yayımlanmış sonuçların listelenmesi; son vokal işareti, dinleme, klasör ve aktarım; tamamlanmış aşamaların hata/iptalde korunması. |
| 13 | Çevrimdışı F1/ekran yardımı ve ilk kullanım rehberi; eski paket/erişilebilirlik ifadelerinin güncellenmesi. |
| 14 | Hakkında alanında kopyalanabilir kaynak/paket bilgisi; yeni derleme metadata’sında UTC tarihi; backend ve kaynak hash’i. |
| 15 | Açılış bilgi penceresinin kaldırılması; katlanabilir günlükler, gereksinim odaklı durum ve belirgin ana eylem. |

**Doğrulama:** CPU ve CUDA ortamlarında ayrı ayrı 472 test; iki ortamın
`pip check` ve release preflight kontrolleri başarılı. 14 yeni regresyon;
tercih edilen model/veri koruması, indirme onayı ve kilit sırası, görev dönüşü,
sonuç aktarımı, model formu/araması, koyu tema, gelişmiş alanlar ve başlangıçta
alt alanın kesilmemesi gibi davranışları kapsar. Native yerleşim testi
800×850, 680×600 ve 1000×700 pencerelerde beş sekmeyi kontrol eder.

İlk görsel kontrolde saptanan alt durum alanının kesilmesi ayrıca düzeltildi.
Devam eden bilgisayar kontrolü kullanıcı tarafından Escape ile durduruldu;
son değişikliklerin etkileşimli görsel tekrarı tamamlanmadı. NVDA/JAWS anonsu,
%125/%150 Windows ölçekleri ve gerçek sesle kullanım kabulü ayrıca yapılmalıdır.
Otomatik kontroller bu kabullerin yerine geçmez.

**Dağıtım — 26 Ekim:** Sürüm 2.1.0 korundu. Yeni CPU/CUDA setup’ları,
GitHub kaynakları ve indirme sayfaları güncellendi. Önceki 2.1.0 kullanıcıları
aynı paketi indirip elle yeniden kurmalıdır. [Güncel kullanım](ARAYUZ_KULLANIMI.md) ·
[Güncel kanıt](SON_DURUM.md).

## İlk incelemenin değerlendirmesi


**Genel değerlendirme:** Programın yetenekleri geniş, fakat kullanıcıya çoğunlukla ayar ve işlem listeleri sunuluyor. İlk kez kullanan kişinin asıl soruları olan “Hangisini seçmeliyim?”, “Bunun sonunda ne elde edeceğim?” ve “Şimdi ne yapacağım?” her ekranda yeterince cevaplanmıyor. Öncelik yeni özellik eklemekten önce mevcut işlemleri anlaşılır bir akışa dönüştürmek olmalı.

Bu bir kullanılabilirlik incelemesidir; gerçek kullanıcılarla yapılmış bir araştırma veya ses kalitesi testi değildir. Aşağıdaki kullanıcı tepkileri, gözlenen arayüz ve kaynak kodundan çıkarılan olası kullanım güçlükleridir.

## İnceleme kapsamı

- Yerel kaynak: `dec3ace`; pencere başlığındaki sürüm: **2.1.0**.
- `oku.md`, `docs/SON_DURUM.md`, ana README, belge dizini ve kullanım belgeleri okundu. Eğitim, canlı dinleme, enstrüman ayırma, vokal onarımı, donanım/model hazırlama ve kullanıcı kabulü açıklamaları ilgili UI koduyla karşılaştırıldı. Sürüm notları ve ilgili teknik inceleme bölümleri de değerlendirildi.
- Hazır CUDA Python ortamıyla gerçek wxPython uygulaması açıldı. Beş sekme, enstrüman görünümü, sayfaların alt bölümleri, başlangıç mesajı ve boş AI Cover formundaki Başlat davranışı incelendi.
- Görsel bulgular mevcut **koyu temada**, programın varsayılan **800 × 850** pencere boyutuna ilişkindir. Açık tema, farklı DPI değerleri ve farklı ekran çözünürlükleri ayrıca denenmedi.
- Ses dönüştürme, eğitim, model indirme ve mikrofon ölçümü başlatılmadı. Eksik model ve eğitim sonucu akışları kaynak kodundan değerlendirildi; bunlar bu oturumda uçtan uca denenmiş gibi sunulmadı.
- NVDA/JAWS konuşması dinlenmedi. Windows erişilebilirlik ağacı incelendi; bu, ekran okuyucu kabulünün yerine geçmez.
- Uygulama kodu değiştirilmedi. İnceleme için açılan uygulama kapatıldı. `settings.json` ve `models.json` inceleme başı/sonunda aynı SHA-256 değerlerine sahipti.

**Öncelikler:** P1: İlk düzeltme turuna alınmalı; yanlış karar, önemli kullanım engeli veya tercih edilen sonucun kaybı riski var. P2: Akışı belirgin biçimde iyileştirir. P3: Daha küçük sunum ve tutarlılık iyileştirmesi.

## Öncelik tablosu

| No | Öncelik | Sorun | Kanıt türü |
| --- | --- | --- | --- |
| 1 | P1 | Eğitimde tercih edilen aday ile kalıcı kaydedilen modeller aynı şey değil | Kod ve belge |
| 2 | P1 | Koyu temada bazı önemli seçenekler zor okunuyor | Gerçek ekran |
| 3 | P1 | AI Cover için nasıl bir ses dosyası gerektiği açık değil | Ekran ve kod |
| 4 | P1 | Eğitim ve canlı dinlemede ana eylem uzun formun altında | Gerçek ekran |
| 5 | P1 | Deneysel altı kanallı ayırma varsayılan ve “Ayrıntılı” diye sunuluyor | Ekran ve kod |
| 6 | P1 | İlk kullanımın model hazırlama akışı kullanıcının görevinden kopuyor | Kod ve belge |
| 7 | P2 | Vokal ekranında çıktı seçimi ile temizleme zinciri birbirine karışıyor | Ekran ve kod |
| 8 | P2 | Eksik seçimler ancak Başlat'a basınca hata oluyor | Gerçek etkileşim ve kod |
| 9 | P2 | Ses modeli ekleme, teknik dosyalar ve ayrı pencereler gerektiriyor | Kod |
| 10 | P2 | Model listeleri hem seçim hem yönetim amacıyla kullanılıyor | Ekran ve kod |
| 11 | P2 | Sayısal ses ayarları neyi değiştirdiklerini yeterince anlatmıyor | Ekran ve kod |
| 12 | P2 | Sonuçlar dosya yöneticisine bırakılıyor; sonraki adım eksik | Kod |
| 13 | P2 | Yardım belgeleri uygulamanın içinden keşfedilemiyor; bazıları eski durum anlatıyor | Ekran, kod ve belge |
| 14 | P2 | Aynı 2.1.0 adı farklı özellik setlerini ayırt etmiyor | Belge ve kod |
| 15 | P3 | Her açılıştaki bilgi penceresi ve tekrarlanan durum alanları gereksiz yük | Ekran ve kod |

## Bulgular ve yapılması gerekenler

### 1. Eğitimde “beğendiğim modeli kaydettim” beklentisi karşılanmayabilir — P1

Sonuç ekranında kullanıcı **“Kontrol hatası en düşük model”** gibi bir adayı dinleyebiliyor ve **“Seçili modeli tercih et ve oturum notu yaz”** diyebiliyor. Ancak kalıcı kayıt düğmesi seçili adayı değil, tutulan epoch modellerinin tamamını kaydediyor. `register_models`, epoch bilgisi olan kayıtları topluyor; karşılaştırmanın `best_validation.pth` kaydı bu bilgiyle oluşturulmuyor. Tek adayı kaydetme işlevi backend'de var, fakat bu düğmeye bağlı değil.

Somut risk: Kullanıcının beğendiği en düşük kontrol hatalı model, tutulan son epoch modellerinden farklı olabilir. Kullanıcı epoch modellerini kaydedip önerilen teknik temizliğe **Evet** derse bu beğendiği aday teknik oturumla birlikte kaldırılabilir. Dosya koruma mekanizmalarının çalışması, kullanıcının tercih ettiği adayın korunacağı anlamına gelmiyor. Bu senaryo kaynak akışından saptandı; kişisel bir eğitim üzerinde silme denenmedi.

**Yapılacak:** “Seçili modeli kalıcı kaydet” ile “Tutulan epoch modellerini topluca kaydet” ayrı eylemler olmalı. Toplu kayıt ve ortak index düzeni korunmalı. Temizlikten önce hangi adayların kalıcı kaydedildiği açıkça gösterilmeli; tercih edilen aday kalıcı değilse bunun kaydı teklif edilmeli. “Evet/Hayır” yerine “Eğitime devam edebilmek için sakla” ve “Çalışma dosyalarını sil, devam olanağını kaldır” gibi sonuç belirten seçenekler kullanılmalı. Varsayılan silme kararı yeniden değerlendirilmeli.

**Kabul ölçütü:** Son epoch arşivinde bulunmayan bir `best_validation` adayı tercih edildiğinde kullanıcı bu adayı kalıcı saklayabilmeli; temizlikten sonra AI Cover'da aynı ağırlık kullanılabilmeli.

Kaynak: `ui_training.py:191`, `ui_training.py:661`, `ui_training.py:675`, `ui_training.py:880`; `training/comparison.py:63`; `training/service.py:290`, `training/service.py:334`.

### 2. Koyu temada donanım ve görünüm seçeneklerinin kontrastı yetersiz — P1

Ayarlar'daki **Açık mod / Koyu mod** ve **İşlemci / Ekran kartı** radyo seçeneklerinin yazıları koyu zemin üzerinde siyah göründü. Seçim işareti görülebiliyor fakat etiketleri okumak güç. Diğer metin alanlarının açık renk olması bu tutarsızlığı artırıyor. Dosya seçme düğmesinin bir üzerine gelme durumunda da açık zemin üzerinde açık yazı görüldü; bunun odak/üzerine gelme durumlarında ayrıca doğrulanması gerekir.

**Yapılacak:** Native radyo düğmeleri dahil bütün etkileşim durumlarının renkleri gözden geçirilmeli. Seçili, seçili değil, odaklı, üzerine gelinmiş ve devre dışı durumlar ayırt edilebilmeli. Yalnız üst kapsayıcıya renk uygulamak yeterli kabul edilmemeli.

**Kabul ölçütü:** İki tema ve Windows yüksek karşıtlık görünümünde metinler okunmalı; hangi donanımın seçildiği renk ayırt etmeye gerek kalmadan anlaşılmalı.

Kaynak: `ui_settings.py:32`, `ui_settings.py:68`; `ui_common.py` içindeki `apply_native_style`.

### 3. AI Cover ekranı tam şarkı mı, yalnız vokal mi istediğini açıklamıyor — P1

Ana ekran **“Bir ses modeli ve kayıt seçin”**, düğme **“Ses dosyası seç”** diyor. Dosya penceresi ise **“Kılavuz Vokal Dosyasını Seçin”** başlığını kullanıyor. Normal kullanıcı “AI Cover” ifadesinden tamamlanmış bir şarkı bekleyebilir. Mevcut akışta vokal ayırma, seçilen vokali dönüştürme ve müzikle birleştirme aynı işlem değil; yeniden miksleme de mevcut ürün kapsamında değil.

**Yapılacak:** Girişin yanına “Dönüştürülecek vokal kaydı. Elinizde müzikli şarkı varsa önce Müzik ve Ses Temizleme'de vokali ayırın.” açıklaması konmalı. İlk sekmenin vokal sonucunu AI Cover girişine aktaran “Bu vokalle ses değiştir” eylemi eklenmeli. Sonucun dönüştürülmüş vokal dosyası olduğu baştan belirtilmeli. Bunun için mevcut kapsam dışında otomatik miksleme eklemek gerekmiyor.

**Kabul ölçütü:** Kullanıcı belge açmadan doğru girdiyi ve üretilecek çıktıyı tarif edebilmeli; ayırdığı vokali yeniden dosya aramadan kullanabilmeli.

Kaynak: `ui_cover.py:481`, `ui_cover.py:586`, `ui_cover.py:744`; `oku.md` ürün kapsamı.

### 4. Başlatma ve dinleme kontrolleri ayarların altında kayboluyor — P1

Varsayılan pencere boyutunda eğitim ekranının ilk görünümü epoch alanına kadar geliyor; **Yeni ses modeli eğit** görünmüyor. Canlı AI Cover'ın ilk görünümünde model, aygıtlar, perde, benzerlik, yöntem ve parça süresi var; **Otomatik ayarla**, ses düzeyi ve **Canlı dinlemeyi başlat** aşağıda kalıyor. Eğitimde kayıt yokken bile dinleme/bölüm seçme düğmeleri önemli bir alan kaplıyor.

**Yapılacak:** Canlı ekranın temel görünümü model → mikrofon/kulaklık → otomatik eşik → ses düzeyi → başlat/durdur şeklinde düzenlenmeli. F0 yöntemi, parça süresi ve gate zamanları gelişmiş bölüme alınmalı. Eğitim kayıtlar → ayarlar → dinle/kaydet şeklinde bölümlenmeli. Başlat/durdur ve kısa durum özeti görünür bir alt alanda kalmalı. Kayıt aralığı ve tutulacak model sayısı, mevcut ürün gereği kullanıcıya açık ve erişilebilir kalmalı.

**Kabul ölçütü:** Temel işlemin ana eylemi varsayılan boyutta görünmeli; klavyeyle mantıklı sırada erişilmeli. Daha küçük pencerelerde ve %125/%150 ölçeklerde kaydırmayla tüm kontrollere ulaşılmalı.

Kaynak: `main.py:81`; `ui_training.py:38`, `ui_training.py:139`; `ui_live_cover.py:67`, `ui_live_cover.py:108`.

### 5. Enstrüman ayırmada varsayılan tercih beklentiyi yanlış yönlendiriyor — P1

Enstrüman görünümüne ilk geçişte **“Ayrıntılı (6 kanal)”** seçili. Ekranın açıklaması aynı modelin gitar/piyano sonuçlarının deneysel olduğunu ve bilimsel kullanım için sunulduğunu söylüyor. “Ayrıntılı” sözcüğü sıradan kullanıcıya “daha iyi seçenek” izlenimi verebilir. “Standart” seçenek başlangıç tercihi değil.

**Yapılacak:** Dört kanallı seçenek başlangıç tercihi olarak değerlendirilmeli; altı kanallı seçeneğin adında doğrudan “Deneysel; gitar ve piyano ayrı” bilgisi bulunmalı. Kullanım koşullarının mevcut onay mekanizması korunmalı. Buradaki öneri kalite üstünlüğü iddiasına değil, sunulan seçenek ile açıklanan sınırlamaların tutarlılığına dayanıyor.

**Kabul ölçütü:** Kullanıcı seçeneği açmadan deneysel olduğunu anlamalı; gitar/piyanonun standart yöntemde “diğer enstrümanlar” içinde kalacağı açık olmalı.

Kaynak: `ui_separator.py:245`, `ui_separator.py:40`; `instruments/__init__.py`.

### 6. Eksik model hazırlamak kullanıcıyı görevinden uzaklaştırıyor — P1

İşleme özel **“Bu işlem için eksik modelleri hazırla”** düğmesinin olması iyi. Fakat bu düğme Ayarlar'a geçiriyor ve hazırlamayı başlatıyor. Ayarlar'ın üstünde görünüm, dosya biçimi ve güncellemeler var; model işlemi daha aşağıda. Başarılı hazırlığın ardından kullanıcıyı geldiği işe götüren bir eylem yok. Boyut bilgisi de ayrı bir hazırlık özeti olarak değil, iş başladıktan sonra günlük/durum alanına yazılıyor.

Bu bilgisayardaki modeller hazırdı; yeni kurulumdaki indirme akışı çalıştırılmadı. Bulgu ilgili yönlendirme ve tamamlanma koduna dayanıyor.

**Yapılacak:** Görev bağlamı korunmalı: “Vokal ayırmak için 1 model eksik; yaklaşık … indirilecek” özeti, indirme ilerlemesi ve sonunda “Vokal ayırmaya dön” düğmesi. Boyutu bilinmeyen dosyalar açıkça belirtilmeli. İşlem kendiliğinden ses üretmeye başlamamalı. Ayarlar'da model/donanım hazırlığı ayrı bir bölüm veya alt sayfa olarak daha kolay bulunmalı.

**Kabul ölçütü:** Boş model klasörlü bir test ortamında kullanıcı yalnız seçili işin modellerini hazırlayıp dosya ve seçeneklerini kaybetmeden aynı işe dönebilmeli.

Kaynak: `ui_operation.py:77`; `main.py:204`; `ui_settings.py:215`, `ui_settings.py:240`, `ui_settings.py:301`.

### 7. Vokal ekranında “ne kaydedilecek” ile “ne temizlenecek” karışıyor — P2

**“Müziği Ayır — Sadece Enstrümantal Müzik Kalsın”** ve **“İnsan Sesini Ayır — Sadece Vokal Kalsın”** aynı anda seçilebiliyor. Bu, iki ayrı çıktı istendiğinde doğru; ancak iki kez kullanılan “sadece” kelimesi seçeneklerin birbirini dışladığını düşündürüyor. Aynı listede arka vokal, yankı ve gürültü temizleme adımları da bulunuyor. Kodda enstrümantal özgün girdiden ayrı alınırken vokal işlemleri zincirleniyor; bu fark ekranda görünmüyor. Üst grup başlığındaki “3.” ve iç seçeneklerde yeniden başlayan numaralar da yapıyı belirsizleştiriyor.

**Yapılacak:** “Kaydedilecek çıktılar: Enstrümantal / Vokal” ile “Vokale uygulanacak temizlik” ayrı sunulmalı. Seçime göre “Vokal ayır → arka vokali temizle → yankıyı azalt” özeti ve oluşacak dosyalar gösterilmeli. Hazır vokal üzerinde yalnız temizlik yapabilme davranışı korunmalı. Her adımın zorunlu olmadığı açıklanmalı.

**Kabul ölçütü:** Kullanıcı hem vokal hem enstrümantal seçtiğinde iki çıktı alacağını, temizleme seçeneklerinin hangi kola uygulandığını anlayabilmeli.

Kaynak: `ui_separator.py:191`, `ui_separator.py:211`, `ui_separator.py:681`.

### 8. Boş form “Hazır” diyor; Başlat'a basınca “Hata” çıkıyor — P2

AI Cover'da model ve dosya seçilmemişken Başlat etkin. Düğmeye basıldığında kırmızı hata simgesiyle model seçme uyarısı açıldı. Eksik form doldurmak normal kullanımın bir parçası; program arızası gibi gösterilmemeli. Eğitimde kayıt yokken “Seçili özgün kaydı dinle” gibi uygulanamayacak eylemler de etkin görünüyor.

**Yapılacak:** Başlat'ın yanında eksik gereksinimler gösterilmeli: “1 model seçin · ses dosyası seçin”. Kullanıcı başlatmayı denerse ilk eksik alana odak götürülmeli. Başlat devre dışı bırakılacaksa nedeni ekran okuyucuyla erişilebilir olmalı. Boş kayıtta kullanılamayan eylemler gizlenmeli veya açıklamalı şekilde devre dışı olmalı.

**Kabul ölçütü:** Yeni kullanıcı deneme-yanılmayla birden fazla modal hata kapatmadan formu tamamlayabilmeli.

Kaynak: `ui_cover.py:660`; `ui_separator.py:303`, `ui_separator.py:789`; `ui_training.py:60`.

### 9. Model ekleme akışı teknik bilgiyi kullanıcıya bırakıyor — P2

Ad girişi, PTH dosyası ve index dosyası için ayrı pencereler açılıyor. Kullanıcı modelin nereden geldiğini, `.pth` ile `.index` arasındaki farkı ve neden bir dosya penceresinde **İptal** diyerek başarılı biçimde ilerlediğini bilmek zorunda. Index penceresinin başlığında isteğe bağlı olduğu yazıyor, fakat “İptal = index olmadan devam” alışıldık bir anlam değil. Canlı dinleme ekranı model eklemek için ayrıca AI Cover sekmesine gönderiyor.

**Yapılacak:** Tek “Ses modeli ekle” formu: ad, zorunlu RVC model dosyası, isteğe bağlı index ve kısa açıklama. “Index kullanmadan devam et” açık bir seçenek olmalı. Aynı form iki sekmeden açılabilmeli. Boş model listesi “Hazır model dosyası ekle / Kendi ses modelini eğit” yollarını açıklamalı.

**Kabul ölçütü:** Kullanıcı `.pth` dosyasını ekleyip index olmadan devam etmek için hiçbir noktada işlemi iptal ettiğini düşünmemeli.

Kaynak: `ui_cover.py:508`, `ui_cover.py:539`; `ui_live_cover.py:57`.

### 10. Model listelerinde seçim anlamı ve görsel düzen ağır — P2

AI Cover'da her model büyük bir açık/kapalı düğmesi. Varsayılan görünümde listede yaklaşık iki tam satır görünüyor; sayfanın ve model listesinin ayrı kaydırma alanları var. Aynı işaretler hem dönüştürülecek modelleri hem listeden kaldırılacak kayıtları belirliyor. Ayarlar'da **“Hazır - [KAPALI]”** ifadesi ise modelin kullanılamadığı şeklinde anlaşılabilir; gerçekte kapalı olan yalnız indirme/kontrol seçimidir.

**Yapılacak:** İsim, dosya durumu ve işlem seçimi ayrı ifade edilmeli. “3 model seçili; sırayla dönüştürülecek” özeti eklenmeli. Kayıt kaldırma, dönüşüm seçiminden ayrılmalı ve yalnız liste kaydını kaldırdığı açıklanmalı. Büyük model listelerinde arama ve daha fazla görünür satır sağlanmalı. Görsel düzen değişse de gerçek onay kutusu rolü, işaretli durumu ve klavye kullanımı korunmalı.

**Kabul ölçütü:** Kullanıcı “hazır”, “seçili” ve “listeden kaldır” kavramlarını birbirine karıştırmadan birden fazla modelle çalışabilmeli.

Kaynak: `ui_cover.py` içindeki `ModelToggleList`; `ui_cover.py:325`, `ui_cover.py:563`; `ui_settings.py:129`.

### 11. Sayısal ses ayarları deney yapmak isteyen kullanıcıyı yönlendirmiyor — P2

Dosya dönüşümünde **“Sesin inceliği / kalınlığı: 0”** var; görünür etikette birim ve artı/eksi yönlerinin anlamı yok. Aynı kavram canlı dinlemede “Perde” diye geçiyor. **“Model sesine benzerlik 0–1”** bir benzerlik yüzdesi gibi anlaşılabilir; bu alan index katkısını ayarlıyor, sonuç için ölçülmüş benzerlik veya kalite puanı değil. Canlı ekranda RMVPE/CREPE ve gate açılma/kapanma süreleri de temel akışta sunuluyor.

**Yapılacak:** Terimler eşleştirilmeli: “Ses tonu (yarım ses): 0 değişmez, + inceltir, − kalınlaştırır”. Index katkısı kısa açıklanmalı; yüksek değerin her zaman daha iyi olduğu izlenimi verilmemeli. Teknik yöntemler gelişmiş bölüme taşınmalı. Eşik için mevcut otomatik ölçüm temel yol olarak öne alınmalı; kullanıcının istediği çok düşük değerleri doğrudan yazabilme desteği korunmalı.

**Kabul ölçütü:** Kullanıcı bir değeri değiştirmeden önce ses üzerindeki beklenen yönü anlayabilmeli; yöntem adı öğrenmek zorunda kalmamalı.

Kaynak: `ui_cover.py:383`, `ui_cover.py:407`; `ui_live_cover.py:67`, `ui_live_cover.py:98`.

### 12. Sonuç ekranı dosyanın üretildiğini söylüyor, kullanmayı tamamlamıyor — P2

Vokal/enstrüman/cover sonucu mesajı kapatıldığında çıktı klasörü açılıyor. Bu mevcut davranış sonuçları bulmayı kolaylaştırıyor; ancak birden fazla aşama çıktısında “Hangisi son sonuç?” sorusunu çözmüyor. Temizleme ve AI Cover ekranlarında sonuçları doğrudan dinleme veya sonraki işleme aktarma alanı yok. Eğitimde dinleme özelliği var; bütün programda yokmuş gibi değerlendirilmemeli.

**Yapılacak:** Uygulamada kalıcı bir sonuç listesi gösterilmeli: “Ayrılmış vokal”, “Yankısı temizlenmiş vokal”, “Son çıktı” gibi açıklamalar; Dinle, Klasörü aç ve uygunsa AI Cover'da kullan eylemleri. Hata/iptalde tamamlanan sonuçlar açıkça ayrılmalı. Çıktı klasörünün otomatik açılması mevcut sözleşme olarak korunabilir; yeni liste buna ek olmalı.

**Kabul ölçütü:** Kullanıcı dosya adlarının sırasını çözmeden son çıktıyı ve önceki aşamaları ayırt edip dinleyebilmeli.

Kaynak: `ui_operation.py:32`; `ui_separator.py:681`; `ui_cover.py:744`; `ui_training.py:190`.

### 13. Kullanım bilgisi belgelerde var, uygulamada erişim zayıf — P2

Menü yalnız Araçlar altında güncelleme ve ayarları sunuyor. İlk kullanım rehberi, model dosyası açıklaması, kısa klavye yardımı veya bağlama duyarlı yardım bağlantısı bulunmuyor. Belgelerde yararlı açıklamalar var; örneğin enstrümanda daha az kanal seçmenin model hesabını azaltmadığı yalnız rehberde açıklanıyor.

Bazı kullanıcı belgelerinin sonunda hâlâ “iki yeni paket gerekir / yeniden üretilecek” gibi eski ifadeler bulunuyor; güncel Son Durum ise 23 Ekim yayınını tamamlanmış gösteriyor. Vokal onarımı belgesindeki “basılı/basılı değil” anlatımı da güncel onay kutusu sözleşmesiyle uyuşmuyor.

**Yapılacak:** Yardım menüsü ve her ana ekranda kısa “Nasıl kullanılır?” bağlantısı eklenmeli. Kullanıcıya gereken özet çevrimdışı erişilebilir olmalı. Tarihsel teknik kayıtlar korunurken güncel kullanım sayfalarındaki eski yayın ifadeleri ayrılmalı veya güncellenmeli. Ekran okuyucu kısayolları açıklanmalı; uzun yardım metinleri temel işlem yolunu uzatmamalı.

**Kabul ölçütü:** İlk defa açan biri uygulamadan çıkmadan üç temel soruya cevap bulabilmeli: hangi dosya, hangi model, sonuç nerede?

Kaynak: `main.py:111`; `docs/ENSTRUMAN_AYIRMA.md`, `docs/VOKAL_ONARIMI.md`, `docs/DONANIM_VE_MODEL_YONETIMI.md`, `docs/SON_DURUM.md`.

### 14. Aynı sürüm adı kullanıcının hangi pakette olduğunu anlatmıyor — P2

Belgeler eski ve yenilenmiş 2.1.0 kurulumlarının farklı olduğunu, mevcut 2.1.0 için otomatik güncelleme bildirimi çıkmadığını açıkça söylüyor. Pencere başlığı ve başlangıç mesajı ise yalnız **2.1.0** gösteriyor. “Bende de 2.1.0 var ama Canlı AI Cover yok” sorusu bu nedenle makul.

**Yapılacak:** Kullanıcının sürüm numarasını koruma kararı değiştirilmeden bir Hakkında alanında paket yenileme tarihi, CPU/CUDA türü ve derleme kimliği gösterilmeli. Destek için kopyalanabilir kısa tanı özeti sunulmalı. Kaynaktan çalıştırma ile kurulu paket bilgisi birbirine karıştırılmamalı.

**Kabul ölçütü:** Aynı 2.1.0 numaralı iki kurulum, teknik günlük veya dosya hash'i aranmadan ayırt edilebilmeli.

Kaynak: `main.py:80`, `main.py:131`; `CHANGELOG.md:6`; `docs/SON_DURUM.md`.

### 15. Başlangıç ve durum sunumu gereksiz tekrar içeriyor — P3

Her açılışta geliştirici adı ve programın hazır olduğunu bildiren modal pencere kapatılıyor. Arkadaki ekranda zaten başlık, açıklama, durum alanı ve günlükte başka bir “Hazır” mesajı var. Henüz işlem yokken boş ilerleme çubuğu ve devre dışı durdurma düğmeleri de alan kaplıyor. Temel eylemler ile ikincil eylemlerin düğme görünümü birbirine çok yakın.

**Yapılacak:** Geliştirici bilgisi Hakkında bölümüne taşınmalı veya karşılama yalnız ilk kullanımda ve gerçek başlangıç yardımıyla gösterilmeli. Tek, anlamlı durum özeti kullanılmalı. İşlem günlüğü açılır ayrıntı alanında erişilebilir tutulmalı. Başlat ana eylem olarak görsel açıdan ayırt edilmeli; zorla durdur gerektiğinde açıklamasıyla sunulmalı.

**Kabul ölçütü:** Sonraki açılışlarda kullanıcı bir bilgi penceresi kapatmadan işe başlayabilmeli; durum alanı “program hazır” yerine sıradaki gerekli adımı söylemeli.

Kaynak: `main.py:131`; `ui_separator.py:271`, `ui_separator.py:303`; `ui_cover.py:435`.

## Uygulama sırası

1. **İlk tur:** Tercih edilen eğitim adayını kalıcı saklama ve temizlik akışını düzelt; koyu tema okunabilirliğini gider; AI Cover girdisini/çıktısını açıkla; deneysel enstrüman seçiminin etiketini ve başlangıç tercihini gözden geçir. Eksik form alanlarını yerinde göster.
2. **İkinci tur:** Eğitim ve canlı ekranı yeniden düzenle; ana eylemleri görünür tut; model hazırlamadan işe dönüşü ekle; tek model ekleme formunu paylaş; seçim ile model yönetimini ayır.
3. **Üçüncü tur:** Sonuç listesi ve sekmeler arası aktarım, bağlama duyarlı yardım, paket kimliği ve belge tutarlılığını tamamla.

Bu sırada ses motorunun kalite varsayılanlarını, kayıtlı donanım/biçim tercihlerini, kişisel dosyaları, çakışmasız çıktı adlarını, indirme koşullarını ve mevcut erişilebilir seçim durumlarını değiştirmek gerekmiyor. Eğitimde kayıt aralığı ve tutulacak model sayısı, ortak index ve kullanıcı kontrollü temizlik korunmalı.

## Kullanıcı kabulü için kısa senaryolar

| Senaryo | Başarı ölçütü |
| --- | --- |
| İlk kez şarkıdan vokal ayırma | Yardım almadan doğru alanı seçer, yalnız gereken modeli hazırlar, çıktıyı bulur. |
| Ayrılan vokalle AI Cover yapma | Tam şarkı/vokal farkını anlar, sonucu tekrar dosya aramadan dönüştürür. |
| İlk ses modelini ekleme | `.pth` gerekliliğini ve index'in isteğe bağlı olduğunu anlar. |
| Enstrüman ayırma | Dört/altı çıktı farkını ve deneysel seçeneği işlemden önce fark eder. |
| Eğitim sonucunu saklama | Dinleyerek tercih ettiği adayı kalıcı kaydeder; temizlik kararının devam eğitimine etkisini bilir. |
| Canlı dinleme | Model ve aygıtları seçer, ölçüm ile dinlemeyi ayırt eder, başlat/durdur kontrollerini kolayca bulur. |
| Klavye/ekran okuyucu | Kontrol adı, işaretli durum, hata sonrası odak ve tamamlanma bildirimi doğru anlaşılır. |

İlk kullanım başarısı, yanlış seçim sayısı, yardım ihtiyacı ve görevin tamamlanma süresi gerçek kullanıcı denemelerinde kaydedilmeli. Mevcut 458 testlik geçmiş, bu kullanılabilirlik ölçütlerinin sağlandığına kanıt olarak kullanılmamalı.
