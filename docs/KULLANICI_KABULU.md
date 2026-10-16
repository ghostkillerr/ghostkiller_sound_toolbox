# İlk deneme: senden beklenenler

Güncelleme: **16 Ekim 2026**. Önceki CPU ve NVIDIA CUDA 2.1.0 kurulumlarının
üretildiği kaynakta 296'şar otomatik test geçti. Sonraki isteğe bağlı vokal
onarımı kaynak sürümüne eklendi; önceki installer'larda henüz yoktur.
Gerçek sesle dinleme ve günlük kullanım
denemesi henüz tamamlanmadı. Otomatik testler, sesin kulağa iyi geldiğini ölçmez.

Kod yazman, komut çalıştırman veya eğitim teorisini bilmen gerekmiyor.
Yazılım değişiklikleri, hata incelemesi, teknik ayarlar, testler ve kurulum
hazırlığı geliştirme tarafında yapılır. Senden gereken, kullanılacak sesi
seçmen ve sonucu günlük dille anlatmandır.

Yeni onarım seçeneğini denemek için **Arka Vokalleri ve Harmoni Seslerini
Temizle** düğmesini aç. Altında görünen **kısa vokal kayıplarını onar** düğmesi
varsayılan kapalıdır. Açarsan standart ve onarılmış mono sonuç ayrı kaydedilir.
Tab/Boşluk tuşlarını ve NVDA'nın açık/kapalı okumasını dinleyip takıldığın yeri
söylemen yeterli. [Kullanım ayrıntıları](VOKAL_ONARIMI.md).

## Şimdi gereken üç şey

1. **Denemek istediğin sesi seç.** Model eğitimi için mümkünse aynı kişiye
   ait, farklı bölümler içeren iki ayrı kayıt belirle. Müziksiz ve yankısı az
   kayıtları tercih et. Bu seçim bir ilk denemedir; iyi model için yeterli veri
   bulunduğu incelemeden önce söylenemez. Kayıtların yoksa önce kayıt hazırlama
   adımı planlanır. Dosyaları internete yüklemen gerekmez; bilgisayardaki
   klasörlerini söylemen yeterli.
2. **Kısa bir işleyiş denemesi yap.** Adımlar aşağıda. Bir mesajı anlamazsan
   olduğu gibi aktar. Teknik anlamını çözmen beklenmiyor.
3. **Duyduğunu ve takıldığın yeri anlat.** Örneğin: “Kelimeler bozuluyor”,
   “Tizlerde metalik oluyor”, “Ses istediğim kişiye benzemiyor” veya
   “Bu düğmeden sonra ne yapacağımı anlayamadım”. Ölçüm hesaplaman gerekmiyor.

## Kısa eğitim denemesi

Bu ilk deneme, düğmelerin ve işlemlerin çalışmasını görmek içindir;
iyi ses modeli elde edildiği anlamına gelmez.

1. **Model Eğitimi → Ses kayıtları ekle** ile kayıtları seç.
2. **Kayıtları eğitim başlatmadan incele** düğmesine bas.
3. Sonuçta anlaşılmayan veya sorun bildirilen bir mesaj varsa onu aktar;
   sonraki ayarlar kayıt incelemesine göre birlikte belirlenir.
4. Bu geliştirme bilgisayarında **Kayıtlı ayar şablonunu uygula →
   Kısa işleyiş denemesi (3 tekrar)** hazırdır. Bu şablon eğitim tekrarını
   `3`, kaydetme ve değerlendirme aralığını `1` yapar. Kurulum başka bir
   bilgisayarda kullanılıyorsa şablonun orada bulunduğu varsayılmaz.
5. Modele bir deneme adı verip **Yeni ses modeli eğit** düğmesine bas.
6. Bittikten sonra sonuç bölümündeki modelleri aynı test kaydıyla dinle.
   İlk karşılaştırmada **index kapalı** seçilebilir; bu, modelin kendi
   sonucunu dinlemek içindir.

Bir hata çıkarsa son yaptığın işlemle birlikte mesajını bildir.
Günlük dosyasını bulman veya hatayı kendin çözmen beklenmiyor.
Gerçek kalite denemesi için kullanılacak kayıtlar ve eğitim süresi bu kısa
denemenin ardından belirlenir; tekrar sayısını artırmak tek başına kalite garantisi değildir.

## Geliştirmede izlenecek sıra

Kullanıcının önceliği **model eğitimi ve ileri özellikler** olarak korunur.
Kayıt inceleme, durdur/devam, ara modeller, karşılaştırma, oturumlar ve deney
kuyruğu zaten vardır; bunlar yeni eklenecek özellikler olarak sayılmamalıdır.

1. **Gerçek bir başlangıç sonucu kaydet:** Kullanılan kayıtlar ve ayarlar,
   eğitim süresi, dinlenen çıktı ve kullanıcının yorumu yerelde tutulur.
2. **İlk kullanımı kolaylaştır:** İlk denemede zor gelen adımlara göre
   yönlendirme, terim açıklamaları ve sonraki işlem önerileri iyileştirilir.
3. **Duyulan sorunu düzelt:** Aynı test kaydıyla önceki ve yeni sonuç
   karşılaştırılır. Değişikliğin kaliteyi artırdığı dinlemeden ilan edilmez.
4. **Uzun çalışmayı doğrula:** Daha uzun eğitim, durdurup devam etme,
   kaynak kullanımı ve model kaydının gerçek kullanım sonuçları incelenir.
5. **İleri özellikleri ölçüme göre seç:** Hız veya yeni eğitim yöntemleri,
   görülen ihtiyaca göre ayrı denemelerle değerlendirilir.

## Daha sonra, dağıtımdan önce

Temiz Windows kurulumu, güncelleme, model ve ayarların korunması ve kaldırma
kontrolleri ayrı bir aşamadır. Hazır Sandbox dosyaları vardır; bu rehberi
okumak bunları başlatmaz. Bu işlemler zamanı geldiğinde adım adım yürütülür.

NVDA veya JAWS kullanıyorsan düğme adlarının, sonuçların ve Tab geçişlerinin
anlaşılır olup olmadığını da dene. “Şurada sustu” veya “Aynı yazıyı iki kez
okudu” demen yeterlidir.

Ayrıntılı kullanım: [Model eğitimi rehberi](MODEL_EGITIMI.md).
