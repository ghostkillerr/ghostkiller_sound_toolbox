# Üretken vokal onarımı araştırması — 16 Ekim 2026

**Sonraki uygulama durumu:** Kullanıcının isteğiyle A2SB kısa aralık onarımı
isteğe bağlı bir adım olarak kaynak sürümüne eklendi. Arka vokal temizliği
açıkken görünür; kapatılınca kapanır ve gizlenir. Standart ve onarılmış mono
dosya ayrı saklanır. [Kullanım ve erişilebilirlik](VOKAL_ONARIMI.md).
Gerçek CUDA worker, kayıt örneğinde üretim/ilerleme/iptal ve PCM24 kaydından
geçti. Aşağıdaki araştırma turlarının kaynak/kurulum değişmedi ifadeleri,
bu entegrasyondan önceki denemelere aittir. Önceki installer'lar bu eki içermez.

Amaç, arka vokal ayırmada ana sesten kaybolan ayrıntıları bir modelle yeniden
üretmeyi denemektir. Önceki hafif karışım kullanıcıya yetersiz geldi; düşüşlerde
kaynak vokalle destek beğenildi, fakat daha iyi bir sonuç istendi.

Bu araştırma, kaynakla karışımı üretken onarım diye adlandırmaz. Modelin yeni
ses üretmesi, doğru sözleri, notaları, tınıyı veya yalnız ana vokali ürettiğini
kanıtlamaz. Kullanıcının dinleyerek karşılaştırması gerekir.

## Araştırılan modeller

| Model | Kaynaklarda belirtilen amaç | Bu denemedeki karar |
| --- | --- | --- |
| NVIDIA A2SB | 44,1 kHz müzikte yüksek frekans tamamlama ve kısa eksik ses aralıklarını üretme | Kısa zaman kaybı çıktısı kullanıcı tarafından beğenildi; hafif gürültü bildirildi, yeni uygulama denemesi gerekiyor |
| Apollo / vokal uyarlaması | Frekans bantlarını kullanarak bozulmuş müzik/ses onarımı | Resmî kod ve topluluk vokal ağırlıklarıyla iki gerçek CUDA çıktısı üretildi |
| AnyEnhance | Konuşma/şarkı iyileştirme; makalede referans tını rehberliği | Genel modelin indirilebilir tam ağırlığı bu incelemede doğrulanamadı; erişilebilir v1 farklı bir yarışma temeli |
| VoiceRestore | Akış eşleştirmeyle konuşma onarımı | Deposu müzikte sonucun iyi olmayabileceğini belirtiyor; ilk şarkı denemesinde öncelik verilmedi |

