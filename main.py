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
   - "Model Eğitimi"  -> ui_training.TrainingPanel
   - "Canlı AI Cover" -> ui_live_cover.LiveCoverPanel
   - "Ayarlar"        -> ui_settings.SettingsPanel
4. Ekran okuyucuların (NVDA / JAWS) rahatça gezebileceği standart sekmeli arayüz.
"""

import os
import sys
import time
_startup_started = time.perf_counter()
from app_runtime import (JOB_LOCK, resource_directory, data_directory, post_ui,
                         configure_runtime_cache, configure_thread_environment,
                         configure_ffmpeg_environment)

os.environ["PYTHONIOENCODING"] = "utf-8"

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    from startup_diagnostics import install
    worker_flag = next((flag for flag in ('--audio-worker','--training-worker') if flag in sys.argv),None)
    diagnostic_directory = None
    if '--startup-probe' in sys.argv:
        diagnostic_directory = os.path.dirname(os.path.abspath(sys.argv[sys.argv.index('--startup-probe') + 1]))
    if worker_flag and len(sys.argv)>sys.argv.index(worker_flag)+1:
        worker_args = sys.argv[sys.argv.index(worker_flag)+1:]
        if worker_args[0]=='--probe' and len(worker_args)>1:
            diagnostic_directory = os.path.dirname(os.path.abspath(worker_args[1]))
        elif worker_args[0]!='--probe':
            diagnostic_directory = worker_args[0]
    install(quiet='--self-test' in sys.argv or '--startup-probe' in sys.argv or worker_flag is not None,
            directory=diagnostic_directory,worker=worker_flag is not None)
    from startup_diagnostics import startup_phase
    startup_phase('python-entry', _startup_started)
    if '--startup-probe' in sys.argv:
        from startup_probe import run
        sys.exit(run(sys.argv[sys.argv.index('--startup-probe') + 1], _startup_started))
    from source_runtime import relaunch_source
    if relaunch_source():
        sys.exit(0)

configure_ffmpeg_environment()
configure_runtime_cache()
configure_thread_environment()

if __name__ == '__main__' and '--self-test' in sys.argv:
    from release_self_test import main as self_test_main
    sys.exit(self_test_main(sys.argv[sys.argv.index('--self-test') + 1:]))

if __name__ == '__main__' and '--training-worker' in sys.argv:
    from training.worker import main as training_main
    sys.exit(training_main(sys.argv[sys.argv.index('--training-worker') + 1:]))

if __name__ == '__main__' and '--audio-worker' in sys.argv:
    from audio_worker import main as audio_main
    sys.exit(audio_main(sys.argv[sys.argv.index('--audio-worker') + 1:]))

import wx
from ui_common import apply_native_style
import traceback

# .exe (PyInstaller) ve farklı Windows ortamları için kodlama, PATH ve kaynak dizini korumaları
os.environ["PYTHONIOENCODING"] = "utf-8"

# Modüler sekmeleri içe aktar
from updater import check_for_updates, check_startup_updates, CURRENT_VERSION


class GhostkillerMainFrame(wx.Frame):
    """
    Ghostkiller Sound Cleaner V2 - Ana Çerçeve Sınıfı
    wx.Notebook barındırır ve sekmeleri yönetir.
    """
    def __init__(self, startup_checks=True):
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
        self.InitUI(startup_checks=startup_checks)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnNavigationKey)
        self.Centre()

        if startup_checks:
            wx.CallAfter(lambda: post_ui(self, self.BeginStartupSequence))

    def OnClose(self, event):
        if JOB_LOCK.locked() and event.CanVeto():
            wx.MessageBox("Bir ses işlemi, canlı dinleme, model/donanım kontrolü veya güncelleme sürüyor. Durdurun veya iptal edin ve işlemin bitmesini bekleyin.", "İşlem Sürüyor", wx.OK | wx.ICON_INFORMATION)
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
        from ui_help import show_help, show_about
        help_menu = wx.Menu()
        current = help_menu.Append(wx.ID_HELP, 'Bu ekran nasıl kullanılır?\tF1')
        self.Bind(wx.EVT_MENU, lambda event: show_help(self, self.HelpTopic()), current)
        first = help_menu.Append(wx.ID_ANY, 'İlk kullanım ve klavye yardımı')
        self.Bind(wx.EVT_MENU, lambda event: show_help(self), first)
        actions = help_menu.Append(wx.ID_ANY, 'Başlat/durdur alanına git\tF6')
        self.Bind(wx.EVT_MENU, lambda event: self.FocusActionBar(), actions)
        about = help_menu.Append(wx.ID_ABOUT, 'Hakkında ve paket bilgisi')
        self.Bind(wx.EVT_MENU, lambda event: show_about(self), about)
        menubar.Append(help_menu, '&Yardım')
        self.SetMenuBar(menubar)

    def BeginStartupSequence(self):
        """Check for updates before the welcome; resume only if staying open."""
        check_startup_updates(
            self, on_complete=lambda: wx.CallAfter(post_ui, self, self.ShowStartupMessage)
        )

    def ShowStartupMessage(self):
        """Updates finish before the ready state, without an interrupting welcome."""
        self.notebook.SetFocus()

    def HelpTopic(self):
        return ('Müzik ve ses temizleme', 'Ses değiştirme', 'Ses modeli eğitimi',
                'Canlı AI Cover', 'Ayarlar')[self.notebook.GetSelection()]

    def OnNavigationKey(self, event):
        # The fixed action area is outside the notebook. Preserve Ctrl+Tab
        # navigation from that area as well as from each page's form.
        if event.GetKeyCode() == wx.WXK_TAB and event.ControlDown():
            self.notebook.AdvanceSelection(not event.ShiftDown())
            self.notebook.SetFocus()
        else:
            event.Skip()

    def FocusActionBar(self):
        bar = self.action_bars[self.notebook.GetSelection()]
        target = next((child for child in bar.GetChildren()
                       if isinstance(child, wx.Button) and child.IsShown() and child.IsEnabled()),
                      self.notebook.GetCurrentPage().txt_status)
        target.SetFocus()

    def InitUI(self, startup_checks=True):
        """Arayüz bileşenlerini, Karanlık Modu ve wx.Notebook sekmelerini oluşturur."""
        from ui_separator import SeparatorPanel
        from ui_cover import CoverPanel
        from ui_training import TrainingPanel
        from ui_live_cover import LiveCoverPanel
        from ui_settings import SettingsPanel
        from app_settings import AppSettings
        self.settings = AppSettings()
        self.settings.open_settings = self.OpenSettings
        self.settings.open_cover = self.OpenCover
        self.settings.add_model = self.AddVoiceModel
        self.settings.use_vocal = self.UseVocal
        self.settings.prepare_models = self.PrepareModels
        self.settings.refresh_operations = self.RefreshOperations
        self.SetBackgroundColour(self.bg_main)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(self.bg_main)
        panel.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # Native notebook controls expose roles/names; live NVDA/JAWS validation is separate.
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
        self.settings.refresh_cover = self.RefreshCoverModels
        self.notebook.AddPage(self.cover_tab, "2. Ses Değiştirme (AI Cover)")
        self.training_tab = TrainingPanel(self.notebook, self.settings)
        self.notebook.AddPage(self.training_tab, "3. Model Eğitimi")
        self.live_cover_tab = LiveCoverPanel(self.notebook, self.settings, models=self.cover_tab.models)
        self.notebook.AddPage(self.live_cover_tab, "4. Canlı AI Cover")
        self.settings_tab = SettingsPanel(self.notebook, self.settings, auto_detect=startup_checks)
        self.notebook.AddPage(self.settings_tab, "5. Ayarlar")
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChanged)

        vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.InstallActionBars(panel, vbox)
        panel.SetSizer(vbox)

        # A11y (Erişilebilirlik): Uygulama açıldığında NVDA / JAWS ekran okuyucunun
        # anında aktif sekmeyi seslendirmesi için odağı açıkça wx.Notebook üzerine ayarlıyoruz.
        apply_native_style(self)
        self.Layout()
        # Native font sizes settle during the first layout. Recalculate the
        # footer before showing the frame so its status field is never clipped.
        panel.Layout()
        self.notebook.SetFocus()

    def InstallActionBars(self, parent, layout):
        # Move the original controls, preserving handlers and live enabled state.
        self.action_bars = []
        pages = (self.separator_tab, self.cover_tab, self.training_tab, self.live_cover_tab, self.settings_tab)
        for index, page in enumerate(pages):
            bar = wx.Panel(parent, style=wx.TAB_TRAVERSAL)
            stack = wx.BoxSizer(wx.VERTICAL)
            row = wx.WrapSizer(wx.HORIZONTAL)
            names = ('btn_start', 'btn_cancel', 'btn_force_stop')
            if index == 3: names = ('btn_start', 'btn_stop', 'btn_force_stop')
            if index == 4: names = ('btn_return', 'btn_cancel')
            for name in names:
                control = getattr(page, name, None)
                if control is None: continue
                control.GetContainingSizer().Detach(control)
                control.Reparent(bar)
                if name != 'btn_return': control.Show()
                row.Add(control, 0, wx.ALL, 4)
            stack.Add(row, 0, wx.EXPAND)
            status = page.txt_status
            status.GetContainingSizer().Detach(status)
            status.Reparent(bar)
            status.SetMinSize((-1, self.FromDIP(42)))
            if index == 2: status.SetValue('Ses kayıtlarını ekleyin ve model adı verin.')
            status.Show()
            stack.Add(status, 0, wx.EXPAND | wx.ALL, 4)
            bar.SetSizer(stack)
            layout.Add(bar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
            bar.Show(index == 0)
            self.action_bars.append(bar)
            page.Layout()
            page.FitInside()

    def AddVoiceModel(self):
        name = self.cover_tab.OnAddModel(None)
        if name:
            self.RefreshCoverModels()
            self.live_cover_tab.model_choice.SetStringSelection(name)

    def UseVocal(self, path):
        if JOB_LOCK.locked():
            return
        if not os.path.isfile(path):
            wx.MessageBox('Sonuç dosyası artık bulunamıyor.', 'Vokal seçimi', wx.OK | wx.ICON_INFORMATION, parent=self)
            return
        self.cover_tab.SetInput(path)
        self.OpenCover()
        self.cover_tab.model_list.SetFocus()

    def OpenSettings(self):
        self.notebook.SetSelection(self.notebook.FindPage(self.settings_tab))
        self.settings_tab.device_choice.SetFocus()

    def OpenCover(self):
        self.notebook.SetSelection(self.notebook.FindPage(self.cover_tab))
        self.cover_tab.btn_add_model.SetFocus()

    def PrepareModels(self, model_ids):
        origin = self.notebook.GetSelection()
        topic = self.HelpTopic()
        def return_to_task():
            self.notebook.SetSelection(origin)
            page = self.notebook.GetPage(origin)
            page.btn_start.SetFocus()
        self.settings_tab.return_action = return_to_task
        self.settings_tab.btn_return.SetLabel(topic + ' işine dön')
        self.settings_tab.btn_return.Show()
        if hasattr(self, 'action_bars'):
            self.action_bars[4].Layout()
        self.notebook.SetSelection(self.notebook.FindPage(self.settings_tab))
        self.settings_tab.PrepareRequiredModels(model_ids)

    def RefreshOperations(self):
        for name in ('separator_tab', 'cover_tab', 'training_tab', 'live_cover_tab'):
            preparation = getattr(getattr(self, name, None), 'preparation', None)
            if preparation is not None and not preparation.IsBeingDeleted():
                preparation.RefreshReadiness()

    def OnPageChanged(self, event):
        for index, bar in enumerate(getattr(self, 'action_bars', ())):
            bar.Show(index == self.notebook.GetSelection())
            bar.InvalidateBestSize()
        self.Layout()
        if getattr(self, 'action_bars', None):
            parent = self.action_bars[0].GetParent()
            parent.Layout()
            parent.Layout()
        self.RefreshOperations()
        live = getattr(self, 'live_cover_tab', None)
        if live is not None and self.notebook.GetCurrentPage() is live and not live.busy:
            self.RefreshCoverModels()
        event.Skip()

    def RefreshCoverModels(self):
        from ui_cover import load_models, get_app_dir
        self.cover_tab.models = load_models(get_app_dir())
        self.cover_tab.UpdateModelCheckList()
        live = getattr(self, 'live_cover_tab', None)
        if live is not None:
            live.RefreshModels(self.cover_tab.models)


def global_exception_handler(exc_type, exc_value, exc_tb):
    """
    Global Hata Yakalayıcı (sys.excepthook):
    Beklenmeyen veya kritik çökme hatalarında, hatanın ayrıntılarını
    kullanıcının veri dizinindeki 'Ghostkiller_CrashLog.txt' dosyasına kaydeder.
    """
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        log_path = os.path.join(data_directory(), "Ghostkiller_CrashLog.txt")
        if os.path.isfile(log_path) and os.path.getsize(log_path) > 2*1024**2:
            os.replace(log_path,os.path.join(data_directory(),'Ghostkiller_CrashLog.previous.txt'))

        with open(log_path, "a", encoding="utf-8") as f:
            f.write("--- GHOSTKILLER SOUND TOOLBOX ÇÖKME RAPORU ---\n")
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
    from startup_diagnostics import SingleInstance
    instance = SingleInstance(data_directory())
    try:
        if instance.existing:
            wx.MessageBox("Program bu kullanıcı oturumunda zaten açık. Mevcut pencereyi kullanın.","Ghostkiller Sound Toolbox",wx.OK|wx.ICON_INFORMATION)
        else:
            frame = GhostkillerMainFrame()
            frame.Show(True)
            startup_phase('window-shown', _startup_started)
            wx.CallAfter(startup_phase, 'event-loop-ready', _startup_started)
            app.MainLoop()
    finally:
        instance.close()
