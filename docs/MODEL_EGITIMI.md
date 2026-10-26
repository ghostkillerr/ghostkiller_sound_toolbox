# Ses modeli eğitimi — kullanım rehberi

25 Ekim kaynak arayüzünü anlatır. Yeni akışlar henüz 23 Ekim 2.1.0
kurulumlarına eklenmedi; [paket ve kaynak durumu](SON_DURUM.md) ayrı izlenir.


Program tek kişiye ait kayıtlarla yerel RVC V2 ses modeli eğitir. Ses dosyaları
bilgisayarınızda kalır. Önce kısa bir deneme yapmanız, iki sonucu dinleyip sonra
daha uzun eğitim başlatmanız önerilir.

## 1. Kayıtları hazırlayın

1. **Ayarlar** sekmesinden işlemci/ekran kartı tercihini yapın, donanımı kontrol edin.
2. ContentVec, seçtiyseniz RMVPE ve örnekleme hızına uygun eğitim ağırlıklarını hazırlayın.
3. **Model Eğitimi → Ses kayıtları ekle** ile aynı kişiye ait kayıtları seçin.
4. **Kayıtları eğitim başlatmadan incele** düğmesine basın. Model adı yazmanız gerekmez.

İnceleme; kayıt süresini, düşük seviyeli sesleri, tepe/clipping ve mono birleştirmede
enerji kaybını bildirir. Tablo eğitim ve kontrol için ayrılan benzersiz süreleri
gösterir. Bu ölçümler gürültü/yankı veya ses kimliğini doğrulayan bir kalite puanı değildir.

Bir kaydı ok tuşlarıyla seçip **Seçili özgün kaydı dinle** ile kontrol edin.
Uygun değilse **listeden kaldır** düğmesini kullanın; dosya diskinizden silinmez.
Yalnız bir bölüm kullanılacaksa **kullanılacak bölümünü belirle** düğmesine
başlangıç/bitiş saniyelerini yazın. Bitiş `0`, kaydın sonu demektir. Bölüm en az
iki saniye olmalıdır. Özgün dosya kesilmez; eğitim için ayrı kopyalar hazırlanır.

Aynı şarkının farklı vokal/stem/kayıt sürümlerini eklediyseniz gelişmiş ayarlardan
aynı eşleştirme adını verin. Bir grubun kayıtları eğitim ve kontrol arasında bölünmez.
Tek kayıtta son bölüm kontrol için ayrılır; örtüşen parçalar sınırı geçmez.
Bu yöntem farklı şarkılarda genellemeyi kanıtlamaz. Tüm farklı kayıtlar aynı grupta
kalırsa bağımsız kontrol için başka bir şarkı/oturum eklemeniz istenir.

## 2. İlk eğitimi başlatın

Modele ad verin. **Kaç epoch'ta bir model kaydedilsin?** alanı ara model aralığıdır:
`10` seçilirse 10, 20, 30 ve devam eden epoch'larda kayıt alınır. Hedef epoch bu
aralığa denk gelmese de son epoch ayrıca kaydedilir. **Son kaç epoch modeli
tutulsun?** alanı disk üzerinde kalacak en yeni kayıt sayısını belirler. Örneğin
aralık `10`, sayı `3` ve hedef `100` ise sonunda 80, 90 ve 100 modelleri kalır.
Emin değilseniz 40 kHz, otomatik batch ve mevcut diğer ayarları koruyun. Epoch
hedefi kalite garantisi değildir; daha fazla epoch sonucu her zaman iyileştirmez.
**Yeni ses modeli eğit** düğmesiyle başlayın.

İşlem sırasında aşama, süre tahmini ve RAM/VRAM ölçümleri gösterilir. **Durdur ve
kaydet**, tam optimizasyon adımından sonra devam noktası bırakır. Zorla durdurma
son kayıttan sonraki adımları kaybettirebilir. Son sağlam kayıt korunur.

