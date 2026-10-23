# Kod incelemesi ve disk temizliği — 22 Ekim 2026

Bu belge 22 Ekim inceleme anını kaydeder. Sonraki 23 Ekim yayınında bu
düzeltmelerle CPU/CUDA kurulumları üretildi; güncel paket ve kabul kanıtları
[Son durum](SON_DURUM.md) içindedir.

Bu inceleme yerel kaynak ağacına aittir. Çalışma başlarken ağaçta mevcut olan
canlı ses, erişilebilirlik, epoch kaydı, eğitim ekranı ve tanıtım değişiklikleri
korundu. Aşağıdaki düzeltmeler bunların üzerine uygulandı. Mevcut installer'lar
yeniden üretilmedi; kaynak değişikliğiyle kurulum içeriği birbirine karıştırılmamalı.

## 1. Proje ne yapıyor, sorumluluklar nasıl dağılıyor?

Ghostkiller Sound Toolbox, Windows üzerinde çalışan Türkçe ve klavye/ekran
okuyucu kullanımını gözeten bir wxPython ses uygulaması. Ses işleme yerelde
yapılıyor. Model indirme ve güncelleme denetimi ayrı ağ işlemleri; ses dosyaları
bir sunucuya işlenmek üzere gönderilmiyor. Kaynaktaki arayüz beş sekmeli:
temizleme/ayırma, AI Cover, model eğitimi, deneysel canlı AI Cover ve ayarlar.
Tanıtım metninin anlattığı yayımlanmış 2.1.0 ile yeni kaynak özellikleri farklı
anları temsil ediyor; dört/beş sekme anlatımı bu bağlamda değerlendirilmeli.

| Katman | İncelenen sorumluluk ve veri akışı |
| --- | --- |
| Başlangıç | `main.py`, `source_runtime.py`: uygun hazır Python ortamı, kaynak/frozen/worker ayrımı, sekmeler ve açılış akışı. |
| Arayüz | `ui_separator.py`, `ui_cover.py`, `ui_training.py`, `ui_live_cover.py`, `ui_settings.py`: seçimleri toplama, iş başlatma, ilerleme, iptal ve sonuç gösterme. |
| İş koordinasyonu | `app_runtime.py`, `audio_service.py`, `audio_worker.py`, `native_process.py`: ortak iş kilidi, ana UI thread'ine dönüş, alt süreç sahipliği ve kapanış. |
| Dosyaya ses işleme | `separator_backend.py`, `separation_audio.py`, `instruments/engine.py`, `restoration/engine.py`, `rvc/infer/`: ayrıştırma, isteğe bağlı onarım, RVC dönüşümü. |
| Canlı ses | `live_audio.py`, `live_cover.py`, `live_gate.py`: Windows ses aygıtları, sınırlı kuyruk, dönüştürme, gate ve kalibrasyon. |
| Eğitim | `training/config.py`, `dataset.py`, `engine.py`, `storage.py`, `worker.py`, `service.py`, `experiments.py`, `preparation_cache.py`, `comparison.py`, `index.py`: veri hazırlığı, eğitim, devam, değerlendirme ve model kaydı. |
| Kalıcı veri | `app_settings.py`, `registry_store.py`, yeni `training/cleanup.py`: atomik JSON, eşzamanlı kayıt değişikliği ve güvenli oturum silme. |
| Modeller/donanım | `model_manager.py`, `model_download.py`, `hardware.py`, `compute_backend.py`: dosya bütünlüğü, indirme/onarım, cihaz seçimi ve hesaplama kontrolü. |
| Çıktı | `audio_export.py`: biçim/kanal seçimi, doğrulama ve mevcut sonucu koruyan dosya/klasör yayını. |
| Dağıtım | `updater.py`, `release_security.py`, `windows_installer.py`, `tools/release/`: sürüm/backend/hash kontrolü, güncelleme ve derleme girdileri. |

Dosyaya çalışan işlerde UI değerleri başlangıçta alınmalı; arka plan işi canlı
UI kontrollerinden ayar okumamalı. Ortak `JOB_LOCK` yalnız hesaplama bitene kadar
değil, son UI geri çağrısı tamamlanana kadar işi sahipleniyor. Ayrı motor süreci
ve Windows Job Object, alt süreçlerin uygulamadan kopup çalışmaya devam etmesini
önleyen yapılar. Bu ayrımı bozacak genel bir yeniden yazım yapılmadı.

