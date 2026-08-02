# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - V2 Ana Çerçeve (main.py)

Bu modül, uygulamanın giriş noktası (entry point) olup şu görevleri üstlenir:
1. Uygulamanın sys.executable ve ortam yolu (PATH) ile ffmpeg/ffprobe yollarının ayarlanması.
2. Orijinal V1 sisteminde bulunan global hata yakalama (sys.excepthook) ve
   masaüstüne 'Ghostkiller_CrashLog.txt' raporlama mekanizmasının çalıştırılması.
3. wx.Notebook kullanılarak arayüzün iki erişilebilir sekmeye bölünmesi:
   - "Ses Ayrıştırma" -> ui_separator.SeparatorPanel
   - "AI Cover"       -> ui_cover.CoverPanel
4. Ekran okuyucuların (NVDA / JAWS) rahatça gezebileceği standart sekmeli arayüz.
"""

import wx
import os
import sys
import traceback

# .exe (PyInstaller) ve farklı Windows ortamları için kodlama, PATH ve kaynak dizini korumaları
os.environ["PYTHONIOENCODING"] = "utf-8"

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
    meipass_dir = getattr(sys, '_MEIPASS', app_dir)
    os.environ["PATH"] = app_dir + os.pathsep + meipass_dir + os.pathsep + os.environ.get("PATH", "")
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["PATH"] = app_dir + os.pathsep + os.environ.get("PATH", "")

# Modüler sekmeleri içe aktar
from ui_separator import SeparatorPanel
from ui_cover import CoverPanel
from updater import check_for_updates, CURRENT_VERSION


class GhostkillerMainFrame(wx.Frame):
    """
    Ghostkiller Sound Cleaner V2 - Ana Çerçeve Sınıfı
    wx.Notebook barındırır ve sekmeleri yönetir.
    """
    def __init__(self):
        """Ana pencereyi, boyutları ve renk paletini başlatır."""
        super(GhostkillerMainFrame, self).__init__(
            parent=None,
            title=f"Ghostkiller Sound Cleaner - V2 Pro (v{CURRENT_VERSION})",
            size=(800, 850)
        )

        self.bg_main = wx.Colour(30, 30, 30)
        self.fg_light = wx.Colour(240, 240, 240)

        self.InitMenuBar()
        self.InitUI()
        self.Centre()

        wx.CallAfter(self.ShowStartupMessage)
        # Açılışta arka planda sessiz güncelleme kontrolü yap
        wx.CallAfter(lambda: check_for_updates(self, silent=True))

    def InitMenuBar(self):
        """A11y (NVDA/JAWS): Ekran okuyucu kullanıcıları için menü çubuğu."""
        menubar = wx.MenuBar()

        # Araçlar Menüsü
        tools_menu = wx.Menu()
        update_item = tools_menu.Append(wx.ID_ANY, "Güncelleme Kontrol Et (F5)\tF5", "Yeni bir sürüm olup olmadığını denetler.")
        self.Bind(wx.EVT_MENU, lambda evt: check_for_updates(self, silent=False), update_item)

        menubar.Append(tools_menu, "&Araçlar")
        self.SetMenuBar(menubar)

    def ShowStartupMessage(self):
        """Uygulama başladığında bilgi mesajı gösterir."""
        wx.MessageBox(
            f"Bu program Yasin Talha Gençsoy tarafından yapılmıştır.\n\nV2 Modüler Sürüm v{CURRENT_VERSION} (Ses Ayrıştırma & AI Cover)",
            "Bilgi",
            wx.OK | wx.ICON_INFORMATION
        )

    def InitUI(self):
        """Arayüz bileşenlerini, Karanlık Modu ve wx.Notebook sekmelerini oluşturur."""
        wx.SystemOptions.SetOption("msw.window.dark-mode", 1)
        self.SetBackgroundColour(self.bg_main)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(self.bg_main)
        panel.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # A11y: Standart wx.Notebook bileşeni ekran okuyucular (NVDA/JAWS) ile tam uyumludur.
        # Kullanıcılar Ctrl+Tab veya Ok tuşları ile sekmeler arasında kolayca dolaşabilir.
        self.notebook = wx.Notebook(panel, style=wx.NB_TOP)
        self.notebook.SetBackgroundColour(self.bg_main)
        self.notebook.SetForegroundColour(self.fg_light)

        font_nb = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.notebook.SetFont(font_nb)

        # 1. SEKME: Ses Ayrıştırma Paneli
        self.separator_tab = SeparatorPanel(self.notebook)
        self.notebook.AddPage(self.separator_tab, "1. Ses Ayrıştırma (Temizleme)")

        # 2. SEKME: AI Cover Paneli
        self.cover_tab = CoverPanel(self.notebook)
        self.notebook.AddPage(self.cover_tab, "2. AI Cover (RVC Dönüştürme)")

        vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(vbox)

        # A11y (Erişilebilirlik): Uygulama açıldığında NVDA / JAWS ekran okuyucunun
        # anında aktif sekmeyi seslendirmesi için odağı açıkça wx.Notebook üzerine ayarlıyoruz.
        self.notebook.SetFocus()


def global_exception_handler(exc_type, exc_value, exc_tb):
    """
    Global Hata Yakalayıcı (sys.excepthook):
    Beklenmeyen veya kritik çökme hatalarında, hatanın ayrıntılarını
    kullanıcının masaüstündeki 'Ghostkiller_CrashLog.txt' dosyasına kaydeder.
    """
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        log_path = os.path.join(desktop_path, "Ghostkiller_CrashLog.txt")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- GHOSTKILLER SOUND CLEANER V2 ÇÖKME RAPORU ---\n")
            f.write(error_msg + "\n\n")

        wx.MessageBox(
            f"Programda kritik bir hata oluştu ve kapandı!\n\n"
            f"Detaylar masaüstündeki 'Ghostkiller_CrashLog.txt' dosyasına kaydedildi.\n\n"
            f"Kısa Hata: {exc_value}",
            "Ölümcül Hata",
            wx.OK | wx.ICON_ERROR
        )
    except Exception:
        pass

    sys.__excepthook__(exc_type, exc_value, exc_tb)


if __name__ == '__main__':
    sys.excepthook = global_exception_handler
    app = wx.App(False)
    frame = GhostkillerMainFrame()
    frame.Show(True)
    app.MainLoop()
