# -*- coding: utf-8 -*-
"""Accessible hardware selection and model maintenance, without blocking wx."""
import threading
import time
import wx
from app_runtime import JOB_LOCK, post_ui, append_log, finish_job
from hardware import detect_hardware
from model_manager import model_catalog, default_model_selection
from ui_cover import ModelToggleList
from ui_common import apply_native_style, DetailsDialog, add_intro, section_title
from updater import check_for_updates, last_update_result


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
        add_intro(self, layout, "Ayarlar", "İşlemlerde kullanılacak donanımı seçin ve programın ihtiyaç duyduğu model dosyalarını hazırlayın.")
        self.theme_choice = wx.RadioBox(self,label='Görünüm',choices=['Açık mod','Koyu mod'],majorDimension=2,style=wx.RA_SPECIFY_COLS)
        self.theme_choice.SetSelection(0 if settings.theme == 'light' else 1)
        self.theme_choice.Bind(wx.EVT_RADIOBOX,self.OnTheme)
        layout.Add(self.theme_choice,0,wx.EXPAND | wx.ALL,8)
        section_title(self, layout, "Program güncellemeleri")
        self.chk_auto_update = wx.CheckBox(self, label="Açılışta güncellemeleri denetle ve otomatik güncelle")
        self.chk_auto_update.SetValue(settings.auto_update)
        self.chk_auto_update.Bind(wx.EVT_CHECKBOX, self.OnAutoUpdate)
        layout.Add(self.chk_auto_update, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Yeni sürüm indirilip uygulanınca program yeniden açılır.\nBu seçeneği kapatırsanız aşağıdaki düğmeyle güncelleyebilirsiniz."),
                   0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.btn_update = wx.Button(self, label="Güncellemeleri denetle")
        self.btn_update.Bind(wx.EVT_BUTTON, self.OnCheckUpdates)
        layout.Add(self.btn_update, 0, wx.ALL, 8)
        update_result = last_update_result()
        self.txt_update_status = wx.TextCtrl(self, value=update_result.get('message', 'Güncellemeleri bu bölümden yönetebilirsiniz.'),
                                            style=wx.TE_READONLY)
        self.txt_update_status.SetName('Son program güncellemesi durumu')
        layout.Add(self.txt_update_status, 0, wx.EXPAND | wx.ALL, 8)
        self.device_choice = wx.RadioBox(self, label="1. İşlemlerde kullanılacak donanım",
                                         choices=["İşlemci", "Ekran kartı"], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.device_choice.SetSelection(0 if settings.preference == "cpu" else 1)
        self.device_choice.Bind(wx.EVT_RADIOBOX, self.OnDevice)
        layout.Add(self.device_choice, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_hardware = wx.TextCtrl(self, value="Donanım henüz kontrol edilmedi.",
                                        style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 130))
        self.txt_hardware.SetName("Donanım kontrolü özeti")
        layout.Add(self.txt_hardware, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_hardware = wx.Button(self, label="Donanımı kontrol et")
        self.btn_hardware.Bind(wx.EVT_BUTTON, self.OnHardware)
        hardware_buttons = wx.WrapSizer(wx.HORIZONTAL)
        hardware_buttons.Add(self.btn_hardware, 0, wx.ALL, 4)
        self.btn_details = wx.Button(self, label="Teknik ayrıntıları göster")
        self.btn_details.Bind(wx.EVT_BUTTON, self.OnDetails)
        hardware_buttons.Add(self.btn_details, 0, wx.ALL, 4)
        layout.Add(hardware_buttons, 0, wx.EXPAND | wx.ALL, 4)
        self.txt_path = wx.TextCtrl(self, value=f"Model klasörü: {settings.manager.root}", style=wx.TE_READONLY)
        self.txt_path.SetName("Modellerin indirileceği klasör")
        layout.Add(self.txt_path, 0, wx.EXPAND | wx.ALL, 8)
        section_title(self, layout, "2. Model dosyaları")
        layout.Add(wx.StaticText(self, label="Ses temizleme ve ses değiştirme modelleri seçili gelir.\nEğitim ve isteğe bağlı vokal onarımı modellerini gerektiğinde ayrıca seçin.\nSeçimleri Boşluk ile değiştirin; ok tuşlarıyla listede dolaşın.\nEksikleri indir: olmayan dosyaları tamamlar. Kontrol et: dosyaları inceler. Onar: sorunlu dosyaları yeniden indirir."),
                   0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.model_list = ModelToggleList(self)
        self.model_list.SetMinSize((-1, 180))
        self.model_list.SetName("İndirilecek veya kontrol edilecek modeller ve dosya durumları")
        self.RefreshModels(initial_selection=True)
        layout.Add(self.model_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        buttons = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_install = wx.Button(self, label="Eksikleri indir")
        self.btn_verify = wx.Button(self, label="Dosyaları kontrol et")
        self.btn_repair = wx.Button(self, label="Seçilenleri onar")
        self.btn_cancel = wx.Button(self, label="İptal et")
        for button, action in ((self.btn_install, "install"), (self.btn_verify, "verify"), (self.btn_repair, "repair")):
            button.Bind(wx.EVT_BUTTON, lambda event, operation=action: self.OnModels(operation))
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.btn_cancel.Enable(False)
        for button in (self.btn_install, self.btn_verify, self.btn_repair, self.btn_cancel):
            buttons.Add(button, 1, wx.ALL, 4)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 4)
        self.gauge = wx.Gauge(self, range=100)
        section_title(self, layout, "3. İşlem durumu")
        self.gauge.SetName("Model indirme veya kontrol ilerlemesi")
        layout.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_status = wx.TextCtrl(self, value="Hazır. Modelleri bu sekmeden indirin veya kontrol edin.", style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1,70))
        self.txt_status.SetName("Model işlemi durumu")
        layout.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.txt_log.SetName("Model ve donanım işlem günlüğü")
        layout.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 8)
        for control in (self.txt_hardware, self.txt_path, self.model_list, self.txt_status, self.txt_log):
            control.SetBackgroundColour(wx.Colour(40, 40, 40))
            control.SetForegroundColour(wx.Colour(240, 240, 240))
        self.SetSizer(layout)
        apply_native_style(self)
        self.FitInside()
        for message in (settings.error, settings.manager.warning):
            if message:
                self.LogMessage(message)
        if auto_detect:
            wx.CallAfter(lambda: post_ui(self, self.OnHardware, None))

    def RefreshModels(self, initial_selection=False):
        catalog = model_catalog()
        catalog.update({'contentvec': 'Ses değiştirme ve eğitim için ses bilgisi',
                        'rmvpe': 'Ses değiştirme ve eğitim için nota algılama',
                        **{f'training_v2_{rate}k': f'Model eğitimi için başlangıç dosyaları ({rate} kHz)' for rate in (32,40,48)}})
        labels = {key: f"{catalog[key]} — {self.settings.manager.status(key)}" for key in self.model_ids}
        self.model_list.SetModels(self.model_ids, labels=labels,
                                  checked_models=default_model_selection() if initial_selection else None)

    def OnTheme(self,event):
        previous = self.settings.theme
        try:
            self.settings.select_theme('light' if self.theme_choice.GetSelection()==0 else 'dark')
            root = wx.GetTopLevelParent(self)
            apply_native_style(root,theme=self.settings.theme)
            root.Layout()
            root.Refresh()
        except Exception as error:
            self.theme_choice.SetSelection(0 if previous=='light' else 1)
            wx.MessageBox(str(error),'Görünüm kaydedilemedi',wx.OK | wx.ICON_ERROR,parent=self)

    def OnAutoUpdate(self, event):
        try:
            self.settings.select_auto_update(self.chk_auto_update.GetValue())
        except Exception as error:
            self.chk_auto_update.SetValue(self.settings.auto_update)
            wx.MessageBox(str(error), 'Güncelleme tercihi kaydedilemedi', wx.OK | wx.ICON_ERROR, parent=self)

    def OnCheckUpdates(self, event):
        check_for_updates(wx.GetTopLevelParent(self), silent=False)

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
            self.txt_hardware.SetValue(self.settings.report.summary(preference))
            self.txt_status.SetValue("Donanım tercihi kaydedildi; ses işlemleri ve model eğitiminde kullanılacak.")
        except Exception as error:
            self.device_choice.SetSelection(0 if previous == "cpu" else 1)
            wx.MessageBox(str(error), "Donanım seçimi", wx.OK | wx.ICON_WARNING)

    def OnHardware(self, event):
        self.StartJob("hardware", ())

    def OnDetails(self, event):
        text = self.settings.report.describe() if self.settings.report else "Önce Donanımı kontrol et düğmesini kullanın."
        with DetailsDialog(self, "Donanımın teknik ayrıntıları", text) as dialog:
            dialog.ShowModal()
        self.btn_details.SetFocus()

    def ShowModelResult(self, summary, failed):
        self.txt_status.SetValue(summary)
        if failed:
            with DetailsDialog(self, "Hazırlanamayan model dosyaları", summary) as dialog:
                dialog.ShowModal()
            self.btn_repair.SetFocus()

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
                post_ui(self, self.txt_hardware.SetValue, report.summary(self.settings.preference))
                message = "Donanım kontrolü tamamlandı."
                try:
                    self.settings.device_for()
                except RuntimeError:
                    # Keep the saved preference visible; the user can select CPU explicitly.
                    message += " Kayıtlı donanım seçiminiz kullanılamıyor. İşlemciyi seçin; nedenini Teknik ayrıntılarda inceleyebilirsiniz."
                post_ui(self, self.txt_status.SetValue, message)
                self.LogMessage(report.summary(self.settings.preference))
            else:
                failures = self.settings.manager.process(selected, action, cancelled=lambda: self.is_cancelled,
                                                         progress=self.Progress, log=self.LogMessage)
                summary = f"{len(selected)} modelden {len(selected) - len(failures)} tanesi hazır."
                if failures:
                    names = model_catalog()
                    summary += " Hazırlanamayan modeller: " + "; ".join(
                        f"{names.get(key,key)}: {reason}" for key,reason in failures.items())
                    summary += "\nBu modelleri seçip Seçilenleri onar düğmesini kullanın. Sorun tekrarlanırsa bu hata bilgisini paylaşın."
                post_ui(self, self.ShowModelResult, summary, bool(failures))
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