Ayrıştırmada enstrümantal kol özgün girdiden çıkıyor; seçilen vokal temizleme
adımları kendi kolunda zincirleniyor. Standart ve onarılmış vokalin ayrı çıktı
olması korunuyor. Sonuçlar doğrulanmadan son dosya adına geçirilmemeli;
numaralandırma önceki başarılı çıktıyı koruyor. Ortak çıktı biçimi ve kanal
ayarları, eğitimde üretilen dinleme örneklerini de kapsıyor.

Eğitimde kaynak grupları ve holdout ayrımı, örtüşen parçalar oluşturulmadan
önce belirleniyor. Index eğitim özelliklerinden oluşturuluyor. Tam devam
checkpoint'i model ağırlığına ek olarak optimizer, scheduler, sayaç ve RNG
durumunu taşıyor. AI Cover'a kaydedilen küçük model bu tam devam kaydının
yerine geçmiyor. Teknik oturumu silmenin anlamı bu nedenle yalnız cache
silmekten daha geniş: o oturuma aynen devam etme olanağı da kalkıyor.

## 2. İncelemenin kapsamı ve yöntemi

Önce `AGENTS.md`, `oku.md`, güncel durum ve özellik belgeleri okundu; kod
sözleşmeleri ve korunacak veri yolları belirlendi. README, sürüm notları,
eğitim/çıkarım teknik belgeleri, derleme rehberi, donanım/model yönetimi,
canlı ses, enstrüman ayırma, vokal onarımı/araştırması, kullanıcı kabulü,
tanıtım metni ve vendor NOTICE dosyaları da kontrol edildi.

Başlangıç yapısal taraması **142 Python dosyası / 26.531 satır** kapsadı.
Bu sayı testleri ve yerel RVC kodunu da içeriyor; bütün üçüncü taraf ağların
matematiksel doğruluğunun satır satır ispatlandığı anlamına gelmiyor.
Elle inceleme, yukarıdaki modüllerin veri akışına, kilitlerine, hata/iptal
yollarına, dosya ömrüne ve testlerle korunmuş sözleşmelerine odaklandı.

Başlangıçta mevcut **441 test** CPU ortamında geçti. Bu sonuç yeni hataların
bulunmasına engel olmadı: kapsamda olmayan koşullar için regresyonlar eklendi,
eski davranışın başarısızlığı görüldü ve kod düzeltildi. Özellikle RVC index
seçimi, ONNX cihaz aktarımı ve eğitim temizliği için yalnız koda bakarak
varsayım yapmak yerine çalıştırılabilir örnekler kullanıldı.

## 3. Bulunan ve düzeltilen sorunlar

### 3.1 Başarısız bağlı eğitim, başlangıç checkpoint'ini kaybedebiliyordu — P1

Yeni bir eğitim başka bir oturumun `resume.pth` dosyasından başlayabiliyor.
Bu yeni oturum hata verse bile daha sonra devam ettirilebilir. Önceki temizleme
kontrolü `failed` durumunu bağımlılığı bitmiş gibi ele alıyordu; ana oturumun
silinmesi devam için gereken başlangıç dosyasını kaldırabiliyordu.

Temizlik artık tamamlanmamış bağlı oturumları durum adından bağımsız koruyor.
Oturum oluşturma ile silme/bağımlılık incelemesi aynı kök yaşam döngüsü kilidini
kullanıyor. Silinecek oturuma yeni bağımlılık eklenmesi bu kontrolün arasına
giremiyor. Başlangıç oturumu temizleniyorsa yeni eğitim oluşturma da reddediliyor.

Kod: `training/cleanup.py`, `training/service.py`.
Regresyon: `test_failed_child_still_needs_parent_for_resume`.

### 3.2 Temizlik, kayıtlı model veya başka eğitimin özgün sesini silebiliyordu — P1

Tamamlanmış oturum klasöründeki bir PTH/index elle AI Cover listesine
eklenmiş olabilir. Aynı klasördeki ses, başka bir eğitimin özgün veya bağımsız
karşılaştırma kaydı olarak da seçilmiş olabilir. Klasörün yalnız teknik
artifaktlardan oluştuğunu varsaymak bu referansları bozuyordu.

