# Çıkarım motoru yayın düzeltmeleri

Tarih: 13 Ekim 2026. İlgili bulgular: R07, R13–R15, R22, R25–R28;
R01 için CPU/CUDA-HIP/XPU cihaz yapılandırması; R20 için embedder URL sabitleme.
Kodda çözülmüş hata ile fiziksel donanım/işitsel yayın doğrulaması ayrı tutulur.
Kişisel sesler, korunmuş PTH ve index dosyaları değiştirilmedi.

## Güvenli index sözleşmesi

`rvc/infer/safe_index.py` dosyaları Python ile sınırlı bloklarda okur.
`inspect_index(path, expected_dimension=None)` bütün uzunlukları, sonlu float
verilerini ve ID'leri doğrular; native FAISS dosya okuyucusu çağırmaz.
`load_index(...)` doğrulanmış sayısal bloklardan yeni FAISS nesnesi oluşturur.
Native `read_index`, `deserialize_index`, IO callback veya eklenti yükleme yoktur.
Bu tasarım sıradan subprocess'i güvenlik sandbox'ı olarak sunmaz.

Kabul edilen formatlar little-endian x64 FAISS `IxF2` FlatL2 ve `IwFl`
IVFFlatL2'dir. IVF'nin quantizer'ı FlatL2, listeleri dosyada tutulan `ilar`
ArrayInvertedLists (`full` veya `sprs`) olmalıdır. IVF merkezleri, orijinal
liste atamaları, vektör ID'leri ve `nprobe` korunur. Direct-map yardımcı tabloları
uzunluk sınırıyla atlanır; komşular native `search_and_reconstruct` ile alınır.
Flat kullanıcısı IVF'ye veya KMeans'e geçirilmez.

RVC boyutu 256/768; tek dosya en çok 2 GiB, liste sayısı 65.536, vektör sayısı
10 milyon; IVF ID'leri benzersiz ve 0..ntotal-1 aralığında olmalıdır.
Load ayrıca dosya büyüklüğünü ölçülen boş RAM'in %40'ıyla sınırlar.
Sayısal okumalar en çok 1.024 vektörlük bloklardır. Sonlu olmayan değerler,
|değer| > 1e10, çelişen sayaçlar, kesilmiş ve ek verili dosyalar reddedilir.
Daha az genel bir parser bu bilinçli destek sözleşmesinin parçasıdır:
PQ/HNSW/wrapper/harici dosya hook'u, IP/diğer metrik ve eski `IvFl` türleri
anlamlı hata verir; sessiz kalite veya format dönüşümü yapılmaz.