**Eğitim oturumlarım** ile önceki oturumları listeleyin. Oturumu seçtikten sonra
sonuç açma, yarım eğitime devam etme, epoch hedefini artırma, önceki eğitimden
yeni model başlatma ve geçmişi inceleme işlemlerinden uygun olanı seçebilirsiniz.
Yalnızca oturumu açmak yeniden eğitim başlatmaz. **Yarım kalan eğitime devam et**
kayıtlı ayarları geri getirir.
CPU/GPU backend'i, veri veya yardımcı model kimliği değişmişse aynen devam edilmez.

## 3. Sonuçları karşılaştırın

Her değerlendirmede son model ve en düşük kontrol mel hatasına sahip model
üretilir. Varsayılan olarak en yeni **üç epoch modeli**, **2048 MB** sınırı
içinde saklanır. Tutulacak sayı ana eğitim ekranından, disk sınırı gelişmiş
ayarlardan değiştirilebilir. Sınır aşılırken en eski epoch modelleri kaldırılır.
Son model, en düşük hatalı model ve tam devam kaydı teknik oturumda ayrıca bulunur.

Sonuç bölümünde modeli, ortak test kaydını ve index kapalı/açık seçeneğini belirleyip
dinleyin. Her aday aynı ayrılmış kayıtlarla sınanır. **Index kapalı** modelin kendi
sonucunu, **index açık** eğitim özelliklerinin desteğiyle sonucu duymanızı sağlar.
Varsayılan karşılaştırmada index oranı `0.75`'tir.

Gelişmiş ayarlardan isteğe bağlı en fazla beş **ayrı karşılaştırma kaydı** seçilebilir.
Bunlar eğitime ve index'e girmez. Her kaydın ilk en fazla 12 saniyesi bütün adaylarla
aynı ayarlarda dönüştürülür. Eğitim dosyasının kopyası bağımsız test olarak kabul edilmez.
Bu kayıtlar eklenmezse en fazla üç holdout parçası kullanılır.

**Değerlendirme geçmişi** epoch/adım, kontrol mel hatası ve son adımın G/D
kayıplarını native tabloda gösterir. Düşük mel hatası daha iyi duyulan tınıyı
garantilemez. Anlaşılırlık, nota kararlılığı, tını ve istenmeyen sesleri dinleyin.
**Tercih et ve not yaz** ile dinleyerek seçtiğiniz adayı kaydedin.

**Seçili modeli kalıcı kaydet** yalnız dinleme listesindeki adayı kaydeder.
**Epoch modellerini ve tercihimi topluca kaydet** tutulan epoch modellerini,
seçili adayı ve oturum notuyla tercih edilen modeli birlikte kaydeder. Aynı
ağırlık iki kez kopyalanmaz; farklı tercih edilen model ayrıca korunur. Örneğin `Ahmet` için temiz klasör
`trained_models/Ahmet/`; dosyalar `Ahmet_Epoch_080.pth`,
`Ahmet_Epoch_090.pth`, `Ahmet_Epoch_100.pth` ve ortak `Ahmet.index` olur.
AI Cover listesinde her epoch ayrı görünür ve aynı index'i kullanır. Aynı adlı
klasör varsa `Ahmet (2)` gibi numaralanır; mevcut dosyaların üzerine yazılmaz.
Teknik eğitim klasörü işlem bitince kendiliğinden açılmaz. Küçük inference
modelleri tam devam kaydı değildir.

Model kaydından sonra eğitim oturumu varsayılan olarak saklanır. Temizlemek
isterseniz **Eğitim oturumlarım → Teknik çalışma dosyalarını sil** yolunu kullanın.
Boyut ve silinecek çalışma dosyaları onaydan önce gösterilir. Varsayılan seçim
oturumu saklamaktır. Devam checkpoint'i, hazırlanmış parçalar/özellikler, ara
test sesleri ve teknik oturum silinince aynı eğitime devam edilemez. Özgün
kayıtlar ve kalıcı modeller korunur. Notla tercih edilen model ve ortak index
kalıcı kayıtla eşleşmiyorsa temizlik engellenir. Yarım veya başka bir eğitimin
başlangıç ağırlığı olarak beklenen oturumlar da temizlenmez.

