# Senden gereken kısa deneme

Teknik ayar seçmen veya komut yazman gerekmiyor. Otomatik testlerin
kontrol edemediği iki şey var: gerçek sesin kulağa nasıl geldiği ve senin
Windows/ekran okuyucu ortamında kullanımın rahatlığı.

## Ses denemesi

1. Aynı kişiye ait, müziksiz ve yankısı az iki farklı kayıt seç. Varsa biri
   daha pes, diğeri daha tiz bölümler içersin. Özel kayıtlarını GitHub'a yükleme.
2. Model Eğitimi'nde kayıtları ekle, **Kayıtları eğitim başlatmadan incele**
   düğmesine bas. Anlamadığın veya yanlış görünen mesajı olduğu gibi bana yaz.
3. İlk işleyiş denemesinde **Eğitim tekrar sayısı** alanını `3`, gelişmiş
   ayarlardaki **Kaydetme ve değerlendirme aralığı** alanını `1` yapabilirsin.
   Bu, kaliteli model için önerilen hedef değil, düğmeleri kısa sürede denemek içindir.
4. Eğitimden sonra iki modeli aynı kontrol kaydıyla, önce index kapalı
   dinle. Hangisinde ses daha anlaşılır, notalar daha kararlı, istenmeyen sesler
   daha az? Bunu günlük dille söylemen yeterli; sayı veya ölçüm hesaplamana gerek yok.

Eğitilecek gerçek kayıtlar ve dinleme tercihi olmadan “ses kalitesi iyileşti”
sonucuna varamayız. Teknik testlerde kullanılan sentetik sesler bunu ölçmez.

## Windows ve ekran okuyucu denemesi

- Hazırlanan kurulumun temiz Windows/Sandbox'ta açıldığını, güncellemede model ve
  ayarların korunduğunu denemek gerekir. Sandbox yapılandırması hazırlanır;
  geliştirici bilgisayarında üretim kurulumu kendiliğinden başlatılmaz.
- NVDA veya JAWS kullanıyorsan kayıt inceleme tablosu, model/test kaydı seçimi ve
  sonuç mesajlarını okuduğunu kontrol et. “Şu düğmede sustu / aynı yazıyı iki kez
  okudu / Tab ile geçemedim” biçiminde anlatman yeterli.
- Bir sorun görürsen yaptığın son işlem ve ekrandaki mesajı bana yaz. Günlük
  dosyasını bulmakta zorlanırsan ben nereden alınacağını tarif ederim.

Bu kabul tamamlanana kadar kurulumlar yayın adayıdır. Herkese dağıtım ve gerçek
güncelleme duyurusu bu sonuçlardan sonra yapılır.
