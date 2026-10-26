# Vokal ve enstrüman işleme

26 Ekim 2026 tarihinde yenilenen 2.1.0 kurulumları bu akışları içerir.
Önceki 2.1.0 kullanıcıları aynı CPU/CUDA paketini elle yeniden kurmalıdır.


Birinci sekmenin başındaki **İşlem alanı** seçiminden çalışma türünü seçin.
**Vokal işleme**, önceki vokal ayırma ve temizleme seçeneklerini gösterir.
**Enstrüman işleme**, model ve kaydedilecek ses kanallarını gösterir.
Dosya ve çıktı klasörü iki görünümde ortaktır; seçim değiştirmek işlem başlatmaz.

## Enstrümanları ayırma

1. Mümkünse özgün şarkıyı seçin. Elinizde yalnız enstrümantal dosya varsa onu
   da kullanabilirsiniz; sonuç kalitesi ayrıca dinlenmelidir.
2. İşlem alanını **Enstrüman işleme** olarak değiştirin.
3. **Ayırma yöntemi** listesinden seçim yapın.
   **Deneysel (6 ayrı ses; gitar ve piyano dahil)**: bas, davul, gitar, piyano, vokal ve diğer
   enstrümanlar. Bu ağırlıklar yalnız bilimsel amaçlarla sunulur. Gitar ve
   özellikle piyano deneysel çıktılardır.
   **Standart (4 ayrı ses)** (başlangıç tercihi): bas, davul, vokal ve diğer enstrümanlar.
   Bu model gitarı ve piyanoyu ayrı çıkarmaz.
4. **Kaydedilecek ayrı sesler** bölümünde **Bası Ayır**, **Davulu Ayır**
   gibi seçeneklerden kaydetmek istediklerinizi **[AÇIK]**, istemediklerinizi
   **[KAPALI]** yapın. Tab ile seçeneğe gidip Boşluk tuşuyla durumunu
   değiştirebilirsiniz. Ardından **Enstrüman ayırmayı başlat** düğmesine basın.
   Daha az kanal seçmek model hesabını azaltmaz;
   yalnız kaydedilen dosyaları azaltır.

Her çalıştırma çıktı klasöründe `sarki_Enstrumanlar` adında yeni bir klasör
oluşturur. Ad kullanılıyorsa `(2)`, `(3)` eklenir. Sonuç mesajı kapatılınca bu
klasör otomatik açılır. Önceki sonuçlar ve giriş dosyası değiştirilmez.
Kanallar 44,1 kHz olarak, **Ayarlar → Ses dosyası biçimi** bölümünde
seçtiğiniz **MP3, WAV, FLAC veya OGG** biçiminde kaydedilir. WAV ve FLAC çıktılar
24 bittir. Sonuç klasörü yalnız seçtiğiniz ses dosyalarını içerir;
`separation.json` üretilmez. Aynı biçim tercihi vokal temizleme, AI Cover ve
eğitim test seslerinde de kullanılır.
**Ses kanalı düzeni** listesinden Mono veya Stereo seçerek kaydedilecek kanal
sayısını belirleyebilirsiniz. **İşlemin kanal düzenini koru** seçilirse
enstrümanlar stereo kaydedilir.
Ses taşması varsa bütün seçili kanallar aynı oranda kısılır; her kanal ayrı
normalleştirilmez. Bu bölüm henüz ses seviyesi düzenleyen bir yeniden miksleme
ekranı değildir; kanalları ayrı dosyalara ayırır.

## Model hazırlığı ve erişilebilirlik

Ayarlar'dan **Enstrüman ayırma** modelini bir kez indirin veya kontrol edin.
SCNet ve altı kanallı Demucs isteğe bağlıdır; standart model seçimlerine
kendiliğinden eklenmez. Bu geliştirme bilgisayarında iki model indirildi ve
kontrol edildi. CPU ve NVIDIA aynı ağırlıkları kullanır; sesler internete
yüklenmez. Çalışma sırasında model indirilmez.

Tab ile işlem alanı, dosya/klasör, model, düz yazı açıklama ve kanal seçimleri
arasında ilerleyebilirsiniz. Kanal düğmeleri vokal işlemedekiyle aynı
erişilebilirlik mantığını kullanır; adları her değişimde **[AÇIK]** veya
**[KAPALI]** olarak güncellenir. Seçili görünüm dışındaki kontroller gizlenir.
Dört kanallı modele geçince gitar/piyano kontrolleri gizlenir ve görünür
seçenekler yeniden numaralanır. Yöntemin açıklaması da seçime göre değişir. İşlem
sırasında seçimler kilitlenir; İptal et ve Zorla durdur kullanılabilir.
Kanal düğmelerinin açık/kapalı okuması 17 Ekim kullanıcı denemesinde doğrulandı;
bu, bütün uygulamanın ekran okuyucu kabulünün tamamlandığı anlamına gelmez.

Sabit bir şarkı süresi sınırı yoktur. Ses parça parça işlenir; süre arttıkça
disk ihtiyacı ve işlem süresi artar. Disk ihtiyacı çözümlemeden önce kontrol
edilir. Sonuç klasörü ancak bütün seçili kanallar hazır olduğunda yayımlanır;
iptal veya hatada yarım sonuç grubu bırakılmaz.

## Modeller ve doğrulama kapsamı

SCNet kaynakları `5d95bf96b19c3eede63248d171efeca8e3abb948` sürümünden alındı;
MIT lisansı ve ağırlık açıklaması `instruments/vendor/NOTICE.md` içindedir.
Altı kanallı HTDemucs mevcut sabit audio-separator kütüphanesindeki mimariyi
kullanır. Resmi ağırlığın SHA-256 kimliği sabittir; yükleme `weights_only=True`
ve yalnız bilinen sınıf izinleriyle yapılır. Demucs geliştiricisi, ağırlıkların
MIT lisansına dahil olmadığını ve yalnız bilimsel amaçlarla sunulduğunu
[açıklıyor](https://github.com/facebookresearch/demucs/issues/327).
İndirme ve kullanım öncesinde bu sınır gösterilir; koşullar kabul edilmeden
işlem başlamaz. Model kurulum paketine gömülmez.

CPU ve NVIDIA'da iki modelle gerçek, sentetik stereo kayıt ayırması geçti.
NVIDIA native worker üzerinden ayrıca bas/davul çıktısı üretildi. Bu testler
dosya, süre, kanal sayısı ve işleyişi doğrular; gerçek şarkı kalitesi veya
gitar/piyano başarısı garantisi değildir. Son paket adaylarının yerel kanıtları
`build/cleanup_fixes_20261017/candidates/cpu-optional-models.json` ve
`cuda-optional-models.json` dosyalarındadır; kişisel kayıt içermez.

Enstrüman ayırma 26 Ekim 2.1.0 CPU/CUDA kurulumlarında bulunur. Yukarıdaki
yeni seçenek adları ve standart başlangıç tercihi 26 Ekim 2.1.0 yenilemesindedir. Test/paket ayrımı [Son durum](SON_DURUM.md) içindedir.
