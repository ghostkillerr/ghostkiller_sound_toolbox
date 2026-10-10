# AI Cover model eğitimi için araştırma ve geliştirme promptu

Aşağıdaki metin ayrı bir araştırma/geliştirme çalışmasında kullanılabilir. Bu dosya eğitim özelliğini eklemez. Kaynakların güncelliği çalışmanın yapıldığı tarihte yeniden doğrulanmalıdır.

---

Ghostkiller Sound Toolbox projesine, kullanıcının ses kayıtlarını seçerek AI Cover için kendi ses modelini oluşturabileceği bir eğitim özelliği tasarla. Önce araştırmayı ve uygulanabilir mimariyi tamamla; ardından aşamalı uygulama planı çıkar. Bu ilk aşamada kodu değiştirme.

Önce oku.md, sonra depodaki tüm Markdown belgelerini ve aktif kodu incele. Mevcut proje Windows üzerinde Python/wxPython ile çalışıyor; yerel ses ayrıştırma, gömülü RVC dönüşümü, ortak CPU/GPU seçimi, model bütünlüğü yönetimi ve iş kilidi içeriyor. Eğitim kaynakları daha önce kullanılmadıkları için kaldırıldı. Bunları eski sürümden körlemesine geri getirme. Kullanıcının mevcut değişikliklerini ve kişisel modellerini koru.

Araştırmanın tarih sınırı 11 Ekim 2026 olsun. Bu tarihe kadar yayımlanmış en güncel kararlı kaynakları araştır; daha sonraki yayınları kullanma. Kararlı sürüm, deneysel dal ve nightly sürümü ayır. Her teknik öneri için resmî belge, yayın, kaynak deposu veya sürüm notuna bağlantı ver; mümkünse sürüm, commit ve yayın tarihini belirt. Kanıt bulunmayan desteği varsayma.

Başlangıç kaynakları:
- Applio kaynakları ve sürümleri: https://github.com/IAHispano/Applio ve https://github.com/IAHispano/Applio/releases
- RVC ana kaynakları: https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- PyTorch kurulum ve platform desteği: https://pytorch.org/get-started/locally/
- AMD ROCm Radeon/Ryzen belgeleri: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/
- NVIDIA CUDA/PyTorch belgeleri, seçilen modelin resmî eğitim kodu ve lisansı.

1. Model ve motor seçimi

Mevcut VoiceConverter tarafından yüklenebilen RVC modellerini önceliklendir. RVC/Applio eğitim ve finetuning seçeneklerini güncel ses dönüştürme yaklaşımlarıyla karşılaştır. Daha yeni bir yaklaşımın bu projeye geçiş maliyetini, çıktı formatını, inference uyumluluğunu, donanım ihtiyacını ve lisansını açıkla. En yeni adı seçmek yerine sürdürülebilir ve test edilebilir çözümü gerekçelendir. Pretrained model üzerinden eğitim ile sıfırdan eğitimi ayır. Çok konuşmacılı tek model ile farklı kişilere ait ayrı modellerin farkını anlat.

2. Kayıttan modele kadar tam süreç

Kullanıcı WAV/FLAC/MP3 kayıtlarını veya kayıt klasörünü seçsin. Gerekirse tek uzun kaydı parçalara ayırabilsin. Dosya çözümleme, kanal/örnekleme hızı normalizasyonu, sessizlik ve clipping tespiti, gürültü/yankı kontrolü, konuşmacı karışıklığı, müzikten vokal ayırma, segmentleme, veri bölme, içerik özellikleri, F0 çıkarımı, eğitim, checkpoint, doğrulama, FAISS index, dışa aktarma ve AI Cover listesine ekleme adımlarını açıkla.

Kayıt süresi ve kalite önerilerini kaynaklandır; garanti süre veya kalite uydurma. Temiz ses ile aşırı işlenmiş sesin eğitimdeki etkisini anlat. Eğitim/doğrulama/test verilerini ayır; aynı kaydın komşu parçalarının veri sızıntısına yol açmasını önle. Kullanıcı orijinalleri değişmesin. Veri az veya kalitesizse anlaşılır bir ön kontrol sonucu gösterilsin. Kayıt sahibi/izin bilgisi proje metadatasında tutulabilsin.

3. NVIDIA, AMD ve CPU desteği

Windows yerel çalıştırma, WSL2 ve Linux yollarını ayrı değerlendir. NVIDIA için CUDA/PyTorch/sürücü/Python uyumluluğunu; AMD için desteklenen GPU mimarilerini, ROCm sürümünü ve işletim sistemi sınırlarını resmî matrislerden doğrula. Bir backend'in inference yapabilmesi, eğitim ve gradient/backward işlemlerini desteklediğinin kanıtı değildir.

CPU eğitimini gerçek eğitim koduyla doğrula; desteklenen ve pratik olanı ayır. Tahmini hız/RAM/VRAM sayılarını ölçüm olmadan kesin sunma. DirectML, ZLUDA veya benzeri yolları ancak seçilen eğitim zincirinin operatör ve backward desteği kanıtlanırsa öner; deneysel durumunu belirt. Tüm AMD kartlarına veya tek CUDA EXE'sine genel destek sözü verme.