Format incelenirken FAISS'in sabitlenmiş kaynak kodları kullanıldı:
[index_read.cpp v1.14.3](https://github.com/facebookresearch/faiss/blob/v1.14.3/faiss/impl/index_read.cpp),
[index_write.cpp v1.14.3](https://github.com/facebookresearch/faiss/blob/v1.14.3/faiss/impl/index_write.cpp).
FAISS'in genel dosya okuyucusu güvenilmeyen dosyalara yönelik güvenlik kontrolü
sağlamadığından kullanıcı dosyası ona aktarılmıyor.
[Resmi FAISS I/O uyarısı](https://github.com/facebookresearch/faiss/wiki/Index-IO,-cloning-and-hyper-parameter-tuning).

Tam `reconstruct_n` RAM kopyası çıkarımdan kaldırıldı. Komşu vektörler en çok
256 query × 8 komşu halinde alınır (768 boyutta yaklaşık 6 MiB vektör geçicisi).
Mevcut squared inverse L2-distance harmanlama korunur. FP32 hesapta bloklama,
BLAS ve cihaz kernel'leri bit düzeyinde eşitlik garantisi vermez; quantization
ve yaklaşık Flat araması eklenmemiştir.

## RMVPE ve RAM sınırı

RMVPE ses aktarımı, mel ve U-Net forward'ı bütün kayıt yerine örtüşmeli
pencerelerde yapar. Varsayılan en çok 2.048 mel çerçevesi, 256 çerçeve bağlam,
1.536 çerçeve core'dur. Ölçülen boş GPU belleği 1 GiB altında ise 512,
2 GiB altında ise 1.024 sınırı seçilir. Backend belleği ölçemiyorsa 2.048
kullanılır. CPU/GPU veya FP32 tercihi sessizce değiştirilmez.

Merkezli STFT için her pencerenin iki yanında dört çerçeve halo kullanılır;
halo mel'den kesilir, çıktı yalnız core'dan biriktirilir. Tam kayıt salience'ı
GPU'da tutulmaz. Normal yol CPU'da yalnız F0 biriktirir. `mel2hidden` yardımcı
API'si salience isteyen çağrılarda bunu CPU'da biriktirir.

`load_audio_infer` kaynak başlığından decode/mono, resample/filtre ve çıktı
buffer'larının muhafazakâr RAM tahminini yapar; ölçülen boş RAM'in %60'ını
geçiyorsa ses allocation'ından önce ihtiyacı/boş alanı açıklayan hata verir.
Kaynak ve sentez dalga biçimi hâlâ RAM'de birleştirilir. Çok saatli diskten
akış halinde sentez desteği iddia edilmiyor; bu kontrol kaynak sınırıdır,
kesin peak-memory benchmark'ı değildir.

`empty_cache` her segmentte çağrılmıyor. Seçili cihazda ölçülen bellek baskısı
varsa `compute_backend.trim_cache` kullanılır; iş sonunda açık cleanup yapılır.
CPU işi global CUDA allocator'ını temizlemez.

## Yardımcı ağ cache ve kalite/API

`InferenceHelperCache(max_entries=2)` iş boyunca cihaz, FP32, helper türü ve
kanonik dosya yolu/boyut/mtime kimliğine bağlı en çok iki ağ tutar.
`VoiceConverter.get_vc` generator değiştirirken ContentVec/RMVPE cache'ini
korur; başarısız yeni model eski generator'ı bırakmaz.
`cleanup_model()` veya `cleanup_model(release_helpers=True)` iş sonudur ve
helper'ları bırakır. Bir GUI işi tek converter ile sırayla modelleri dönüştürür.
Bağımsız converter paylaşımı gerekiyorsa aynı `helper_cache=` verilebilir;
çağıran iş sonunda cache'i temizlemelidir. İstatistik kimliği disk cache
geçersizleştirmesidir; bir dosya yayıncı imzası yerine geçmez.

`InferenceQualityPolicy` üç açık bool seçenek taşır: 80 Hz giriş high-pass,
48 Hz pipeline high-pass ve F0 smoothing. Üçü varsayılan açık bırakılarak önceki
seçili davranış korunur. API'de ctor veya convert argümanıyla kapatılıp A/B
karşılaştırması yapılabilir. SOTA, vibratoyu bozmaz ve boğuklaşmayı önler
şeklindeki kanıtsız yorumlar kaldırıldı. Bu seçeneklerin tüm seslerde üstünlük
sağladığı iddia edilmiyor; kör gerçek ses dinlemesi hâlâ yayın doğrulamasıdır.

Checkpoint `embedder_model` metadata'sı varsa seçilen embedder ile eşleşmelidir;
GUI ContentVec kullanırken başka embedder metadata'sı açık hata verir. Custom
embedder için gerçek klasör gerekir. Metadata'sız eski RVC modelleri tarihsel
ContentVec sözleşmesiyle denenir; metadata'nın yokluğu eğitim embedder'ını
kanıtlamaz. `hop_length=160` artık gerçek sabit 16 kHz / 100 fps sözleşmesidir;
yok sayılan 128 ve başka değerler açık hata verir. Global warning bastırması
kaldırıldı; `allow_model_download=False` embedder'da `local_files_only=True`
kullanır. Standalone ContentVec indirme yolu da yayıncı SHA-256 + yapı/CRC
kontrolünü atomik replace öncesinde uygular; config ağırlıktan önce hazırlanır.
Embedder URL'leri Applio commit
`b81f9708367b124b29a47788e4c89b721166234f` ile sabitlendi.

## İkinci incelemede ek kapatılan model allocation açığı

İçe aktarılan 18 alanlı config, boyutu küçük PTH olsa bile dev kanal/katman/
kernel/liste sayısıyla dev ağ oluşturabiliyordu. `model_validation.py` bu
alanları generator öncesinde sınırlar. Meta cihazda parametre allocation'ı
olmadan ağ oluşturulur; toplam 200 milyon parametre sınırı ve boş RAM kontrolü
uygulanır. Meta state şekilleri ve legacy weight_g/weight_v adları eşleştirilir;
ağırlıklar 65.536 elemanlık bloklarda sonluluk için kontrol edilir. Yanlış şekil,
NaN, sparse/bitişik olmayan ağırlıklar ve dev combined config açık hata verir.
Model hiçbir zaman daha küçük bir profile sessizce dönüştürülmez.

`checkpoint_archive_precheck` kullanıcı PTH'sinde torch.load öncesi iki GiB
fiziksel / dört GiB açılmış ZIP sınırını ve boş RAM bütçesini uygular.
Gerçek ZIP central-directory kayıtları küçük okumalarla sayılır; 20.000 üye,
32 MiB central metadata ve 16 MiB data.pkl sınırı, ZipFile'ın üye nesnelerini
oluşturmasından önce denetlenir. EOCD/ZIP64 sahte sayaçlar kabul edilmez.
Standard stored torch.save ZIP, `weights_only=True, mmap=True` ile yüklenir.
Kullanıcıdan gelen non-ZIP eski pickle, sıkıştırılmış/şifreli/yinelenen ZIP
reddedilir; modelin güvenilen bir ortamda güncel torch.save ile dışa aktarılması
istenir. Managed loader'ın `allow_legacy=True` istisnası yalnız zaten yayıncı
hash'i doğrulanmış bilinen asset içindir; legacy pickle allocation güvenliği
iddiası değildir. Archive kontrolü Python/PyTorch/native kütüphanelerde hiç
başka hata olmadığının veya bütün kötü amaçlı PTH'lerin tam güvenlikle
çalıştırılabildiğinin kanıtı olarak sunulmaz.

Ağırlıklar generator'a aktarıldıktan sonra checkpoint'in ikinci CPU weight
kopyası bırakılır; config/embedder metadata'sı korunur. Standart üç vocoder'ın
40 kHz meta ağları yaklaşık 26–27,5 milyon parametredir. Korunmuş gerçek
Deneme RVC latest CPU'da yüklenmiş, V2/40 kHz/ContentVec metadata'sı ve 69.285
vektörlü FlatL2 index doğrulanmıştır; dosyalar yazılmamıştır.

## İkinci inceleme: süre kaybı ve özel embedder

ContentVec'nin 400 örnek receptive field / 320 hop kullanan valid convolution'ı
1,2 saniyelik 40 kHz cover'ın son 20 ms'sini düşürüyordu. Encoder'a gerekli
son özelliği üretmek için yalnız yeterli yansıtılmış gerçek ses bağlamı eklenir;
son kısmi 10 ms çerçeve de sentezlenir. Ara segmentlerdeki mevcut 10 ms gerçek
lookahead hedef çerçeve sayısına eklenmez; no-F0 akışının segment başına uzama
riski de kapanır. Bitmiş waveform sıfırla uzatılmaz. Yalnız sentezlenmiş fazla
örnekler orijinal source info × hedef rate'in yuvarlanmış sample sayısına kesilir;
kısa sonuç hâlâ hata sayılır. 44,1 kHz kaynak resample yuvarlaması da ara
16 kHz sample sayısından bağımsız olarak orijinal zaman çizelgesine bağlanır.

Özel/standalone embedder da 1 MiB config, mevcut scalar/list sınırları,
50 fps convolution hop, meta üzerinde 200 milyon parametre ve boş RAM
kontrolünden geçer. V2 hidden boyutu 768, V1 final projection boyutu 256
olmalıdır. Tek Torch ZIP bin veya boyutu sınırlı safetensors dosyası gerekir;
sharded weight dosyaları bu sınırlandırılmış API'de desteklenmez. Cache anahtarı
safetensors kimliğini de kapsar. Japonca gibi legacy console kod sayfasında
basılamayan dosya yolu tanıları doğrudan print yerine logging kullanır.

## Test ve gerçek ağırlık kanıtları

35 inference senaryosu ve mevcut 16 motor regresyonu geçti. İkinci incelemede
eklenen archive ve model schema kontrolleri de bu koşulardadır.
Senaryolar Flat256/768 exact roundtrip, IVF dense/sparse/direct-map ve nprobe,
L2 metriği, kesilmiş/ek/NaN/giantcount index, yanlış IVF ID/centroid, 80 byte
mutation, validation sonrası değişen numeric veri, sınırlı komşu blokları,
33001-frame RMVPE forward sınırı ve STFT sınır eşitliği, helper yaşam döngüsü,
embedder uyumu, ignored-hop reddi, CPU'nun CUDA cache'e dokunmaması, büyük ses
header'ı ve meta config allocation sınırını kapsar.

Gerçek E2E RMVPE ağıyla yalnız sentetik harmonik/vibrato/sessizlik sinyali
kullanıldı. Tam yerel kanıt Git dışındaki `build/local_reports/INFERENCE_RMVPE_REAL_CHECK.json`,
tekrar betiği `test/audit_inference_release.py`.

| Ölçüm | AMD CPU | NVIDIA CUDA |
| --- | --- | --- |
| 8 s önceki forward ile en büyük F0 farkı | 0 Hz | 0,000662 Hz |
| 45 s en büyük F0 farkı | 0,06148 Hz | 0,06137 Hz |
| 45 s sesli/sessiz disagreement | 0 frame | 0 frame |
| 45 s pencere sınırları p95 cents farkı | 0,07091 | 0,07183 |
| 45 s süre, eski → yeni | 2,906 → 3,453 s | 0,297 → 0,391 s |
| 45 s allocated VRAM peak, eski → yeni | ölçülmedi | 696.004.096 → 520.756.224 bayt |

CUDA kısa çalışmada aynı şekilli forward'a rağmen çok küçük sayısal fark
vardır; bit eşitlik iddia edilmiyor. İlk CUDA çalışması 15,218 saniyelik
başlangıç/kernel ısınmasını içerir ve hız karşılaştırması olarak kullanılmaz.
45 s ölçümü tek örnektir: yaklaşık %25,2 daha az allocated VRAM, overlap
nedeniyle ek hesap süresi görülür. Reserved VRAM/toplam sürücü belleği ölçümü
değildir. Bu veri minimum sistem gereksinimi veya işitsel kalite puanı değildir.

Bidirectional GRU nedeniyle uzun pencereli çıkarım tam-kayıt forward'ına
matematiksel olarak eşit değildir. Bu sentetik deneyde küçük sınır farkı
bulunması bütün gerçek şarkı/nefes/ünsüz/düşük ses/diğerGPU senaryolarında
kalite eşitliği kanıtı sayılmaz. AMD/Intel fiziksel GPU, gerçek uzun şarkı,
kör dinleme ve tüm dış model/vocoder matrisi hâlâ ölçülmelidir.
