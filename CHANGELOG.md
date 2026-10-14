# Sürüm notları

Ghostkiller Sound Toolbox'ın kullanıcıya yansıyan önemli değişiklikleri burada
toplanır. Küçük teknik düzeltmeler ilgili özelliğin altında birleştirilir.

## 2.0.0 — Yayın hazırlığında

CPU ve NVIDIA CUDA kurulumları için hazırlanan sürüm. GitHub'da henüz indirilebilir
bir Release yayımlanmadı; aşağıdaki yenilikler mevcut kaynak kodunun kapsamıdır.
Kurulum kabul testleri tamamlandığında gerçek yayın tarihi ve indirmeler eklenecek.

### Ses araçları ve model eğitimi

- **Vokal ve müzik ayrıştırma:** ana vokal, enstrümantal, arka vokal, yankı ve
  gürültü temizleme adımları aynı iş akışında kullanılabilir.
- **Yerel RVC ile ses değiştirme:** kişisel ses modeli ve isteğe bağlı index
  dosyası eklenebilir. Pitch, index ve perde işlemlerinin hata denetimleri
  geliştirildi; ses dosyaları yerel işlenir.
- **RVC V2 model eğitimi:** kayıt hazırlama ve analiz, eğitim, durdurma/devam,
  değerlendirme ve index oluşturma tek sekmede toplandı. Eğitilen model ses
  değiştirmede kullanılabilir.

### Kullanım ve güvenilirlik

- **Ortak model ve donanım yönetimi:** işlemci/ekran kartı seçimi, eksik modelleri
  indirme, çevrimdışı dosya kontrolü ve bozuk dosyaları onarma Ayarlar'da toplandı.
- **Erişilebilir arayüz:** Türkçe native kontroller, klavye ile gezinme ve eğitim
  alanlarının açıklamaları düzenlendi. Açık/koyu görünüm tercihi kalıcı saklanır.
- **Daha dayanıklı işlemler:** ses ve eğitim işleri ayrı süreçlerde çalışır;
  hata ve iptal durumlarında önceki başarılı çıktılar ve kişisel veriler korunur.

### Kurulum ve güncellemeler

- **İki Windows x64 paketi:** CPU ve NVIDIA CUDA ayrı hazırlanır. Python,
  FFmpeg, uygulama ikonu, kullanım sözleşmesi ve bağımlılık lisansları paketlenir.
- **Program içinden güncelleme:** kurulu uygulama açılışta varsayılan olarak
  denetler ve doğrulanmış güncellemeyi aynı klasöre uygular. Otomatik denetim
  Ayarlar'dan kapatılabilir; elle denetleme düğmesi ve F5 kullanılabilir.
  Güncelleme kişisel model ve ayarları korur; Windows yönetici izni isteyebilir.
- **Tanıtım ve indirme sayfası:** programın özellikleri, paket seçimi ve ilk
  kullanım bilgileri [proje sitesinde](https://ghostkillerr.github.io/ghostkiller_sound_toolbox/)
  yer alır. İndirmeler doğrulanmış Release yayımlandığında açılır.

Yayın öncesi temiz Windows, gerçek donanım, NVDA/JAWS ve eski kurulumdan güncelleme
kabulü tamamlanmalıdır. Kaynak testleri bu kabulün yerine geçmez.

## Önemli geliştirme aşamaları

Bu tarihler kaynak geliştirme aşamalarını gösterir; ayrı dağıtım sürümleri veya
yayımlanmış güncellemeler değildir. Küçük düzeltmeler ve tekrar eden arayüz
çalışmaları ilgili aşamada birleştirilmiştir.

| Tarih | Kayda değer gelişme |
| --- | --- |
| 2–3 Ağustos 2026 | Modüler ses ayrıştırma ve gömülü RVC dönüşümünün temeli; pitch/index düzeltmeleri ve ses işleme iyileştirmeleri. |
| 8–11 Ekim 2026 | Ortak Ayarlar, donanım ve model yönetimi; erişilebilir model seçimi, güvenli iptal ve yerel verilerin paketlerden ayrılması. |
| 13 Ekim 2026 | Uygulama içi RVC V2 eğitimi, ayrı ses/eğitim süreçleri, model bütünlüğü denetimleri ve doğrulanan yayın paketlerinin altyapısı. |
| 14 Ekim 2026 | Açık/koyu görünüm ve eğitim erişilebilirliği; bağımsız CPU/CUDA kurulum hazırlığı, program içinden güncelleme ve GitHub tanıtım sayfası. |

## Sonraki yayınlar

Her kod değişikliği ayrı bir sürüm oluşturmaz. Birbiriyle ilgili geliştirmeler
test edilen tek sürümde toplanır. Her yayımlanmış sürüm için gerçek tarih,
kullanıcıya etkisi olan kısa yenilik/düzeltme listesi ve iki kurulum bağlantısı
eklenir. Ayrıntılı derleme ve yayın adımları [oku.md](oku.md) dosyasındadır;
indirilebilir sürümlerin kaydı [GitHub Releases](https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases)
sayfasıdır.