Bağlı eğitim hata vermiş olsa da devam edilebilir; başlangıç checkpoint'ine
bağımlılığı sürerken eski oturum silinmez. Bir oturumun özgün/karşılaştırma kaydı
veya AI Cover listesindeki bir model/index temizlenecek klasörün içindeyse de
işlem durur. Önce modeli kalıcı konuma kaydedip eski liste kaydını kaldırmak gerekir.
Okunamayan oturum/model kayıtları ve yönlendirilmiş klasörler otomatik temizliği
engeller; belirsiz durumda dosyalar korunur.

Dosya kilidi gibi bir nedenle temizlik yarıda kalırsa oturum **Temizlik yarım
kaldı** olarak görünür. Bu durumdaki oturumdan eğitim başlatılmaz; menüden
**Teknik çalışma dosyalarını sil** yeniden denenebilir veya teknik klasör
açılabilir. Bozuk isteğe bağlı hazırlık-cache kaydı tek başına tamamlanmış
silme işlemini başarısız diye göstermez.

## 4. Ek eğitim veya yeni deneme

- **Toplam tekrar sayısını artır ve devam et:** Eğitim oturumlarım içinden tamamlanan
  oturumu seçin, daha yüksek
  toplam epoch hedefi girin. Aynı veri, optimizer/scheduler ve RNG ile devam edilir.
  Hedef değişikliği ve hangi checkpoint'ten yapıldığı kaydedilir.
- **Önceki eğitimden yeni bir model eğit:** Formda yeni kayıt/ayarları belirleyip
  Eğitim oturumlarım içinden başlangıç eğitimini seçin. Önceki G/D ağırlıkları kopyalanır;
  optimizer ve sayaçlar yeni oturumda sıfırdan başlar. Örnekleme hızı/mimari
  eşleşmelidir. Eski oturum ve modeller değişmez. Bu işlem tam resume değildir.
- **İki eğitimin ayarlarını karşılaştır:** Gelişmiş eğitim ayarlarından iki oturum seçip epoch, öğrenme hızı,
  batch, parça/örtüşme ve kontrol payı farklarını okuyun.

## 5. Aynı kayıtlarla farklı ayarlar denemek

Gelişmiş ayarlardan kendi **ayar şablonlarınızı** kaydedip uygulayabilirsiniz.
Şablon kişisel seslerinizi, kaynak yollarını veya kayıt gruplarını içermez.

**Sıraya ekle**, formun o andaki veri/ayarlarını kaydeder. **Sıradaki eğitimleri
çalıştır** ile işler tek tek yürür. Hata veya durdurmada sıra bekler. Program
yeniden açıldığında önceki yarım iş kendiliğinden tekrarlanmaz; oturum listesinden
açıp devam edebilirsiniz. Sıradan çıkarmak eğitim/model dosyalarını silmez.

**Doğrulanmış hazırlığı yeniden kullan** açıksa aynı veri, bölüm/grup/split,
F0/ContentVec kimliği ve runtime ile tamamlanmış bir deneyin hazırlanmış verileri
kontrol edilip yeni oturuma kopyalanabilir. Dosyalar ortak yazılabilir şekilde
paylaşılmaz. Eski oturum silinmiş/değişmişse kaynaklar yeniden hazırlanır.

## Teknik sınırlar

Eğitim ve export FP32; yardımcı model ve hazırlık kimlikleri hash ile sabittir.
Index yalnız eğitim özelliklerinden tam FlatL2 ile üretilir. Otomatik denoise,
perde değiştirme, AMP/TF32 veya farklı vocoder'a sessiz geçiş yapılmaz.
Uzun gerçek kayıt kalitesi, donanım uyumu ve canlı NVDA/JAWS kullanımı ayrıca
denetlenmelidir. Ayrıntılar [teknik eğitim sınırlarında](TRAINING_RELEASE_FIXES.md)
açıklanır; sentetik testler profesyonel ses kalitesi kanıtı değildir.
