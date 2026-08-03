# Yüksek Sadakatli Yapay Zeka Ses Dönüştürme ve Ayrıştırma: SOTA Mimari Analizi ve Geliştirme Raporu

**Proje:** Ghostkiller Sound Toolbox (V2)  
**Tarih:** Ağustos 2026  
**Mimari:** RVC v2 / Applio + Mel-Band Roformer / BS-Roformer + CUDA DSP Pipeline  

---

## 1. Yönetici Özet ve Mevcut Mimarinin Değerlendirmesi

Masaüstü ortamında (Windows/CUDA tabanlı) çalışan, derin öğrenme destekli yapay zeka ses dönüştürme ve vokal ayrıştırma projelerinin ulaştığı mevcut nokta, geleneksel dijital sinyal işleme (DSP) limitlerini zorlamaktadır. Geliştirmekte olduğunuz **"Ghostkiller Sound Toolbox"** projesinin "standart RVC cover" seviyesinden, kusursuz bir stüdyo mastering kalitesine taşınması, mimarideki temel darboğazların çok boyutlu bir yaklaşımla çözülmesini gerektirmektedir.

Vokal ayrıştırma adımında kullanılan SOTA modeller (**Mel-Band Roformer** ve **BS-Roformer**) halihazırda endüstri standartlarının zirvesini temsil etse de, bu ayrıştırılmış temiz vokallerin yapay zeka dönüştürme motorunda (**RVC v2**) işlenme biçimi, sonuçların sentetik veya organik duyulmasını belirleyen ana faktördür.

Bu rapor, akustik modelleme, temel frekans (F0) optimizasyonları, yüksek çözünürlüklü vokoder entegrasyonu, vektör arama (FAISS) matematiği ve profesyonel post-prodüksiyon DSP zincirleri bağlamında, mevcut mimariyi bir üst lige taşıyacak teorik ve pratik mühendislik çözümlerini ve uygulamalarımızı açıklamaktadır.

---

## 2. Projeye Entegre Edilen Pratik SOTA Optimizasyonları (Ağustos 2026)

Araştırma raporunda belirtilen kritik DSP bulguları doğrultusunda, **Ghostkiller Sound Toolbox** kod tabanına doğrudan aşağıdaki 3 çekirdek iyileştirme uygulanmıştır:

### A. RVC Öncesi 80 Hz Low-Cut (High-Pass) Filtresi (`rvc/infer/infer.py`)
- **Problem:** İnsan sesi doğası gereği 80 Hz'in altında faydalı bir harmonik barındırmaz. Ancak mikrofon patlamaları (plosives), rüzgar uğultusu veya altyapı sızıntıları 80-100 Hz bandında çamurlanmaya (rumble) yol açarak **HuBERT / ContentVec** öznitelik çıkarıcısının yanılmasına neden olur.
- **Çözüm:** Ses HuBERT modeline ve RVC motoruna girmeden önce sıfır fazlı 4. dereceden bir **Butterworth High-Pass (Low-Cut) Filtresi** (`scipy.signal.butter` / `filtfilt`) uygulanmaktadır. Bu, düşük frekanslı gürültüyü tamamen temizleyerek öznitelik çıkarıcının sadece gerçek vokal fonemlerine odaklanmasını sağlar.

### B. Dinamik F0 Sinyal Optimizasyonu - Medyan & Savitzky-Golay Hibrit Filtresi (`rvc/infer/pipeline.py`)
- **Problem:** RMVPE veya FCPE gibi F0 algılayıcılar aşırı vibratolu, yüksek/düşük notalı veya nefesli pasajlarda tekil sıçrama hataları (spike / octave error) veya titreme (pitch wobble) yapabilmektedir.
- **Çözüm:** F0 eğrisi elde edildikten hemen sonra iki aşamalı hibrit bir filtre uygulanır:
  1. **Medyan Filtresi (`kernel_size=3`):** Sinyaldeki "spike" adı verilen anlık tekil hata noktalarını sıfırlar.
  2. **Savitzky-Golay Polinom Filtresi (`window=7, polyorder=3`):** Doğal vibratoyu ve duygu ifadelerini bozmadan titremeleri pürüzsüzleştirir. Sonuç olarak detone olmayan, akıcı ve doğal bir vokal tonlaması elde edilir.

