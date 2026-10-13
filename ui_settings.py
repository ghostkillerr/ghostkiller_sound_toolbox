# -*- coding: utf-8 -*-
"""Accessible hardware selection and model maintenance, without blocking wx."""
import threading
import time
import wx
from app_runtime import JOB_LOCK, post_ui, append_log, finish_job
from hardware import detect_hardware
from model_manager import model_catalog
from ui_cover import ModelToggleList


class SettingsPanel(wx.ScrolledWindow):
    def __init__(self, parent, settings, auto_detect=True):
        super().__init__(parent,style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.SetScrollRate(0,20)
        self.settings = settings
        self.model_ids = list(model_catalog())
        self.is_cancelled = False
        self.busy = False
        self._progress_at = 0
        self.SetBackgroundColour(wx.Colour(30, 30, 30))
        self.SetForegroundColour(wx.Colour(240, 240, 240))
        layout = wx.BoxSizer(wx.VERTICAL)
        self.device_choice = wx.RadioBox(self, label="Ekran kartını mı, işlemciyi mi kullanmak istiyorsunuz?",
                                         choices=["İşlemci", "Ekran kartı"], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.device_choice.SetSelection(0 if settings.preference == "cpu" else 1)
        self.device_choice.Bind(wx.EVT_RADIOBOX, self.OnDevice)
        layout.Add(self.device_choice, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_hardware = wx.TextCtrl(self, value="Donanım henüz kontrol edilmedi.",
                                        style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 145))
        self.txt_hardware.SetName("Donanım desteği ve hesaplama testi sonuçları")
        layout.Add(self.txt_hardware, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_hardware = wx.Button(self, label="Donanımı kontrol et")
        self.btn_hardware.Bind(wx.EVT_BUTTON, self.OnHardware)
        layout.Add(self.btn_hardware, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.txt_path = wx.TextCtrl(self, value=f"Model klasörü: {settings.manager.root}", style=wx.TE_READONLY)
        self.txt_path.SetName("Modellerin indirileceği klasör")
        layout.Add(self.txt_path, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Modeller: başlangıçta tümü açıktır. Boşluk ile açıp kapatın; yukarı/aşağı oklarla dolaşın."),
                   0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.model_list = ModelToggleList(self)
        self.model_list.SetMinSize((-1, 240))
        self.model_list.SetName("İndirilecek veya kontrol edilecek modeller ve dosya durumları")
        self.RefreshModels(select_all=True)
        layout.Add(self.model_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_install = wx.Button(self, label="Eksikleri indir")
        self.btn_verify = wx.Button(self, label="Dosyaları kontrol et")
        self.btn_repair = wx.Button(self, label="Seçilenleri onar")
        self.btn_cancel = wx.Button(self, label="İptal")
        for button, action in ((self.btn_install, "install"), (self.btn_verify, "verify"), (self.btn_repair, "repair")):
            button.Bind(wx.EVT_BUTTON, lambda event, operation=action: self.OnModels(operation))
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.btn_cancel.Enable(False)
        for button in (self.btn_install, self.btn_verify, self.btn_repair, self.btn_cancel):
            buttons.Add(button, 1, wx.ALL, 4)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 4)
        self.gauge = wx.Gauge(self, range=100)
        self.gauge.SetName("Model indirme veya kontrol ilerlemesi")
        layout.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_status = wx.TextCtrl(self, value="Hazır. Modelleri bu sekmeden indirin veya kontrol edin.", style=wx.TE_READONLY)
        self.txt_status.SetName("Model işlemi durumu")
        layout.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_log.SetName("Model ve donanım işlem günlüğü")
        layout.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 8)
        for control in (self.txt_hardware, self.txt_path, self.model_list, self.txt_status, self.txt_log):
            control.SetBackgroundColour(wx.Colour(40, 40, 40))
            control.SetForegroundColour(wx.Colour(240, 240, 240))
        self.SetSizer(layout)
        self.FitInside()
        for message in (settings.error, settings.manager.warning):
            if message:
                self.LogMessage(message)
        if auto_detect:
            wx.CallAfter(lambda: post_ui(self, self.OnHardware, None))

    def RefreshModels(self, select_all=False):
        catalog = model_catalog()
        labels = {key: f"{catalog[key]} — {self.settings.manager.status(key)}" for key in self.model_ids}
        self.model_list.SetModels(self.model_ids, labels=labels,
                                  checked_models=self.model_ids if select_all else None)

    def LogMessage(self, text):
        append_log(self, text)

    def EnableUI(self, enable):
        self.busy = not enable
        for control in (self.device_choice, self.model_list, self.btn_hardware, self.btn_install, self.btn_verify, self.btn_repair):
            control.Enable(enable)
        self.btn_cancel.Enable(not enable)

    def OnDevice(self, event):
        previous = self.settings.preference
        try:
            if JOB_LOCK.locked():
                raise RuntimeError("İşlem sürerken donanım değiştirilemez. İşlemin bitmesini bekleyin.")
            preference = "cpu" if self.device_choice.GetSelection() == 0 else "gpu"
            self.settings.select(preference)
            self.txt_status.SetValue("Donanım tercihi kaydedildi; ses işlemleri ve model eğitiminde kullanılacak.")
        except Exception as error:
            self.device_choice.SetSelection(0 if previous == "cpu" else 1)
            wx.MessageBox(str(error), "Donanım seçimi", wx.OK | wx.ICON_WARNING)

    def OnHardware(self, event):
        self.StartJob("hardware", ())

    def OnModels(self, action):
        selected = self.model_list.GetCheckedModels()
        if not selected:
            wx.MessageBox("Listeden en az bir model seçin.", "Model seçimi", wx.OK | wx.ICON_INFORMATION)
            self.model_list.FocusModel(0)
            return
        try:
            if action != "verify":
                self.settings.device_for()
        except Exception as error:
            wx.MessageBox(str(error), "Donanım desteği", wx.OK | wx.ICON_WARNING)
            return
        self.StartJob(action, selected)

    def StartJob(self, action, selected):
        if not JOB_LOCK.acquire(blocking=False):
            self.txt_status.SetValue("Başka bir işlem sürüyor. Bitmesini bekleyip tekrar deneyin.")
            return
        try:
            self.is_cancelled = False
            self.EnableUI(False)
            self.gauge.SetValue(0)
            self.txt_status.SetValue("Donanım kontrol ediliyor..." if action == "hardware" else "Model işlemi başladı...")
            worker = threading.Thread(target=self.RunJob, args=(action, tuple(selected)), daemon=True)
            worker.start()
        except Exception:
            JOB_LOCK.release()
            self.EnableUI(True)
            raise

    def OnCancel(self, event):
        self.is_cancelled = True
        self.btn_cancel.Enable(False)
        self.txt_status.SetValue("İptal ediliyor; mevcut dosya/hesaplama kontrolünün durması bekleniyor...")

    def Progress(self, filename, done, total):
        now = time.monotonic()
        if now - self._progress_at < 0.2 and (not total or done != total):
            return
        self._progress_at = now
        percent = max(0, min(100, int(done * 100 / total))) if total else 0
        text = f"{filename}: {done / 1024 ** 2:.1f} MB" if done else filename
        if total:
            text += f" / {total / 1024 ** 2:.1f} MB (%{percent})"
        post_ui(self, self.txt_status.SetValue, text)
        post_ui(self, self.gauge.SetValue, percent)

    def RunJob(self, action, selected):
        try:
            if action == "hardware":
                report = detect_hardware()
                if self.is_cancelled:
                    raise InterruptedError("Donanım kontrolü iptal edildi.")
                self.settings.report = report
                post_ui(self, self.txt_hardware.SetValue, report.describe())
                message = "Donanım kontrolü tamamlandı."
                try:
                    self.settings.device_for()
                except RuntimeError as error:
                    # Keep the saved preference visible; the user can select CPU explicitly.
                    message += " " + str(error)
                post_ui(self, self.txt_status.SetValue, message)
                self.LogMessage(report.describe())
            else:
                failures = self.settings.manager.process(selected, action, cancelled=lambda: self.is_cancelled,
                                                         progress=self.Progress, log=self.LogMessage)
                summary = f"İşlem tamamlandı. Hazır: {len(selected) - len(failures)}, sorunlu: {len(failures)}."
                if failures:
                    summary += " Ayrıntılar günlükte; eksik/bozuk dosyalar için Onar'ı kullanın."
                post_ui(self, self.txt_status.SetValue, summary)
                post_ui(self, self.gauge.SetValue, 0 if failures else 100)
                self.LogMessage(summary)
        except InterruptedError:
            post_ui(self, self.txt_status.SetValue, "İşlem iptal edildi. Tamamlanmış dosyalar korundu.")
        except Exception as error:
            self.LogMessage(f"HATA: {error}")
            post_ui(self, self.txt_status.SetValue, f"İşlem başarısız: {error}")
        finally:
            post_ui(self, self.RefreshModels)
            finish_job(self)
