# İsteğe bağlı kısa vokal onarımı

Müzik ve ses temizleme sekmesinde **3. Arka Vokalleri ve Harmoni Seslerini
Temizle** açıkken hemen altında **Arka vokal temizliğinden sonra kısa vokal
kayıplarını onar** seçeneği görünür. Varsayılan kapalıdır. Arka vokal temizliği
kapatılınca bu seçenek de kapanır ve gizlenir.

Normal sonucu almak için onarımı kapalı bırak. İkisini karşılaştırmak için
onarımı açıp ses temizlemeyi başlat. Standart temizlenmiş dosya ile
`Onarilmis_Mono_Vokal.flac` son ekli dosya ayrı kaydedilir. Sonraki yankı/gürültü
adımları da seçiliyse onarılmış sonuçtan devam eder. Onarım başarısız olursa
tamamlanan standart sonuç korunur.

Bu deneysel yöntem kısa kayıp aralıklarını A2SB ile üretir. Üretilen ses kayıp
yerin çevresine yumuşak geçişle yerleştirilir. Temizleme öncesi vokal sonuçla
karıştırılmaz. Model tek kanallı olduğu için onarılmış çıktı **mono** olur;
standart sonuç kendi kanal sayısını korur. Uzun kayıp cümleler bu yöntemle
tamamlanmaz. Doğru söz, nota ve ana sesin korunması dinleyerek değerlendirilir.

Model gerekirse Ayarlar'daki **Kısa vokal kayıplarını onar: A2SB
(araştırma/değerlendirme)** kaydından indirilip kontrol edilir. Boyutu yaklaşık
2,26 GB'dır; CPU'da daha yavaş çalışabilir. Model NVIDIA'nın ticari olmayan
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
dosya korumasını doğrular. CPU ve NVIDIA ortamlarında 307'şer otomatik test geçti.
Canlı NVDA konuşması için kullanıcı dinlemesi ayrıca
gerekir. Gerçek CUDA işleyicisi kayıt örneğinde onarım, ilerleme, iptal ve PCM24
kaydını doğruladı. Bunlar bütün şarkıların ses kalitesi kabulü değildir.

Bu seçenek güncel CPU ve NVIDIA CUDA 2.1.0 yerel kurulumlarına da eklendi.
Paketli işleyicide CPU başlangıcı ve NVIDIA'da gerçek A2SB üretimi doğrulandı.
Kurulumlar henüz GitHub Release olarak yayımlanmadı; temiz Windows ve dinleme
kabulü ayrıca bekliyor. [Güncel kurulum kanıtı](KURULUM_YENIDEN_DERLEME_2026-10-16.md).
