# Ses modeli eğitimi — kullanım rehberi

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

Modele ad verin. Emin değilseniz 40 kHz, otomatik batch ve mevcut diğer ayarları
koruyun. Epoch hedefi kalite garantisi değildir; daha fazla epoch sonucu her zaman
iyileştirmez. **Yeni ses modeli eğit** düğmesiyle başlayın.

İşlem sırasında aşama, süre tahmini ve RAM/VRAM ölçümleri gösterilir. **Durdur ve
kaydet**, tam optimizasyon adımından sonra devam noktası bırakır. Zorla durdurma
son kayıttan sonraki adımları kaybettirebilir. Son sağlam kayıt korunur.

**Eğitim oturumlarım** ile önceki oturumları listeleyin. Açmak yeniden eğitim
başlatmaz. **Yarım kalan eğitime devam et** kayıtlı ayarları geri getirir.
CPU/GPU backend'i, veri veya yardımcı model kimliği değişmişse aynen devam edilmez.

## 3. Sonuçları karşılaştırın

Her değerlendirmede son model ve en düşük kontrol mel hatasına sahip model
üretilir. Varsayılan olarak ayrıca en fazla **üç ara model**, **2048 MB** sınırı
içinde saklanır. Sayı ve disk sınırı gelişmiş ayarlardan değiştirilebilir.
Tercih ettiğiniz bir ara model korunur; bu model tek başına yeni disk sınırını
aşıyorsa silinmez. Son model, en düşük hatalı model ve tam devam kaydı arşiv
budamasından etkilenmez.

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

**Ses değiştirme listesine ekle** kalıcı bir model/index kopyası oluşturur.
Farklı adayları farklı adlarla kaydedebilirsiniz; mevcut adın üstüne yazılmaz.
Küçük inference modeli tam devam kaydı değildir.

## 4. Ek eğitim veya yeni deneme

- **Toplam tekrar sayısını artır ve devam et:** Önce bir oturum açın, daha yüksek
  toplam epoch hedefi girin. Aynı veri, optimizer/scheduler ve RNG ile devam edilir.
  Hedef değişikliği ve hangi checkpoint'ten yapıldığı kaydedilir.
- **Önceki eğitimden yeni bir model eğit:** Formda yeni kayıt/ayarları belirleyin,
  başlangıç alınacak eğitim oturumunu seçin. Önceki G/D ağırlıkları kopyalanır;
  optimizer ve sayaçlar yeni oturumda sıfırdan başlar. Örnekleme hızı/mimari
  eşleşmelidir. Eski oturum ve modeller değişmez. Bu işlem tam resume değildir.
- **İki eğitimin ayarlarını karşılaştır:** İki oturum seçip epoch, öğrenme hızı,
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
