**# Ghostkiller Sound Cleaner - V2 Proje Yol Haritası ve Entegrasyon Planı**



**## Proje Amacı**

**Mevcut `wxPython` tabanlı "Ghostkiller Sound Cleaner" ses ayrıştırma yazılımına, yeni bir RVC (AI Cover) modülünün entegre edilmesi ve kod yapısının modüler (parçalı) hale getirilmesi.**



**## Temel Kurallar ve Kısıtlamalar (Anti Gravity için Talimatlar)**

**1. \*\*Modüler Mimari:\*\* Proje `main.py`, `ui\_separator.py` ve `ui\_cover.py` olmak üzere 3 ana parçaya bölünecek.** 

**2. \*\*Erişilebilirlik (A11y):\*\* Arayüz tamamen `wxPython` standart bileşenleriyle (Notebook, CheckListBox, SpinCtrl vb.) yazılacak. Ekran okuyucuların (NVDA/JAWS) `Tab` tuşu ile rahatça dolaşabilmesi için sekme sıraları ve odaklanma düzgün olacak. Özel çizim (custom paint) arayüzler KULLANILMAYACAK.**

**3. \*\*Donanım ve VRAM Yönetimi (Kritik):\*\* RTX 5060 Ti 16 GB VRAM kullanılmaktadır. RVC çıkarım (inference) işlemleri sırasında VRAM'in şişip çökmesini (OOM) engellemek için, aynı anda birden fazla model \*\*asla çalıştırılmayacaktır\*\*. İşlemler `threading` kullanılarak tekli sıraya (queue) alınacak, biri bitince diğer modele geçilecektir.**

**4. \*\*Odak ve Düzen:\*\* Geliştirme sürecinde multitasking yapılmayacak. Bir dosyadaki işlemler hatasız bitmeden diğerine geçilmeyecek.** 



**---**



**## Adım Adım Geliştirme Aşamaları**



**### Adım 1: Çekirdek Çerçeve (`main.py`)**

**\*   \*\*İçerik:\*\* Uygulamanın ana giriş noktası (entry point).**

**\*   \*\*Görevler:\*\***

&#x20;   **\*   Uygulamanın `sys.executable` ve ortam yolu (PATH) ayarlarının yapılması.**

&#x20;   **\*   Eski sistemde bulunan global hata yakalama (`sys.excepthook`) ve `Ghostkiller\_CrashLog.txt` oluşturma bloğunun korunması.**

&#x20;   **\*   `wx.Notebook` kullanılarak arayüzün iki ayrı sekmeye bölünmesi: "Ses Ayrıştırma" ve "AI Cover".**

&#x20;   **\*   Diğer modüllerin (`ui\_separator.py` ve `ui\_cover.py`) içe aktarılıp sekmelere bağlanması.**



**### Adım 2: Ses Ayrıştırma Modülü (`ui\_separator.py`)**

**\*   \*\*İçerik:\*\* Orijinal koddaki `VocalChainApp` sınıfının ayrıştırma (audio-separator) mantığının buraya taşınması.**

**\*   \*\*Görevler:\*\***

&#x20;   **\*   Eski kodda bulunan girdi/çıktı seçimi, iş parçacığı yönetimi, `Separator` yapılandırması ve `ProcessChain` döngüsünün eksiksiz kopyalanması.**

&#x20;   **\*   \*\*Akıllı Model Kontrolcüsü (YENİ EKLEME):\*\* Koda bir başlangıç kontrol bloğu eklenecek. Program, önce varsayılan işletim sistemi model dizinine (örn. Windows `AppData` veya `.cache/audio-separator`) bakacak. Modeller orada varsa (`os.path.exists`), `Separator` sınıfının `model\_file\_dir` parametresi orası olarak ayarlanacak. Eğer yoksa, `app\_dir` (exe'nin bulunduğu yer) içinde `modeller` adında bir klasör oluşturulacak ve yeni indirmeler bu klasöre yönlendirilecek.**

&#x20;   **\*   \*Amaç:\* Eski kullanıcıların disklerinin tekrar dolmasını önlemek ve yeni kurulumları taşınabilir (portable) klasörde tutmak.**



**### Adım 3: AI Cover Modülü (`ui\_cover.py`)**

**\*   \*\*İçerik:\*\* RVC modeli çıkarım arayüzü ve yönetim sistemi.**

**\*   \*\*Görevler:\*\***

&#x20;   **\*   \*\*Veri Yönetimi:\*\* `app\_dir` içinde `models.json` oluşturularak, kullanıcıların eklediği model adları, `.pth` ve `.index` yollarının kalıcı olarak saklanması/okunması.**

&#x20;   **\*   \*\*Arayüz Bileşenleri:\*\* "Model Ekle" butonu, `.wav` acapella girdi seçimi, işlem yapılacak modellerin seçildiği erişilebilir bir `wx.CheckListBox`, Pitch (Nota) ayarı (`wx.SpinCtrl`) ve F0 Algoritma seçimi (`wx.Choice` - rmvpe / mangio-crepe).**

&#x20;   **\*   \*\*İşlem Motoru:\*\* "Başlat" butonuna basıldığında, seçilen modellerin bir listesi oluşturulacak. Bu liste ayrı bir `thread` (iş parçacığı) üzerinden `subprocess.run` komutlarıyla Applio CLI (veya entegre edilecek mevcut RVC CLI) betiğine gönderilecek. Model işlemleri mutlaka \*sırayla\* gerçekleştirilecek.**



**### Adım 4: Derleme ve Dağıtım (Son Aşama)**

**\*   \*\*Görevler:\*\***

&#x20;   **\*   Eski `Inno Setup (.iss)` dosyasının modüler yapıya uygun şekilde güncellenmesi.**

&#x20;   **\*   `PyInstaller` ile oluşturulan exe dosyasının, yeni modüler Python dosyalarını ve `ffmpeg.exe` / `ffprobe.exe` bağımlılıklarını eksiksiz paketlediğinin teyit edilmesi.**

