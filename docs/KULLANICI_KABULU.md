# Kullanıcı denemesi

Güncelleme: **23 Ekim 2026**. Güncel test ve paket durumu
[Son durum](SON_DURUM.md) dosyasındadır. Kod yazman, komut çalıştırman veya
eğitim teorisini bilmen gerekmiyor. Sonucu dinleyip takıldığın yeri anlatman yeterli.

## 1. Hazırlık ve sonuçları bulma

1. İşlem ekranında dosya biçimi, kanal düzeni ve donanım özetini kontrol et.
2. Model eksikse görünen **Bu işlem için eksik modelleri hazırla** düğmesini
   kullan. Yalnız ilgili modeller seçilmeli; hazır olunca düğme kaybolmalı.
3. Kısa bir kayıtla işlem yap. Sonuç mesajını kapatınca çıktı klasörü açılmalı.
4. Aynı işlemi tekrar yap. Yeni sonuç `(2)` ile kaydedilmeli; önceki dosya
   değişmemeli. Ses adlarına program adı veya JSON raporu eklenmemeli.
5. Ayarlar'da MP3/WAV/FLAC/OGG ve mono/stereo tercihlerini değiştirip yeni
   sonuçların bu tercihle kaydedildiğini dene.

## 2. Ses kalitesi

- **Vokal:** kullandığın temizleme adımlarını ve sesin nasıl değiştiğini anlat.
  Örneğin “Kelimeler kayboluyor”, “Yankı kaldı” veya “Ses metalik oldu”.
- **Onarım:** arka vokal temizliğini açınca kısa vokal onarımı seçeneği görünür.
  Varsayılan kapalıdır. Açıp standart ve onarılmış dosyayı karşılaştır; onarımın
  iyi/kötü etkilediği bölümü söyle. Uzun kayıp cümleleri tamamlaması beklenmez.
- **Enstrüman:** dört/altı kanal sonuçlarını ayrı dinle; diğer seslerin hangi
  kanala sızdığını anlat. Gitar/piyano ayrımı deneyseldir.
- **Ses değiştirme:** aynı kısa vokalle seçtiğin modeli dinle; anlaşılmayan
  kelime, benzerlik veya perde sorunu varsa belirt.

A2SB ve altı kanallı HTDemucs için koşullar gösterilir; kabul etmezsen işlem
başlamamalı. Sesleri internete yüklemen gerekmez; dosyalar bilgisayarında işlenir.

## 3. Eğitim

1. Aynı kişiye ait, mümkünse farklı bölümler içeren temiz kayıtlar ekle.
2. **Kayıtları eğitim başlatmadan incele** düğmesini kullan; anlaşılmayan uyarıyı aktar.
3. İlk işleyiş denemesi için kısa eğitim ayarı hazırlanır. Kayıt aralığına `2`,
   tutulacak son model sayısına `3` gibi küçük değerler yaz. Az tekrar,
   düğmelerin çalışmasını gösterir; iyi ses modeli kanıtı değildir.
4. Eğitim sonucundaki modelleri aynı test kaydıyla dinle. Önce **index kapalı**
   seçimi modelin kendi sonucunu duymanı sağlar.
5. Daha uzun denemede **durdur ve kaydet**, **Eğitim oturumlarım** içinden
   **yarım kalan eğitime devam et** ve epoch modellerini AI Cover listesine
   ekleme akışlarını dene. Model klasöründe yalnız seçtiğin sayıda
   `Ad_Epoch_NNN.pth` ve tek `Ad.index` bulunmalı; teknik eğitim dosyaları bu
   klasöre karışmamalıdır. Model kaydından sonra önerilen teknik dosya temizliğini
   onayla; bildirilen boşaltılan alan kadar oturum klasörü kalkmalı, özgün kayıtlar
   ve kalıcı modeller açılmaya devam etmelidir.

Kayıt incelemesi, ara modeller, oturumlar, şablonlar ve eğitim sırası zaten
vardır. İyileştirmeler gerçek kullanımda zor gelen adıma ve duyulan sonuca göre seçilir.

## 4. Klavye ve hatalar

Tab/ok/Boşluk ile kontrollerin adını, açık/kapalı durumunu, kısa ayar özetini ve
sonuçları NVDA/JAWS ile dinle. “Şurada sustu”, “Aynı yazıyı iki kez okudu” veya
“Buradan sonra ne yapacağımı anlayamadım” demen yeterli.

Hata olursa son yaptığın işlemle birlikte mesajı bildir. Günlük dosyasını bulman
veya hatayı kendin çözmen beklenmez. Yayın öncesinde yeni installer'ın temiz
Windows'ta kurulması ve eski sürümden güncellenmesi geliştirme tarafında ayrıca sınanır.