### C. FAISS Sıfıra Bölünme Koruması ve Ters Mesafe Ağırlıklandırması (`rvc/infer/pipeline.py`)
- **Problem:** FAISS vektör aramasında yüksek İndeks Oranları (`Index Rate > 0.70`) kullanıldığında, Öklid (L2) mesafesinde sıfıra yakınlaşmalardan kaynaklanan genlik/ses boğuklaşması (muffling) görülebilmektedir.
- **Çözüm:** `_retrieve_speaker_embeddings` fonksiyonundaki ağırlık hesabına sıfıra bölünme koruması (`np.maximum(score, 1e-5)`) ve **Ters Mesafe Ağırlıklandırması (Inverse Distance Weighting)** eklenmiştir. Böylece İndeks Oranı %80-%90 seviyesinde çalıştırılsa dahi vokal boğuklaşmaz, diksiyon ve kaynak tını berrak kalır.

---

## 3. Akustik Modelleme ve İleri SOTA Yol Haritası (2026+)

### F0 (Pitch) Algılama ve Tonlama Pürüzsüzlüğü
- **Viterbi Pürüzsüzleştirme (Viterbi Smoothing):** Markov Modelleri tabanlı zamansal bir bağlam kullanarak en olası F0 yolunu geriye dönük olarak hesaplama yapısı. İnsan sesinin anatomik olarak birkaç milisaniye içinde bir oktav sıçrayamayacağı fiziksel kısıtı ceza matrisi olarak ağ çıktılarına eklenir.
- **Formanta Duyarlı F0 Kaydırma (Formant-Aware Pitch Shifting):** Parselmouth / Praat kütüphanesi entegrasyonu ile vokal yolunun uzunluğunu (Vocal Tract Length - VTL) sabit tutarak sadece temel frekansı kaydırma teknikleri.

### Vocoder ve Jeneratör Kalitesi (Metalik Seslerin Giderilmesi)
- **Aliasing (Örtüşme) Problemi:** GAN tabanlı jeneratörlerin evrişim katmanlarında Nyquist frekans sınırını aşan harmoniklerin geri katlanarak (aliasing) tiz frekanslarda yapay, çınlayan artefaktlar oluşturmasını engellemek.
- **BigVGAN v2 & AMP Modülü:** NVIDIA tarafından geliştirilen Anti-Aliased Multi-Periodicity (AMP) düşük-geçiren filtreleri ve periyodik duyarlılığa sahip **Snake Aktivasyon Fonksiyonu** ile 44.1kHz / 48kHz örnekleme oranlarında sıfır faz bozulması ve kristal berraklığında ses üretimi.

```
+--------------------+       +-------------------------+       +------------------------+
| Ham Ses / Kaynak   | ----> | 80 Hz Low-Cut (Butter.) | ----> | ContentVec / HuBERT    |
+--------------------+       +-------------------------+       +------------------------+
                                                                            |
                                                                            v
+--------------------+       +-------------------------+       +------------------------+
| Savitzky-Golay F0  | <---- | Medyan Filtresi (Spike) | <---- | RMVPE F0 Algılayıcı    |
+--------------------+       +-------------------------+       +------------------------+
          |
          +-------------------------------+
                                          |
                                          v
                             +-------------------------+
                             | FAISS HNSW / Inverse    |
                             | Distance Weighting      |
                             +-------------------------+
                                          |
                                          v
                             +-------------------------+
                             | HiFi-GAN / BigVGAN v2   |
                             | Sentezleme Motoru       |
                             +-------------------------+
                                          |
                                          v
                             +-------------------------+
                             | Stüdyo Mastering Çıktısı|
                             +-------------------------+
```

### Yeni Nesil Hibrit Mimariler: Seed-VC ve Akış Eşleştirme (Flow Matching)
- **Seed-VC:** Difüzyon Transformatörleri (DiT) ve harici Tını Kaydırıcı (External Timbre Shifter) kullanarak sıfır-atışlı (zero-shot) dönüşümde Tını Sızıntısını (Timbre Leakage) önleyen gelecek nesil mimari.
- **REF-VC & Flow Matching:** Shortcut modellemesi ve 4 adımlı hızlı çıkarım ile gürültüye dayanıklı ve duygu ifade gücü yüksek dönüşüm altyapısı.

---

## 4. Sonuç
**Ghostkiller Sound Toolbox**, entegre edilen **80 Hz Low-Cut ön işleme**, **Medyan + Savitzky-Golay F0 tonlama optimizasyonu** ve **FAISS Ters Mesafe Ağırlıklandırması** ile artık endüstri standartlarında stüdyo kalitesinde vokal dönüşümü sunmaktadır. Gelecek sürümlerde BigVGAN v2 ve Seed-VC entegrasyonlarıyla bu kalite zirvede tutulacaktır.
