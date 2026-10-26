"""Offline, task-oriented help; shipped as code with every application build."""
import json
from pathlib import Path
import sys
import wx
from app_runtime import resource_directory
from app_version import read_application_version
from ui_common import DetailsDialog


HELP = {
    'Müzik ve ses temizleme':
        '1. Şarkıyı veya hazır vokal kaydını seçin. Çıktı klasörü başlangıçta kaydın bulunduğu klasördür.\n'
        '2. Enstrümantal ve/veya vokal çıktısını seçin. İkisi açıksa iki ayrı ses elde edersiniz. '
        'Hazır vokalde yalnız gereken temizleme adımlarını seçebilirsiniz.\n'
        '3. Vokal temizliği seçilen sırada uygulanır. Her aşama ayrı kaydedilir; enstrümantal özgün şarkıdan alınır.\n'
        '4. Gerekirse yalnız bu işin eksik modellerini hazırlayın, sonra işe dönün.\n'
        '5. Sonuçlar listesinden dinleyin veya vokali Ses Değiştirme ekranına aktarın.\n\n'
        'Enstrüman işleme: Standart yöntem bas, davul, vokal ve diğer sesleri ayırır. '
        'Gitar/piyano için altı çıkışlı deneysel yöntem ayrıca seçilir; koşulları kabul edilmelidir. '
        'Daha az çıktı seçmek hesaplamayı azaltmaz, yalnız daha az dosya kaydeder.',
    'Ses değiştirme':
        '1. Hazır RVC .pth model dosyanızı ekleyin veya Model Eğitimi ile kendi modelinizi oluşturun. '
        'İsteğe bağlı .index, eğitim kayıtlarından destek sağlar.\n'
        '2. Dönüştürülecek vokali seçin. Müzikli şarkıda önce ilk sekmeden vokali ayırın.\n'
        '3. Bir veya birkaç model işaretleyin; her model sırayla ayrı vokal dosyası üretir.\n'
        '4. Ses tonu 0 ise değişmez; pozitif değer inceltir, negatif değer kalınlaştırır.\n'
        '5. Eksik yardımcıları hazırlayıp dönüşümü başlatın. Sonuç yalnız dönüştürülmüş vokaldir; '
        'müzikle otomatik birleştirme yapılmaz.\n\n'
        'Index katkısı bir kalite/benzerlik yüzdesi değildir. Daha yüksek değer her zaman daha iyi duyulmaz. '
        'Emin değilseniz gelişmiş ayarları koruyun.',
    'Ses modeli eğitimi':
        '1. Aynı kişiye ait temiz, mümkünse farklı bölümlerden kayıtlar ekleyin. '
        'Kayıtları inceleyip seçili kaydı dinleyebilirsiniz; özgün dosyalar değişmez.\n'
        '2. Model adı ve eğitim tekrar sayısını girin. 40 kHz varsayılanı korunabilir. '
        'Kayıt aralığı ile tutulacak son epoch sayısını seçin. Daha fazla tekrar kalite garantisi değildir.\n'
        '3. Eğitim sırasında Durdur ve kaydet ile daha sonra devam edebilirsiniz. '
        'Eğitim oturumlarım önceki sonuçları ve devam seçeneklerini açar.\n'
        '4. Adayları aynı test sesiyle dinleyin. Düşük kontrol hatası mutlaka daha iyi ses değildir.\n'
        '5. Seçili modeli kalıcı kaydedin veya epoch modellerini topluca kaydedin. '
        'Tercih ettiğiniz aday da toplu kayıtta korunur.\n'
        '6. Teknik çalışma dosyalarını silmek isteğe bağlıdır. Silerseniz bu eğitime devam edemez '
        've eski test seslerini açamazsınız; kalıcı modeller ve özgün kayıtlar korunur.',
    'Canlı AI Cover':
        '1. Kulaklık kullanın. Model, mikrofon ve dinleme çıkışını seçin.\n'
        '2. Otomatik ayarla ile 10 saniye konuşmadan ortamı ölçün. Ölçüm sonunda mikrofon kapanır; '
        'canlı dinleme ayrıca başlatılır.\n'
        '3. Ses düzeyini ayarlayıp Canlı dinlemeyi başlat düğmesine basın. Hazır sesinden sonra konuşun.\n'
        '4. Durdur düğmesi mikrofonu ve çıkışı kapatır. Ses dosyaya kaydedilmez.\n\n'
        'Deneyseldir; donanıma bağlı gecikme vardır. Bu bir sanal mikrofon kurulumu değildir. '
        'Gelişmiş bölümdeki parça süresi toplam gecikme değildir. '
        'Eşiği dinlerken değiştirebilirsiniz: -35 dB daha çok sesi keser, -60 dB daha hassastır. '
        'Alt sınır yoktur; 0 dB veya altında sonlu bir değer yazabilirsiniz.',
    'Ayarlar':
        'İşlemci/ekran kartı tercihi bütün ses işlerinde ortaktır. Donanım testi destek durumunu gösterir.\n'
        'Model listesindeki Hazır/Eksik dosyanın durumudur. [AÇIK]/[KAPALI] yalnız bakım için '
        'işaretlenmiş olup olmadığını anlatır; modelin kullanımını kapatmaz.\n'
        'Eksikleri indir eksikleri tamamlar; Kontrol et çevrimdışı inceler; Onar sorunlu dosyaları indirir.\n'
        'FLAC kayıpsız varsayılandır. MP3/OGG daha küçük, kayıplı dosyalardır; WAV kayıpsızdır. '
        'Biçim ve mono/stereo tercihi bütün dosya çıktılarına uygulanır, canlı dinlemeye uygulanmaz.\n'
        'Güncelleme indirilmeden önce onayınız istenir. Sesler yerel işlenir.',
}


