# Kullanıcı denemesi

Güncelleme: **18 Ekim 2026**. Güncel test ve paket durumu
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
3. İlk işleyiş denemesi için kısa eğitim ayarı hazırlanır. Az tekrar,
   düğmelerin çalışmasını gösterir; iyi ses modeli kanıtı değildir.
4. Eğitim sonucundaki modelleri aynı test kaydıyla dinle. Önce **index kapalı**
   seçimi modelin kendi sonucunu duymanı sağlar.
5. Daha uzun denemede **durdur ve kaydet**, **yarım kalan eğitime devam et** ve
   modeli ses değiştirme listesine ekleme akışlarını dene.

Kayıt incelemesi, ara modeller, oturumlar, şablonlar ve eğitim sırası zaten
vardır. İyileştirmeler gerçek kullanımda zor gelen adıma ve duyulan sonuca göre seçilir.

## 4. Klavye ve hatalar

Tab/ok/Boşluk ile kontrollerin adını, açık/kapalı durumunu, kısa ayar özetini ve
sonuçları NVDA/JAWS ile dinle. “Şurada sustu”, “Aynı yazıyı iki kez okudu” veya
“Buradan sonra ne yapacağımı anlayamadım” demen yeterli.

Hata olursa son yaptığın işlemle birlikte mesajı bildir. Günlük dosyasını bulman
veya hatayı kendin çözmen beklenmez. Yayın öncesinde yeni installer'ın temiz
Windows'ta kurulması ve eski sürümden güncellenmesi geliştirme tarafında ayrıca sınanır.

Ayrıntılar: [enstrüman ayırma](ENSTRUMAN_AYIRMA.md),
[vokal onarımı](VOKAL_ONARIMI.md), [model eğitimi](MODEL_EGITIMI.md),
[donanım ve modeller](DONANIM_VE_MODEL_YONETIMI.md).