Kaynaklar: [A2SB resmî depo](https://github.com/NVIDIA/diffusion-audio-restoration),
[A2SB model kartı](https://huggingface.co/nvidia/audio_to_audio_schrodinger_bridge/blob/main/modelcard.md),
[Apollo resmî depo](https://github.com/JusperLee/Apollo),
[Apollo vokal ağırlıkları](https://huggingface.co/oulianov/Apollo-vocal-msst),
[AnyEnhance makalesi](https://arxiv.org/abs/2501.15417),
[AnyEnhance v1 açıklaması](https://github.com/viewfinder-annn/AnyEnhance-v1),
[VoiceRestore açıklaması](https://github.com/skirdey/voicerestore).

AnyEnhance v1 açıklamasına göre erişilebilir temel 45,68 milyon parametreli,
farklı verilerle eğitilmiş bir sürümdür; referans rehberliği açıkça etkin değildir
ve self-critic kullanılmaz. Bu temeli makaledeki tam şarkı/referans modeli diye
sunmak doğru olmaz. Model araştırması yalnız isim/özet eşleşmesiyle bitirilmedi.

## Gerçek Apollo denemesi

- Kod: `JusperLee/Apollo`, sabit commit
  `e84bcacc59d5455f05d86a5c97dd4aeb3c14dbb6`.
- Vokal ağırlıkları: `oulianov/Apollo-vocal-msst`, sabit revision
  `192df97361699796d8e8abc54ed7a983c38eab6c`.
- Ağırlık SHA-256:
  `59e1311f93e1f0fde6d5d11fa69d97e41cdee39be38f0cf4ccb80cfce34b2a2b`.
- Ağ: 48.434.348 parametre, `feature_dim=384`, sekiz katman, 44,1 kHz.
  Bütün ağırlık anahtar ve boyutları eksiksiz eşleşti.
- Gerçek NVIDIA RTX 5060 Ti üzerinde FP32 çalıştı.
- Şarkının 45–65 saniyesi için iki çıktı üretildi: doğrudan bozulmuş vokal
  ve kaynak destekli vokal sonrasında model onarımı.
- Model 43–67 saniyeyi bağlamla işledi; orta 20 saniye dinlemeye ayrıldı.
  Upstream'in bağlam ve örtüşmeli pencere yordamı kullanıldı.
- İşlem süreleri 33,141 ve 16,219 saniye; tepe GPU tahsisi 3.247,3 MiB.
- İki çıktı da 44,1 kHz stereo, 20 saniye ve sonlu örneklerle doğrulandı.
  Ses düzeyi eşitlenmiş PCM24 dinleme kopyaları hazırlandı.
- **Dinleme ve kalite kararı bekleniyor.** Apollo'nun sıkıştırma bozulması
  hedefi, ayrıştırmada tamamen kaybolmuş kelimeleri geri getirme kanıtı değildir.

## A2SB denemesinin kapsamı

- Kod: `NVIDIA/diffusion-audio-restoration`, sabit commit
  `02ddff01c4dbbe20839e13e09da1988db7dd4be9`.
- Tek parçalı model: `nvidia/audio_to_audio_schrodinger_bridge`, revision
  `c3d0f52831b3c1c216ad98736dc9fd9253d38342`.
- Ağırlık: 2.262.312.618 byte; SHA-256
  `fc3dac27c63ce736f5f9e72e12420afb65d63e7899947e6280d132a8f833b8ad`.
- Ağ: 565.544.851 parametre; resmî ağ tanımı ve eksiksiz eşleşen ağırlıklar.
- Model kartı tek kanallı 44,1 kHz sesi, 4 kHz üstü bant tamamlamayı ve
  bir saniyeden kısa zaman kayıplarını belirtir. Linux tercih edildiği için
  buradaki Windows/PyTorch denemesi ayrıca kontrol edildi; gerçek CUDA frekans
  üretimi çalıştı. Bu sonuç bütün Windows/donanım sürümlerinin kabulü değildir.
- Bu deneme **düzensiz harmonik frekans maskeleri** kullanır; bu, resmî
  model kartındaki standart girişlerden farklı, deneysel bir uyarlamadır.
- Temizleme öncesi vokalden mevcut RMVPE ile perde çizgisi çıkarılır.
  Önemli harmoniklerde temizleme sonrası ciddi zayıflayan alanlar aday seçilir.
  Bu işlem ana/arka şarkıcı kimliğini ayırt eden bir model değildir.
- Referans ses yalnız perde/maskeye rehberlik eder. Referans dalga biçimi
  model girdisine veya çıktısına geri karıştırılmaz; seçili frekansları model üretir.
- Resmî `ddpm_sample` yordamının gövdesi değiştirilmeden, tek model ve 32
  örnekleme adımıyla çalıştırılır. Eğitim/ölçüm bağımlılıkları içe aktarılmaz.
- İlk hedef şarkının aynı 45–65 saniyesidir. Mono model sonucu için mono
  karşılaştırma kayıtları hazırlanır; stereo kabulü olarak sayılmaz.
- Harmonik maske denemesi tamamlandı: 32 örnekleme adımı 233,625 saniye,
  tepe GPU tahsisi 3.730,9 MiB. Seçilen alanlar bütün zaman/frekans alanının
  yaklaşık %0,555'idir; bu bir kalite veya vokal kurtarma yüzdesi değildir.
- Seçilmeyen model temsili alanlarında fark sıfır; çıktı 20 saniye,
  44,1 kHz mono ve sonlu. Kaynak dosyalar korunmuş durumda.
- Ayrı kısa zaman kaybı denemesi 55,84–55,93 ve 59,44–59,58
  saniye aralıklarını resmî `fast_inpaint_ddpm_sample` yordamıyla yeniden üretir.
  Bu aralıklar kaynak/sonuç enerji kaybıyla seçildi; gerçekten ana vokal mi
  arka vokal mi olduğu bu ölçümden anlaşılamaz. Diğer kayıplar onarılmış sayılmaz.
- Son iki aralık, hızlı yordamın ayrı bağlam pencereleri koşuluna uygun biçimde
  yaklaşık üç saniyelik pencere uzunluğundan daha uzak seçildi. İlk üç aralıklı
  prototip bu koşulu sağlamadığı için saklanıp son karşılaştırmadan çıkarıldı.
- Kısa zaman denemesi tamamlandı: iki aralık için 32'şer adım, toplam 30,156
  saniye ve tepe GPU tahsisi 3.488,4 MiB. Seçilmeyen temsil alanlarında fark
  sıfır; çıktı 20 saniye, 44,1 kHz mono ve sonlu. Kaynak dosyalar değişmedi.
- Kullanıcı bu turun 4 numaralı, kısa zaman kaybı çıktısını beğendi; arkada
  hafif gürültü bildirdi. Bu, diğer modellerin veya bütün kaydın kabulü değildir.

## Hazır dinleme karşılaştırması

Aynı 45–65 saniyelik bölümden altı adet 20 saniyelik, 55–65 saniyelik bölümden
altı adet 10 saniyelik PCM24 örnek hazırlandı: sorunlu sonuç, beğenilen kaynak
desteği, doğrudan Apollo, kaynak desteğinden sonra Apollo, A2SB harmonik frekans
üretimi ve A2SB kısa aralık üretimi. Toplam 12 örneğin süre, örnekleme hızı,
kanal sayısı ve sonlu örnek kontrolleri geçti. Her grupta ortak RMS hedefi
kullanıldı; limiter uygulanmadı. A2SB ile karşılaştırma için hepsi mono.

Yerel `07_uretken_model_karsilastirma.json` kaydı bu kontrolleri ve özgün sesin
değişmediğini doğrular. Bu teknik kontroller ses kalitesinin kabulü değildir.

## Standart temizleme sonrasında yerel onarım

Kullanıcı, beğendiği kısa aralık üretiminin standart arka vokal ayırma çıktısına
uygulanmasını istedi. Bu turda giriş, yankı ön işlemi yapılmadan alınmış mevcut
standart arka vokal sonucudur; hafif kaynak karışımı kullanılmaz.

Önceki 4 numaranın iki aralığı dışındaki dalga biçimi, temizleme girdisinden
düşük seviyede farklıydı: aralıklardan en az 100 ms uzak örneklerde fark RMS'i
0,000613637, tepe mutlak fark 0,007616028 ölçüldü. Seçilmeyen model temsilinin
korunması, STFT dönüşümü sonrasında bütün dalga biçiminin aynı kalacağını
kanıtlamaz. Bu ölçüm, kullanıcının duyduğu gürültünün nedenini tek başına belirlemez.

Yeni deneme, her kayıp aralığı aynı standart temizlenmiş girdiden bağımsız
olarak üretir; model dalga biçimini yalnız aralık ve 35 ms çevresine yerleştirir.
15 ms kosinüs geçişi kullanılır. Bunun dışındaki örnekler doğrudan korunur.
Kaynak vokal yalnız kayıp konumu ve aşırı üretilmiş seviye için azaltıcı tavan
hesabında kullanılır; dalga biçimi geri karıştırılmaz. Referansa göre ses
azalması ana ve arka vokali ayırt etmez; dinleme zorunludur.

İlk kapsam aynı 45–65 saniyedir. Bir saniyeden uzun kelime/cümle kayıpları bu
yöntemle onarılmış sayılmaz. İşlem kaydı ve son kontroller yerel
`08_standart_temizleme_onarim.json` içinde tutulur.

Bu tur tamamlandı: 51,50–51,65; 53,93–53,98; 55,85–55,92; 56,36–57,25;
57,60–57,74; 59,44–59,58 ve 63,34–63,42 saniyelerinde yedi bağımsız üretim
yapıldı. Çekirdek kayıplar toplam 1,52 saniye; geçişlerle birlikte değiştirilen
alan 2,0097 saniye. 32'şer adımlı üretim toplam 129,312 saniyede tamamlandı;
tepe GPU tahsisi 3.487,4 MiB.

Geçiş alanları dışında dalga biçimi farkı tam sıfır; ortak kazançlı iki PCM24
dinleme dosyasında da bu örnekler birebir eşit. Sesler 44,1 kHz, mono, 20 saniye,
sonlu ve taşma olmadan doğrulandı. Özgün kayıt ve girişler hash ile korundu;
uygulama kaynakları mevcut kurulumlarla eşleşiyor. Önceki 4 numaranın yalnız
kayıp çevresine yerleştirilmiş ek kopyası da hazır. Gürültünün azalıp azalmadığı,
ana ses ve arka vokal ayrımı için **yeni dinleme kararı bekleniyor**.

## Olası uygulama sırası

Kullanıcı ilk karşılaştırmada A2SB kısa aralık yöntemini seçti. Şimdi standart
temizleme ve bu onarımın sıralı sonucu, bildirilen gürültüyle birlikte sınanır.
Tercih edilen yöntem bu dinleme sonrasında isteğe bağlı bir onarım adımı olarak
tasarlanır. Temizleme öncesi ve onarım öncesi dosyalar korunur; kaynak desteği
ile yeni model üretimi ayrı adlandırılır.

A2SB'nin mono varsayımını stereo destek diye sunmamak, kullanılacak modelin
lisans/dağıtım koşullarını karşılamak, model indirme ve worker sınırlarını
uygulamanın mevcut doğrulama düzenine eklemek gerekir. Bu araştırma sonunda
üretim kurulumlarını yeniden derlemek için henüz bir kaynak değişikliği yoktur.

Bir modelin kayıp yere ses üretmesi, aynı kişinin doğru sözü ve notayı
söylediğini kanıtlamaz. Referans harmoniği yönlendirme sağlar; üst üste aynı
notayı söyleyen ana/arka sesleri tek başına ayıramaz. Dinleme ve farklı gerçek
kayıtlarla ölçüm, kalıcı özellikten önce gelir.

## Korunan ortam ve dağıtım sınırı

Kodlar/ağırlıklar yalnız `build/vocal_restoration_research_20261016` altında,
sesler mevcut ignored deneme klasöründe tutulur. İndirme boyut ve SHA değerleri
Hugging Face dosya metadata'sıyla eşleşti; kaynaklar sabit commit'lere bağlıdır.
Checkpoint'ler kısıtlı `weights_only=True` yüklemesiyle okunur.

Uygulamanın CUDA/CPU paketlerine bağımlılık kurulmadı. Yalnız araştırma
klasöründeki `deps` alanına `jsonargparse==4.52.0` eklendi. Uygulama kaynakları,
kalıcı işlem sırası ve iki installer değiştirilmedi. Yeni özellik olarak
paketlenmiş veya yayımlanmış değildir. Sesler uzak bir servise gönderilmedi.

Lisans alanları: Apollo kodu CC-BY-SA-4.0, seçilen vokal ağırlıkları
CC-BY-NC-SA-4.0; A2SB model/kodu kendi ticari olmayan NVIDIA lisanslarını belirtir.
Bu yerel deney, modellerin kuruluma veya genel dağıtıma eklendiği anlamına gelmez.

Yerel ayrıntılar: `04_apollo_vocal_trial.json`, `05_a2sb_harmonic_trial.json`,
`06_a2sb_temporal_spaced_trial.json`, `07_uretken_model_karsilastirma.json`,
indirilen kod/ağırlık kayıtları ve gerçek dinleme örnekleri. Kişisel tam yolları
içeren bu kanıtlar Git'e eklenmez.