def show_help(parent, topic=None):
    text = HELP.get(topic) if topic else '\n\n'.join(title + '\n' + text for title, text in HELP.items())
    text += '\n\nKlavye: Ctrl+Tab sekme değiştirir. Tab/Shift+Tab kontroller arasında ilerler. '
    text += 'Boşluk seçim yapar; model listesinde ok tuşlarıyla dolaşabilirsiniz. F1 bulunduğunuz ekranın yardımını açar. '
    text += 'F6 başlat/durdur alanına gider. Başlat/durdur ve durum alanı pencerenin altındadır. Sonuçlar aynı ad varsa (2), (3) ile korunur.'
    with DetailsDialog(parent, (topic or 'İlk kullanım') + ' — yardım', text) as dialog:
        dialog.ShowModal()


def add_help(owner, layout, topic):
    button = wx.Button(owner, label='Nasıl kullanılır?')
    button.Bind(wx.EVT_BUTTON, lambda event: show_help(owner, topic))
    layout.Add(button, 0, wx.ALL, 6)
    return button


def application_identity():
    lines = ['Ghostkiller Sound Toolbox ' + read_application_version(), 'Geliştirici: Yasin Talha Gençsoy']
    if not getattr(sys, 'frozen', False):
        lines += ['Çalışma türü: Yerel kaynak; kurulu paket değildir.',
                  'Arayüz düzenlemesi: 25 Ekim 2026 (kaynak).']
    else:
        try:
            info = json.loads((Path(resource_directory())/'build-info.json').read_text(encoding='utf-8'))
            lines += ['Paket: ' + str(info.get('backend', 'Bilinmiyor')).upper(),
                      'Derleme: ' + str(info.get('built_at_utc', info.get('built_at', 'Paket bilgisine kaydedilmemiş'))),
                      'Kaynak kimliği: ' + str(info.get('application_source_sha256', 'Bilinmiyor'))]
        except (OSError, ValueError, AttributeError):
            lines.append('Bu eski pakette derleme kimliği okunamıyor.')
    lines.append('2.1.0 yenilemeleri aynı sürüm numarasını taşır. Paket tarihini kontrol edin. Eski 2.1.0 kurulumları otomatik güncelleme teklifi almaz; yenilenmiş CPU/CUDA paketi elle kurulmalıdır.')
    return '\n\n'.join(lines)


def show_about(parent):
    with DetailsDialog(parent, 'Hakkında ve paket bilgisi', application_identity()) as dialog:
        copy = wx.Button(dialog, label='Paket bilgisini kopyala')
        def copy_text(event):
            if wx.TheClipboard.Open():
                try:
                    wx.TheClipboard.SetData(wx.TextDataObject(dialog.details.GetValue()))
                finally:
                    wx.TheClipboard.Close()
        copy.Bind(wx.EVT_BUTTON, copy_text)
        dialog.GetSizer().Add(copy, 0, wx.ALL, 8)
        dialog.Layout()
        dialog.ShowModal()