## 5. Canlı AI Cover — deneysel

23 Ekim 2026 tarihinde yenilenen 2.1.0 kurulumunda **4. Canlı AI Cover**,
ardından **5. Ayarlar** görünmelidir. Önceki 2.1.0 kurulumları otomatik
güncelleme bildirimi almaz; aynı CPU/CUDA paketini elle yeniden kurun.

1. Kulaklık tak; AI Cover'a eklediğin modeli, mikrofonu ve dinleme aygıtını seç.
2. **Canlı dinlemeyi başlat** düğmesine basıp kısa cümleler söyle. Hangi sesi
   duyduğunu, konuşmanın anlaşılırlığını, kesinti veya rahatsız eden gecikmeyi anlat.
   Model ve aygıtlar hazır olduğunda seçilen çıkıştan kısa hazır sesi gelmeli;
   bu sesten sonra konuşmaya başlayabilmelisin.
3. 250/500/1000 ms parça sürelerini ayrı dene. Bu seçenekler toplam gecikme
   değildir; duyduğun gecikmeyi ve atlanan parça sayısını birlikte değerlendir.
   **Ses eşiği** -45 dB'den başlar; dip sesi devam ederse dinlerken -35 dB gibi
   daha yüksek bir eşik dene. Konuşma durunca model beklemeli ve dip sesi
   kesilmeli; konuşunca tekrar açılmalıdır. Eşiği fazla yükseltmek zayıf heceleri kesebilir.
4. **Canlı dinlemeyi durdur** sonrasında mikrofon göstergesi kapanmalı,
   kulaklıktan ses kesilmeli ve diğer işlemler yeniden başlayabilmeli.
5. Mikrofon çıkarılırsa anlaşılır hata beklenir. Tekrar bağlayıp listeyi
   yenilemek ve yeniden başlatmak mümkün olmalı.
6. Çıkış olarak Line 2 seçildiğinde **Doğrulanmış ses yolu** Line 2'yi
   göstermeli. Çıkış kaybolursa varsayılana geçilmemeli. Günlüğe sürekli
   satır eklenmemeli; yalnız **Mikrofon açıldı.** bir kez görünmelidir.
7. Dinleme kapalıyken **Otomatik ayarla (10 saniye sessizlik)** düğmesine bas.
   Konuşmadan 10 saniye bekle; geri sayım durum alanında görünmeli. Sonunda
   **Dinleme tamamlandı** penceresinde **Ayarlandı. Mikrofon kapatıldı.** yazmalı ve Windows mikrofon göstergesi
   kapanmalıdır. Kulaklığa/Line 2'ye ölçüm sesi gönderilmemelidir. Model seçili
   veya hazır olmasa da yalnız mikrofon seçimiyle bu ölçüm yapılabilmelidir.
8. Ölçümü **Ölçümü iptal et** ile yarıda kes: önceki eşik korunmalı, mikrofon
   kapanmalıdır. Geçersiz/yüksek/değişken ölçümde de önceki ayar korunmalıdır.
   Başka mikrofon seçince yeniden ölçüm istenmeli. Başarılı ölçümden sonra
   canlı dinlemeyi başlat; sessizken gürültü kesilmeli, kelime sonları ve kısa
   heceler korunmalıdır. Ölçüm günlüğü de yalnız bir açılış satırı içermelidir.
9. Ses eşiğine **-100** veya **-120,5** yaz: değer -80'e geri çekilmemeli.
   Dinleme sürerken geçerli değer motora aktarılmalı; sayıyı yazarken geçici
   boş/eksik giriş, son geçerli canlı eşiği değiştirmemelidir. Otomatik ölçüm
   sonucundaki pencere kapanana kadar mikrofon tekrar açılmamalıdır.
10. İşlem, enstrüman ve model seçimlerinde NVDA kontrolü **onay kutusu** olarak,
    her öğeyi de gerçek değerine göre **işaretli** veya **işaretli değil** diye
    okumalıdır. Seçim değişince aynı öğe sürekli işaretli kalmamalıdır.

Canlı dinleme ses dosyası üretmez. Ayrıntılı kullanım ve teknik sınırlar
[Canlı AI Cover](CANLI_AI_COVER.md) belgesindedir.

Ayrıntılar: [enstrüman ayırma](ENSTRUMAN_AYIRMA.md),
[vokal onarımı](VOKAL_ONARIMI.md), [model eğitimi](MODEL_EGITIMI.md),
[donanım ve modeller](DONANIM_VE_MODEL_YONETIMI.md).