Silmeden önce model kayıtları ve oturumların kaynak/karşılaştırma yolları
kontrol ediliyor. Kayıtlı model klasör içindeyse temizlik duruyor. Frozen
uygulamada model listesi veri klasöründe tutulurken eski göreli yollar
program klasörüne göre çözülebildiği için iki kök de kontrol ediliyor.
Bozuk veya okunamayan kayıtlar boş liste kabul edilip geçilmiyor.

Oturum kökü ve içindeki symlink/junction yönlendirmeleri reddediliyor.
Oturumun çözümlenmiş yolu, eğitim kökünün doğrudan çocuğu olmak zorunda.

Regresyonlar: `test_registered_model_inside_session_blocks_cleanup`,
`test_legacy_relative_model_in_frozen_app_blocks_cleanup`,
`test_other_sessions_source_recordings_are_not_deleted`,
`test_session_root_junction_is_rejected_before_resolution`.

### 3.3 Yarım kalan silme, oturumu yanlış durumda bırakıyordu — P1

Windows'ta bir dosyanın kilitli olması gibi bir durumda `rmtree` bazı
dosyaları silip kalanlarda hata verebilir. Böyle bir oturumu yeniden
`completed` saymak, artık tam olmayan çalışma verisini kullanılabilir gösterir.
Silme durumu tanınıp yeniden denenemiyorsa kullanıcı da yarım klasörle kalır.

Silme öncesi `deleting` durumu atomik kaydediliyor. Dosya tanıtıcıları
bırakıldıktan sonra klasör siliniyor. Kısmi başarısızlıkta bu durum korunuyor;
işaret dosyası silinmişse mümkün olduğunda yeniden yazılıyor. Aynı temizlik
yeniden denenebiliyor. Denetleyici ve doğrudan worker girişi, bu durumdaki
oturumu çalıştırmadan reddediyor.

UI, **Temizlik yarım kaldı** durumunda yalnız temizliği yeniden deneme ve
teknik klasörü açma seçeneklerini sunuyor. Tamamlanmış eğitim/sonuç menüsü
gösterilmiyor. İsteğe bağlı hazırlık-cache dosyası bozuksa asıl silme başarıyla
tamamlandıktan sonra bunun yüzünden yanlış bir başarısızlık üretilmiyor;
bozuk cache içeriği korunuyor.

Regresyonlar: `test_partial_cleanup_keeps_tombstone_and_can_be_retried`,
`test_controller_rejects_cleanup_before_clearing_markers`,
`test_raw_worker_rejects_cleanup_without_mutating_session`,
`test_corrupt_optional_cache_does_not_report_completed_deletion_as_failed`.

### 3.4 Devam kontrolü ve UI iptal işareti oturum sahipliğini aşabiliyordu — P1

`validate_resume`, çalışan başka bir denetleyici/worker varken manifest'in
cihaz, model kökü veya çıktı ayarlarını güncelleyebiliyordu. UI başlangıç
yolunda iptal işaretinin kilit alınmadan kaldırılması da diğer işlemin
iptal isteğini silebiliyordu.

Devam doğrulaması artık hem denetleyici hem worker kilidi altında yapılıyor.
UI, dosyadaki iptal işaretine doğrudan dokunmuyor. Oturum kimliğini ve
işaretin temizlenmesini kilidi alan `TrainingProcess` yönetiyor; çok erken
gelen iptal isteği bellekte tutulup oturum sahiplenildiğinde uygulanıyor.

Regresyonlar: `test_resume_validation_does_not_modify_an_active_session`,
`test_ui_leaves_cancel_marker_for_the_locked_controller`.

### 3.5 Boyutu bilinmeyen indirme diski sınırsız kullanabiliyordu — P2

HTTP yanıtı `Content-Length` vermediğinde dosya boyutu üzerinden yapılan
başlangıç disk kontrolü etkisiz kalabiliyordu. Ayrıca küçük olması beklenen
JSON/YAML yapılandırmalarının indirme ve parser girişinde ayrı bir üst
sınırı bulunmuyordu.

Model dosyaları için **4 GiB**, JSON/YAML için **1 MiB** sınır eklendi.
Başlık bildiriyorsa okumadan önce, her durumda okunan toplam bayt üzerinden
kontrol ediliyor. Boyutu bilinmeyen akışta her blok öncesi boş alan yeniden
ölçülüyor; **64 MiB** pay korunuyor. Büyük yerel metadata da parse edilmeden
reddediliyor. Başarısız indirme önceki hedef dosyasını değiştirmiyor;
limit aşan parça tekrar kullanılmıyor. Mevcut ETag/Range devam davranışı korunuyor.

