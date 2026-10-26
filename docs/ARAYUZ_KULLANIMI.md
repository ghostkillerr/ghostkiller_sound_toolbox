# Arayüzde temel işler

25 Ekim 2026 kaynak düzenlemesi. Bu rehber yeni arayüzü anlatır; yayımlanmış
23 Ekim 2.1.0 kurulumları henüz bu düzenlemeleri içermez.

Her ekranda **F1** o ekranın çevrimdışı yardımını açar. **Ctrl+Tab** ve
**Ctrl+Shift+Tab** sekme değiştirir. **F6** pencerenin altındaki başlat/durdur
alanına gider; bu alan form kaydırılsa da yerinde kalır. **Tab/Shift+Tab**
kontroller arasında ilerler; **Boşluk** işaretli/işaretsiz seçimini değiştirir.
Günlükler açılır ayrıntı alanındadır. Yardım menüsündeki **Hakkında ve paket
bilgisi** sürümü, geliştiriciyi ve paket türünü gösterir; bilgi kopyalanabilir.

## Bir şarkının vokalini başka sesle söylemek

1. **Müzik ve Ses Temizleme** ekranında şarkıyı seçin. **Vokali ayır ve
   kaydet** açık olsun. Müziği de ayrı dosyada istiyorsanız **Enstrümantal
   çıktısını kaydet** seçeneğini açın. Bu iki seçim birlikte kullanılabilir.
2. Gerekiyorsa vokal temizliğini seçin. Ekrandaki zincir, vokale uygulanacak
   sırayı gösterir. Enstrümantal her zaman özgün şarkıdan çıkarılır. Hazır
   vokaliniz varsa yeniden ayırmadan yalnız gerekli temizliği seçebilirsiniz.
3. Eksik model düğmesi görünüyorsa hazırlayın. İndirme öncesinde modeller,
   bilinen boyut ve boyutu bilinmeyen dosyalar açıklanır. Hazırlık bitince
   **işe dön** düğmesiyle dosya ve seçimlerinizi koruyarak geri gelin.
4. Alt alandan başlatın. İş bitince sonuçlar listesinde her aşama görünür;
   en son üretilen vokal ayrıca belirtilir. Tamamlanmış aşamalar hata/iptalde
   listede kalır. Bir sonucu dinleyebilir veya klasörünü açabilirsiniz.
5. Vokali seçip **Bu vokalle ses değiştir** düğmesine basın. Ses Değiştirme
   ekranına dosya aktarılır. **Ses modeli ekle** ile hazır RVC `.pth` dosyanızı
   ekleyin; `.index` varsa ekleyin, yoksa alanı boş bırakın. Hazır modeliniz
   yoksa Model Eğitimi ekranında kendi kayıtlarınızla model oluşturabilirsiniz.
6. Dönüştürmede kullanılacak bir veya birkaç modeli işaretleyin. Arama yapmak
   gizlenen modellerin işaretini kaldırmaz; toplam seçili sayısını kontrol edin.
   Model listesini yönetme düğmesi dönüşüm seçiminden ayrıdır; yalnız liste
   kaydını kaldırır, model dosyalarını silmez.
7. Ses tonu **0** ise değişmez; **+** inceltir, **−** kalınlaştırır. Birim yarım
   sestir. Gelişmiş ayarlardaki **Index katkısı** kalite veya benzerlik puanı
   değildir. Emin değilseniz varsayılanları koruyun ve başlatın.

AI Cover sonucu dönüştürülmüş vokaldir; müzikle otomatik birleştirme yapılmaz.
Önceki dosyalar korunur; ad çakışırsa `(2)`, `(3)` eklenir. Sonuç mesajının
ardından klasörün otomatik açılması devam eder.

## Enstrüman, eğitim ve canlı dinleme

- Enstrüman ayırmada başlangıç **Standart (4 ayrı ses)** seçeneğidir: bas,
  davul, vokal ve diğer sesler. Gitar/piyano ayrı istendiğinde **Deneysel
  (6 ayrı ses; gitar ve piyano dahil)** seçilir. Daha az çıktı seçmek model
  hesabını azaltmaz. [Enstrüman rehberi](ENSTRUMAN_AYIRMA.md).
- Eğitim sonunda **Seçili modeli kalıcı kaydet** tek adayı kaydeder. Toplu
  kayıt, epoch modellerini, seçili adayı ve notla tercih ettiğiniz modeli
  birlikte korur. Oturum kendiliğinden silinmez. Daha sonra oturumlar
  ekranından ayrı onayla temizlenebilir; tercih edilen modelin kalıcı kopyası
  yoksa temizlik engellenir. [Eğitim rehberi](MODEL_EGITIMI.md).
- Canlı dinlemede model, mikrofon ve kulaklığı seçin. **Otomatik ayarla** ile
  10 saniye sessiz kalıp ölçüm yapın; ardından canlı dinlemeyi ayrıca başlatın.
  Teknik yöntemler ve elle eşik girişi **Gelişmiş canlı ses ayarları** içindedir.
  Ses eşiğinin alt sınırı yoktur: 0 dB veya altında sonlu her değer
  yazılabilir. [Canlı dinleme rehberi](CANLI_AI_COVER.md).

Ayarlar listesindeki **Hazır/Eksik** dosyanın durumudur. **[AÇIK]/[KAPALI]**
yalnız bakım için seçilmiş olup olmadığını gösterir; modelin ses işlerinde
kullanımını kapatmaz. Donanım/model hazırlığı sayfanın başında, görünüm ve
ortak dosya tercihleri devamındadır.
