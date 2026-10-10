# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - V2 Ana Çerçeve (main.py)

Bu modül, uygulamanın giriş noktası (entry point) olup şu görevleri üstlenir:
1. Uygulamanın sys.executable ve ortam yolu (PATH) ile ffmpeg/ffprobe yollarının ayarlanması.
2. Orijinal V1 sisteminde bulunan global hata yakalama (sys.excepthook) ve
   kullanıcı veri dizinine 'Ghostkiller_CrashLog.txt' raporlama mekanizmasının çalıştırılması.
3. wx.Notebook kullanılarak arayüzün erişilebilir sekmelere bölünmesi:
   - "Ses Ayrıştırma" -> ui_separator.SeparatorPanel
   - "AI Cover"       -> ui_cover.CoverPanel
   - "Ayarlar"        -> ui_settings.SettingsPanel
4. Ekran okuyucuların (NVDA / JAWS) rahatça gezebileceği standart sekmeli arayüz.
"""

import wx
import os
import sys
import traceback
from app_runtime import JOB_LOCK, resource_directory, data_directory, post_ui, configure_runtime_cache

configure_runtime_cache()

# .exe (PyInstaller) ve farklı Windows ortamları için kodlama, PATH ve kaynak dizini korumaları
os.environ["PYTHONIOENCODING"] = "utf-8"

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
    meipass_dir = getattr(sys, '_MEIPASS', app_dir)
    os.environ["PATH"] = app_dir + os.pathsep + meipass_dir + os.pathsep + os.environ.get("PATH", "")
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_dir = os.path.join(app_dir, "tools", "ffmpeg")
    os.environ["PATH"] = app_dir + os.pathsep + ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

# Modüler sekmeleri içe aktar
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
            title=f"Ghostkiller Sound Toolbox (v{CURRENT_VERSION})",
            size=(800, 850)
        )

        self.bg_main = wx.Colour(30, 30, 30)
        self.fg_light = wx.Colour(240, 240, 240)

        self.InitIcon()
        self.InitMenuBar()
        self.InitUI()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Centre()

        wx.CallAfter(lambda: post_ui(self, self.ShowStartupMessage))
        # Açılışta arka planda sessiz güncelleme kontrolü yap
        wx.CallAfter(lambda: post_ui(self, check_for_updates, self, True))

    def OnClose(self, event):
        if JOB_LOCK.locked() and event.CanVeto():
            wx.MessageBox("Bir ses işlemi, model/donanım kontrolü veya güncelleme sürüyor. İptal edin ve işlemin durmasını bekleyin.", "İşlem Sürüyor", wx.OK | wx.ICON_INFORMATION)
            event.Veto()
            return
        event.Skip()

    def InitIcon(self):
        """Program penceresinde logo.ico simgesini görüntüler."""
        try:
            icon_path = os.path.join(resource_directory(), "logo.ico")
            if os.path.exists(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def InitMenuBar(self):
        """A11y (NVDA/JAWS): Ekran okuyucu kullanıcıları için menü çubuğu."""
        menubar = wx.MenuBar()

        # Araçlar Menüsü
        tools_menu = wx.Menu()
        update_item = tools_menu.Append(wx.ID_ANY, "Güncelleme Kontrol Et (F5)\tF5", "Yeni bir sürüm olup olmadığını denetler.")
        self.Bind(wx.EVT_MENU, lambda evt: check_for_updates(self, silent=False), update_item)
        settings_item = tools_menu.Append(wx.ID_ANY, "&Ayarlar", "Donanım ve model yönetimi")
        self.Bind(wx.EVT_MENU, lambda evt: self.OpenSettings(), settings_item)

        menubar.Append(tools_menu, "&Araçlar")
        self.SetMenuBar(menubar)

    def ShowStartupMessage(self):
        """Uygulama başladığında bilgi mesajı gösterir."""
        wx.MessageBox(
            f"Ghostkiller Sound Toolbox (v{CURRENT_VERSION})\n\n"
            "Geliştirici: Yasin Talha Gençsoy\n\n"
            "Ses temizleme ve yapay zeka ile ses değiştirme programı hazır.",
            "Ghostkiller Sound Toolbox",
            wx.OK | wx.ICON_INFORMATION
        )

    def InitUI(self):
        """Arayüz bileşenlerini, Karanlık Modu ve wx.Notebook sekmelerini oluşturur."""
        from ui_separator import SeparatorPanel
        from ui_cover import CoverPanel
        from ui_settings import SettingsPanel
        from app_settings import AppSettings
        self.settings = AppSettings()
        self.settings.open_settings = self.OpenSettings
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
        self.separator_tab = SeparatorPanel(self.notebook, settings=self.settings)
        self.notebook.AddPage(self.separator_tab, "1. Müzik ve Ses Temizleme")

        # 2. SEKME: AI Cover Paneli
        self.cover_tab = CoverPanel(self.notebook, settings=self.settings)
        self.notebook.AddPage(self.cover_tab, "2. Ses Değiştirme (AI Cover)")
        self.settings_tab = SettingsPanel(self.notebook, self.settings)
        self.notebook.AddPage(self.settings_tab, "3. Ayarlar")

        vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(vbox)

        # A11y (Erişilebilirlik): Uygulama açıldığında NVDA / JAWS ekran okuyucunun
        # anında aktif sekmeyi seslendirmesi için odağı açıkça wx.Notebook üzerine ayarlıyoruz.
        self.notebook.SetFocus()

    def OpenSettings(self):
        self.notebook.SetSelection(2)
        self.settings_tab.device_choice.SetFocus()


def global_exception_handler(exc_type, exc_value, exc_tb):
    """
    Global Hata Yakalayıcı (sys.excepthook):
    Beklenmeyen veya kritik çökme hatalarında, hatanın ayrıntılarını
    kullanıcının veri dizinindeki 'Ghostkiller_CrashLog.txt' dosyasına kaydeder.
    """
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        log_path = os.path.join(data_directory(), "Ghostkiller_CrashLog.txt")

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- GHOSTKILLER SOUND CLEANER V2 ÇÖKME RAPORU ---\n")
            f.write(error_msg + "\n\n")

        details = f"Hata günlüğü: {log_path}"
    except Exception as log_error:
        details = f"Hata günlüğü kaydedilemedi: {log_error}"
    try:
        wx.MessageBox(f"Programda beklenmeyen bir hata oluştu.\n\n{details}\n\nKısa Hata: {exc_value}", "Uygulama Hatası", wx.OK | wx.ICON_ERROR)
    except Exception:
        pass

    sys.__excepthook__(exc_type, exc_value, exc_tb)


if __name__ == '__main__':
    sys.excepthook = global_exception_handler
    app = wx.App(False)
    frame = GhostkillerMainFrame()
    frame.Show(True)
    app.MainLoop()