Kod: `model_download.py`, `model_manager.py`.
Regresyonlar: `test/test_download_limits.py`; mevcut sürdürülebilir indirme
testleri de tam paket içinde geçti.

### 3.6 Seçilen RVC index'i başka dosyayla değiştiriliyordu — P2

Eski kod, yolda `trained` varsa bunu `added` yapıp o konumda dosya arıyordu.
Bu işlem yalnız index dosya adına uygulanmıyordu; `trained_models` klasörü de
`added_models` olabiliyordu. Alternatif dosya varsa kullanıcının seçtiği index
yerine başka dosya dönüştürmeye giriyordu. Dosya yüklenebilir olduğu için
sonucun yanlış model özellikleriyle üretildiği açık hata vermeyebilirdi.

Bu örtük yol değişimi kaldırıldı. Seçilen dosya doğrudan mevcut güvenli index
yükleyicisine gidiyor; FAISS format ve boyut kontrolleri korunuyor.

Kod: `rvc/infer/infer.py`.
Regresyon: `test_selected_index_is_not_replaced_by_a_similarly_named_file`;
klasör ve dosya adındaki üç ayrı örnekte gerçek alternatif dosya oluşturuluyor.

### 3.7 ONNX, seçilen CUDA kartını almıyordu — P2

Donanım seçimi birden fazla uygun kartta en çok belleği olanı seçebiliyor.
PyTorch'a `cuda:1` aktarılırken ONNX sağlayıcısına yalnız sağlayıcı adı
veriliyordu; cihaz numarası yoktu. İki motorun aynı kartta çalışacağı
sözleşmesi sağlanmıyordu.

`separator_backend.py`, CUDA sağlayıcı seçeneklerine seçilen `device_id`
değerini de ekliyor. Numarasız `cuda` kullanılırsa PyTorch'un etkin cihazı
alınıyor. CPU seçiminin sağlayıcı davranışı korunuyor.

Regresyon: `test_onnx_separator_receives_the_selected_cuda_device`.
Gerçek ONNX seçenek normalleştiricisi, `cuda:1` için `device_id=1`
aldığını doğruluyor. Bu test iki fiziksel kartla performans kabulü değildir.

## 4. Spagetti kod değerlendirmesi ve yapılan ayrıştırma

Kodun tamamı tek bir kontrolsüz akış halinde değil. İşlem motorları,
subprocess yönetimi, çıktı kaydı, eğitim hazırlığı ve donanım katmanları
ayrılmış; mevcut testler özellikle hata ve iptal durumlarında değerli koruma
sağlıyor. Buna rağmen sorumluluk sınırlarının aşıldığı iki bağımlılık vardı:

- Eğitim model kaydı, kayıt biçimini doğrulamak için `ui_cover` içe aktarıyordu.
  Doğrulayıcı `registry_store.py` içine taşındı; servis artık GUI yüklemek
  zorunda değil. Eski UI import yüzeyi uyumluluk için kullanılabilir kaldı.
- Model yöneticisi eski cache konumlarını `ui_separator` üzerinden alıyordu.
  Yol listesi `app_runtime.py` içine taşındı; dosya yönetimi UI modülüne
  bağımlı olmaktan çıkarıldı.

Eğitim oturumu silme/boyut/bağımlılık mantığı da `training/service.py`
içinden yeni `training/cleanup.py` modülüne ayrıldı. Servisin dışarı sunduğu
fonksiyon adları korundu. Böylece süreç yönetimi ve kalıcı model kaydıyla
silme yaşam döngüsü aynı uzun dosyada büyümeye devam etmiyor.

İlk ölçümdeki belirgin bakım yükleri:

