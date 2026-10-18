# İsteğe bağlı kısa vokal onarımı

Kayıt uzunluğu için bir saat sınırı kaldırıldı. Sesler parça parça okunur ve
yeniden örneklenir; onarımın çalışma dizileri yine RAM'de tutulur. Bellek
ihtiyacı dosyalar tamamen okunmadan önce kontrol edilir. Uzun kayıtlar daha
fazla bellek ve zaman gerektirir; belleği yetersiz bilgisayarda işlem açıklayıcı
mesajla durur. Bu değişiklik kaynak kodunda uygulanıp sınandı.
Güncel paket ve doğrulama sonucu [Son durum](SON_DURUM.md) içindedir.

Müzik ve ses temizleme sekmesinde **3. Arka Vokalleri ve Harmoni Seslerini
Temizle** açıkken hemen altında **Arka vokal temizliğinden sonra kısa vokal
kayıplarını onar** seçeneği görünür. Varsayılan kapalıdır. Arka vokal temizliği
kapatılınca bu seçenek de kapanır ve gizlenir.

Normal sonucu almak için onarımı kapalı bırak. İkisini karşılaştırmak için
onarımı açıp ses temizlemeyi başlat. Standart temizlenmiş dosya ile
`Onarilmis_Vokal` adını taşıyan dosya ayrı kaydedilir. Dosya uzantısı
**Ayarlar → Ses dosyası biçimi** bölümünde seçilen MP3, WAV, FLAC veya OGG olur.
Sonraki yankı/gürültü adımları da seçiliyse onarılmış kayıpsız geçici sesten
devam eder; sıkıştırılmış çıktı yeniden işlenmez. Onarım başarısız olursa
tamamlanan standart sonuç korunur.

Çıktı adlarına program adı eklenmez. Aynı ad varsa `(2)`, `(3)` eklenerek önceki
sonuç korunur. İşlem sonucu mesajı kapatılınca çıktı klasörü açılır.

Bu deneysel yöntem kısa kayıp aralıklarını A2SB ile üretir. Üretilen ses kayıp
yerin çevresine yumuşak geçişle yerleştirilir. Temizleme öncesi vokal sonuçla
karıştırılmaz. Model tek kanallı ses üretir. **Ayarlar → Ses kanalı düzeni**
seçeneğiyle kaydı mono veya stereo yapabilirsiniz; mono ses stereo kaydedilirse
aynı ses iki kanala yazılır. **İşlemin kanal düzenini koru** seçilirse onarım
mono kalır; standart sonuç kendi kanal sayısını korur. Uzun kayıp cümleler bu yöntemle
tamamlanmaz. Doğru söz, nota ve ana sesin korunması dinleyerek değerlendirilir.

Model gerekirse Ayarlar'daki **Kısa vokal kayıplarını onar: A2SB
(ticari olmayan kullanım)** kaydından indirilip kontrol edilir. Boyutu yaklaşık
2,26 GB'dır; CPU'da daha yavaş çalışabilir. İndirme veya ilk kullanım
öncesinde model koşulları gösterilir; kabul edilmezse işlem başlamaz. Model NVIDIA'nın ticari olmayan
lisansına tabidir. Ayrıntılar `restoration/vendor/` içindeki lisans/NOTICE
dosyalarındadır. Bu bilgisayarda mevcut ağırlık doğrulanıp hazırlandı.

## Klavye ve NVDA

- Tab ile arka vokal düğmesine gel; Boşluk tuşuyla aç.
- Sonraki Tab, görünen onarım düğmesine gider. Boşluk tuşu seçimi değiştirir.
- Etiket `[AÇIK]` veya `[KAPALI]` içerir; erişilebilirlik arayüzü basılı/basılı
  değil durumunu, adı, açıklamayı ve aç/kapat eylemini sunar.
- Ana seçenek kapatılınca gizlenen onarım düğmesi Tab sırasında atlanır.
  Odak bu düğmedeyken gizlenirse arka vokal düğmesine geri alınır.
- İşlem sırasında seçenekler kilitlenir; İptal et ve Zorla durdur korunur.

Yerel kontroller görünürlük, Tab sırası, erişilebilir rol/ad/durum/eylem ve
dosya korumasını doğrular. Güncel CPU/CUDA test sonucu [Son durum](SON_DURUM.md) dosyasındadır.
Canlı NVDA konuşması için kullanıcı dinlemesi ayrıca
gerekir. Gerçek CUDA işleyicisi kayıt örneğinde onarım, ilerleme, iptal ve PCM24
kaydını doğruladı. Bunlar bütün şarkıların ses kalitesi kabulü değildir.

Önceki paketli işleyicilerde CPU başlangıcı ve NVIDIA'da gerçek A2SB üretimi
doğrulanmıştı. Eski kurulum adayları temizlikte kaldırıldı; yayın için güncel
kaynakla iki yeni paket gerekir. Güncel durum ve kalan kabuller için
[Son durum](SON_DURUM.md) dosyasını esas alın.