Her backend için ileri geçiş, loss, backward, optimizer adımı, checkpoint kaydetme/yükleme ve kısa gerçek eğitim testi öner. Otomatik batch ayarı, düşük bellek modu ve FP32/FP16/BF16 seçimini donanım ve model uyumluluğuna bağla. Desteklenmeyen GPU'da CPU'ya geçişi kullanıcıya açıkla.

4. Çoklu kullanım ve kaynak yönetimi

Birden fazla ses projesi, dataset, model sürümü ve eğitim işi yönetilebilsin. Kullanıcılar birbirlerinin kayıtlarını ve çıktılarını ezmesin. Masaüstünde birden fazla proje/kullanıcı profili ile ağ üzerinden eşzamanlı çok kullanıcılı servis ihtiyacını ayrı açıkla; servis gereksinimi net değilse tek kısa kapsam sorusu sor. Sunucu yüklemesini varsayılan olarak ekleme.

Her işin benzersiz kimliği, dizini, durumu, günlüğü ve sahipliği olsun. Kuyruk adil olsun; CPU/RAM/VRAM limitleri ve cihaz başına çalışma kapasitesi bulunsun. Kuyrukta birden fazla iş olması aynı GPU'da sınırsız paralellik anlamına gelmesin. Çoklu GPU ve distributed training ayrı, ölçülmüş bir özellik olarak ele alınsın.

Mevcut JOB_LOCK ile uyumlu bir geçiş tasarla. Eğitim, cover, ayrıştırma ve model indirme işlerinin kaynak çakışmalarını ele al. Uzun eğitimi ayrı worker süreçlerinde yürütme seçeneğini; Windows spawn, PyInstaller ve süreç iletişimi açısından değerlendir.

5. İş yaşam döngüsü ve kurtarma

Durumlar en az sırada, hazırlanıyor, eğitiliyor, doğrulanıyor, tamamlandı, başarısız, iptal edildi olsun. Checkpoint atomik kaydedilsin. İptal ve uygulama kapanışında son sağlam checkpoint korunsun; uyumlu checkpoint'ten devam edilebilsin. Resume için optimizer/scheduler ve rastgelelik durumunu da değerlendir. Disk dolması, OOM, bozuk veri, worker çökmesi ve kopan UI sonrası kurtarma tasarla. Model yalnızca dışa aktarma ve inference doğrulaması geçince AI Cover listesine eklensin.

6. Erişilebilir kullanıcı deneyimi

Türkçe, standart wx kontrolleri, yalnız klavyeyle kullanım ve NVDA/JAWS erişilebilirliği korunmalı. Basit akış: Kayıt seç → Kaliteyi kontrol et → Model adı/donanım seç → Eğit → Deneme sesi oluştur → AI Cover'a ekle. Teknik seçenekler gerektiğinde gelişmiş ayarlarda sunulsun. İlerleme aşaması, epoch, süre ve sonuç metin olarak okunabilsin; günlük odağı zorla taşımasın. Süre tahmini ölçüm yokken gösterilmesin. Ekran okuyucu uyumluluğunu canlı test yapılmadan doğrulanmış sayma.

7. Kalite ve kabul ölçütleri

Loss azalması tek başına iyi ses modeli kanıtı olmasın. Eğitim dışında ayrılmış konuşma ve şarkı örnekleriyle ses benzerliği, anlaşılırlık, pitch davranışı, artefaktlar ve overfitting değerlendirmesi öner. Otomatik metriklerle işitsel değerlendirmeyi ayır. Farklı kullanıcılara ait datasetlerin karışmaması, iptal, resume, eksik pretrained dosya, CPU/GPU hataları ve çıktı koruma için anlamlı regresyon testleri planla.

8. Dağıtım ve teslimatlar

Python ve bağımlılık sürümleri sabitlensin; CPU/CUDA/ROCm ortamları ayrı ve yeniden üretilebilir tanımlansın. Model ağırlıkları, kişisel kayıtlar ve eğitim datasetleri Git'e veya setup'a girmesin. Ortak yönetilen modeller models/ altında kalsın; eğitim çalışma verileri normal kullanıcı hesabında yazılabilir ayrı dizinde tutulsun. Upstream lisans/dağıtım koşullarını kontrol et.

Sonuç olarak Türkçe bir rapor ver: kaynaklandırılmış yaklaşım karşılaştırması, önerilen motor ve gerekçesi, platform/donanım destek matrisi, kayıt hazırlama rehberi, süreç ve veri mimarisi, erişilebilir ekran akışı, aşamalı uygulama planı, bağımlılık/dağıtım planı ve test kabul ölçütleri. Doğrulanmış bilgiyi, öneriyi ve henüz test edilmemiş varsayımı açıkça ayır. Ardından bu projeye uygulanacak küçük ilk geliştirme adımını tarif et.