| Bölüm | Ölçüm | Değerlendirme |
| --- | --- | --- |
| `ui_training.py` | 1.052 satır; kurucu 192 satır | Form, oturum menüsü, kuyruk ve sonuç davranışları aynı panelde. Yeni büyük özellikte oturum işlemleri ve sonuç görünümü ayrılabilir. |
| `ui_cover.py` | 895 satır; `InitUI` 212, `_run_inference_queue` 134 satır | Widget oluşturma uzunluğu tek başına hata değil. İş kuyruğu/çıktı koordinasyonu panel dışında bir servis için daha uygun bir sonraki sınır. |
| `ui_separator.py` | 858 satır; `ProcessChain` 107 satır | Vokal ve enstrüman akışlarının UI ile bağlandığı yer dikkat istiyor. Ortak export/worker katmanları zaten ayrılmış. |
| `model_manager.py` | 630 satır; `process` 133 satır | Katalog, doğrulama ve indirme aynı dosyada; içteki asset-handler akışı geniş. Ağırlık şeması doğrulaması ileride ayrı modül olabilir. |
| RVC `convert_audio` / `pipeline` | 197 / 192 satır | Zaman çizelgesi, F0, index ve model ömrü iç içe. Sayısal davranışı koruyan testler olmadan parçalamak yüksek regresyon riski taşır. |

Bu ölçümler başlangıç anına aittir. Dosya uzunluğu doğrudan hata kanıtı
olarak kullanılmadı. Kanıtlanan mantık hataları düzeltildi; salt kısa dosya
elde etmek için ses kalitesi veya erişilebilirlik davranışını değiştiren
genel bir yeniden yazım yapılmadı. Tablodaki kalan maddeler bakım borcudur.

## 5. İncelenip bu turda değiştirilmesi gerekmeyen sözleşmeler

- `audio_export` doğrulama, benzersiz isim ve atomik yayın akışı önceki
  sonuçları koruyor. Tam testlerde biçim/kanal dönüşümü, hata ve iptal
  regresyonları geçti.
- Eğitim hazırlığında holdout/index ayrımı, tam checkpoint ve backend/RNG
  uyumluluk kontrolleri korunuyor. Hazırlık-cache yeniden kullanımı dosyaları
  bağımsız oturuma kopyalıyor; ortak yazılabilir dosya paylaşımı yapmıyor.
- Canlı dönüşüm sınırlı kuyruk kullanıyor; yavaş modelde eski sesi biriktirip
  gecikmeyi sınırsız büyütme yaklaşımı yok. Aygıt kimliği, native tampon ömrü,
  gate ve kapanış testleri geçti. Gerçek mikrofon kalitesi ayrıca değerlendirilir.
- RVC index okuyucusunun sınırlı Python doğrulaması, helper-cache sınırları,
  FP32 ve sonlu örnek kontrolleri korundu. Bu turda kalite algoritması,
  hop/F0 değerleri veya model ağırlıkları değiştirilmedi.
- Güncelleme ve paketlemede backend, sürüm, hash ve kaynak kimliği kontrolleri
  mevcut. Yayın üreticileri kişisel model/veri içeren paket ağacını reddediyor.
  Yerel eski paketler bu kontrolle de incelendi; yeni yayın yapılmadı.

Bu maddeler test ve kod incelemesinin kapsamını anlatır; bütün girdilerde
hatasızlık veya bütün donanımlarda çalışma garantisi değildir.

## 6. Disk incelemesi ve yapılan temizlik

Başlangıçta proje ağacındaki dosyaların mantıksal boyut toplamı
**35.971.412.115 bayt**, yaklaşık **33,50 GiB** idi. En büyük alanlar yönetilen
modeller, kişisel modeller/eğitimler, iki hazır Python ortamı ve aynı
derlemelerin birden fazla kopyasıydı. Temizlikten sonraki ölçüm yaklaşık
**24,34 GiB**; yeni test/inceleme kayıtları da bu toplama dahil.

Yalnız aşağıdaki türetilmiş dosyalar kaldırıldı:

| Silinen konum | Bayt | Neden kaldırılabilir? |
| --- | ---: | --- |
| `build/release_dist_cpu` | 1.233.041.123 | Eski CPU paketinin açılmış ağacı; asıl setup saklandı. |
| `build/release_dist_cuda` | 5.538.837.832 | Eski CUDA paketinin açılmış ağacı; asıl setup saklandı. |
| `build/release_work_cpu` | 281.284.573 | PyInstaller ara paketleri; teşhis kayıtları ayrıca arşivlendi. |
| `build/release_work_cuda` | 281.382.612 | PyInstaller ara paketleri; teşhis kayıtları ayrıca arşivlendi. |
| CPU `.candidate.exe` | 373.870.115 | Saklanan CPU setup ile boyut ve tam SHA-256 aynı. |
| CUDA `.candidate.exe` | 2.136.866.539 | Saklanan CUDA setup ile boyut ve tam SHA-256 aynı. |
| **Toplam** | **9.845.282.794** | **9,17 GiB dosya** |

