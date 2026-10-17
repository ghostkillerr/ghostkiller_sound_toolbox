# Projenin güncel durumu — 17 Ekim 2026

Kaynak sürümü **2.1.0**, durum **yayın hazırlığında**. GitHub'a kaynak göndermek
kurulu programları güncellemez; installer Release henüz yayımlanmadı.
Kullanım rehberleri [belgeler dizininde](README.md) toplanır.

Kişisel ayar/model kayıtları Git dışındadır. Yerel yollar ve model adları
içerebilen eski JSON raporları `build/local_reports/` klasörüne taşındı.
Kullanıcıya ait model adları kaynak ve rehberlerden çıkarıldı; özel veri
ve mutlak kullanıcı yolu kontrolü Git indeksi üzerinde ve CI'de uygulanır.
Genel mimari config'leri uygulamanın çalışması için kaynakta korunur.

## Tamamlanan düzeltmeler

- Dört kanallı SCNet ve deneysel altı kanallı HTDemucs ile ayrı stereo PCM24
  FLAC çıktıları kaynakta hazırdır. Ses seviyesi düzenleyen yeniden miksleme
  ekranı yoktur; gitar/piyano kalitesi ayrıca dinlenmelidir.
- Enstrüman ayırmada zorla durdurma veya worker çöküşü sonrası geçici dosyaları
  ana süreç temizler; yalnız tamamlanan sonuçlar yayımlanır.
- Kayıt incelemesinin son hash okumasına iptal iletilir. İptal edilen analiz
  başarılı sonuç olarak gösterilmez.
- Yayın manifesti CPU/CUDA paketlerinin aynı ve güncel kaynakla üretilmesini ister.
- A2SB'nin ticari olmayan, HTDemucs ağırlıklarının bilimsel kullanım koşulları
  indirme ve çalıştırma öncesinde gösterilir. Kabul edilmeden işlem başlamaz.
- İsteğe bağlı vokal onarımında bir saat sınırı kaldırıldı; RAM ön kontrolü
  vardır. Standart ve onarılmış mono sonuç ayrı saklanır.
- Enstrüman kanal düğmeleri vokal işlemedeki ortak **[AÇIK]/[KAPALI]** ad ve
  erişilebilirlik bildirimlerini kullanır. **Kullanıcı bu okumanın çalıştığını
  doğruladı.** Bu kabul denenen kontrollerle sınırlıdır.

## Temizlik

İlk turda 71.066 eski dosya / 10,448 GiB kaldırılmıştı. Son GitHub hazırlığı
turunda ayrıca **967 dosya / 2,491 GiB** temizlendi:

- Güncel kaynağı içermeyen iki installer adayı ve üretilmiş Sandbox başlatıcıları.
- Eski test/kurulum fixture'ları, günlükler, ekran görüntüleri ve tek kullanımlık betikler.
- Önbellekler ve gerekli bilgileri güncel rehberlere taşınan 20 eski rapor.

156 kişisel model/ses/ayar/eğitim dosyasının boyut ve değişiklik zamanı korundu.
CPU/CUDA ortamları, Python, FFmpeg/toolchain/lisans-kaynak materyali, araştırma
modelleri ve Git kurtarma bundle'ları saklandı. `Setup/Yeni_Ozellikleri_Ac.cmd`
mevcut kaynaktan uygulamayı açmaya devam eder.

Temizlik listesi ve sonuçları yerelde `build/github_sync_20261017/` altındadır;
bu klasör ve kişisel veriler Git'e veya siteye eklenmez.

## Test ve paket durumu

Güncel kaynakta CPU ve NVIDIA CUDA ortamlarının **her birinde 329 test geçti**.
Sitenin dört Node testi ve yalnız kamuya açık dosyaları hazırlayan site üretimi
başarılı. Kullanım belgelerindeki yerel bağlantılar kontrol edildi; eksik yok.
Günlükler `build/github_sync_20261017/cpu-tests.log`, `cuda-tests.log` ve
`site-tests.log` dosyalarındadır. Hosted CI fiziksel GPU kabulü sayılmaz.

Önceki iki frozen aday; açılış, native kontroller, FFmpeg, ayrı ses/eğitim
worker'ları, gerçek SCNet/HTDemucs sentetik ayırma ve izole Inno kurulum
fixture'larından geçmişti. NVIDIA'da gerçek Torch/ONNX GPU ve A2SB kısa onarım
da doğrulandı. Bu sonuçlar tarihsel adaylara aittir; temizlenen installer'ların
yerine güncel kaynakla **CPU ve NVIDIA CUDA** yeniden üretilmelidir.

Özet kanıt `build/cleanup_fixes_20261017/candidate_verification.json`, son kaynak
durumu `build/training_release_verified.json` içindedir. `installer_rebuild_pending`
**true**, `release_ready` **false** durumundadır. Kök `version.json` yayımlanmamış
ve paketsiz kalır. Yeni antivirüs taraması veya kod imzalama yapılmadı.

## Yayından önce kalanlar

1. Gerçek sesle dört/altı kanal ayırmayı, standart/onarılmış vokali ve cover'ı
   sırayla dinlemek; eğitim, durdur/devam ve çıkan modelin kısa denemesini yapmak.
2. Diğer ekranlarda klavye ve ekran okuyucu kullanımını değerlendirmek.
3. Güncel iki installer'ı üretip frozen ve temiz Windows testlerini yapmak.
4. Aynı backend eski sürümden yükseltme, model/ayar koruma ve yönetici izninde
   kabul/iptal akışlarını sınamak; ardından gerçek Release ve indirmeleri açmak.

Kullanıcıdan kod, hash veya derleme komutu beklenmez; ses ve kullanım geri
bildirimi yeterlidir. Ayrıntılar [kullanıcı kabulünde](KULLANICI_KABULU.md).