Kaldırılan dosyaların mantıksal boyut toplamı ile ölçülen serbest disk alanı
artışı ayrı değerlerdir. Temizlik kontrolündeki boş alan ölçümü
**79.611.752.448 → 86.129.008.640 bayt**, yaklaşık **6,07 GiB artış** gösterdi.
Diskin tamamına ait bu ölçüm diğer süreçlerin kullanımından da etkilenebilir.

Silmeden önce mutlak hedefler açık bir izin listesiyle workspace/build
içinde doğrulandı; yönlendirilmiş yollar reddedildi. Eski paketlerde kişisel
model/ses bulunmadığı paket ağacı doğrulamasıyla kontrol edildi. Build-info
dosyalarının hash'leri setup receipt'leriyle eşleşti. İki aday installer'ın
asıl setup ile tam hash eşleşmesi yeniden kontrol edildi.

PyInstaller `.toc`, uyarı ve çapraz referans kayıtları **4.202.518 baytlık**
`preserved_pyinstaller_records.zip` içinde saklandı. İki build-info da ayrıca
korundu. Setup'lar, receipt'ler ve önceki test/derleme raporları duruyor.

Korunanlar: `models/`, `modeller/`, `rvc/models/`, `trained_models/`,
`training_runs/`, `deneme/`, kişisel ayarlar/model listesi/şablonlar, hazır
CPU/CUDA/Python ortamları, FFmpeg/Python kaynak-lisans materyali, araştırma
çıktıları ve Git kurtarma yedekleri. Koruma envanterindeki **2.019 dosyanın**
boyutu ve SHA-256 değeri temizlik sonrasında aynı çıktı. Saklanan iki setup'ın
hash'i de değişmedi. Gerçek kullanıcı eğitim oturumu silinmedi.

`release_dist_*` ve `release_work_*` artık yerelde yok. Yeni paket veya frozen
test gerektiğinde kaynaklardan yeniden üretilmeli. Hazır çalışma ortamları
durduğu için kaynak uygulamayı ve testleri çalıştırmak için tekrar indirme
ve ortam kurulumu gerekmiyor.

## 7. Son doğrulama ve açık sınırlar

| Kontrol | Sonuç |
| --- | --- |
| Başlangıç CPU test paketi | 441 test geçti. |
| Son CPU test paketi | **458 test**, 63,324 saniye, başarılı. |
| Son CUDA ortamı test paketi | **458 test**, 53,957 saniye, başarılı. |
| Yeni regresyon sayısı | **17 test metodu**; bazıları birden fazla alt senaryo içeriyor. |
| Python sözdizimi | 145 dosyanın AST kontrolü hatasız. |
| Değişiklik biçimi | `git diff --check` başarılı. |
| Eski paket ağacı incelemesi | CPU 15.991, CUDA 16.031 dosya; kişisel/test/model sızıntısı kontrolü geçti. |
| Kişisel dosya koruması | 2.019 dosyada boyut ve SHA-256 eşleşti. |
| Saklanan installer'lar | İki dosyada boyut ve SHA-256 eşleşti. |

Testler hazır yerel ortamlarda, offline model ayarları ve proje içindeki
geçici klasörle çalıştırıldı. Gerçek mikrofon açılmadı. CUDA ortamında test
paketinin geçmesi, her testin fiziksel GPU üzerinde bir büyük modeli
çalıştırdığı anlamına gelmez. İki fiziksel GPU, uzun gerçek eğitim,
işitsel kalite/gecikme ve canlı NVDA/JAWS kabulü bu turun kanıtı değildir.

Bu düzeltmeler mevcut `Setup/` installer'larının içinde değildir. Kaynak
kullanımı güncel kodu alır; installer üzerinden dağıtım için yeni CPU/CUDA
derlemesi ve o derlemelere ait frozen/kurulum kabulü gerekir.

Yerel ayrıntılı kanıtlar `build/audit_20261022/` içindedir: başlangıç/son test
logları, hataları yeniden üreten test logları, ilk disk envanteri,
`cleanup_verified_plan.json`, `cleanup_removed.json`,
`cleanup_verification.json`, korunmuş build-info ve PyInstaller arşivi.
Bu dosyalar kişisel yerel yol içerebildiğinden Git dışındadır.
