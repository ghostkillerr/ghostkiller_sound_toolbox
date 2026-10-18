"""Compact operation readiness and actionable, native result feedback."""
from pathlib import Path
import errno
import wx
from app_runtime import JOB_LOCK
from audio_export import selected_output_format, selected_output_channels
from ui_common import explanation_control


def operation_error(error):
    text = str(error)
    lower = text.lower()
    if isinstance(error, PermissionError) or 'permission denied' in lower or 'access is denied' in lower:
        return 'Dosyaya erişilemiyor. Dosyayı kullanan programı kapatın ve yazma izniniz olan bir çıktı klasörü seçin.'
    if getattr(error, 'errno', None) == errno.ENOSPC or 'disk full' in lower or 'no space left' in lower:
        return 'Diskte yeterli boş alan yok. Yer açın veya başka bir çıktı klasörü seçin.'
    if isinstance(error, MemoryError) or 'out of memory' in lower or 'unable to allocate' in lower or 'bellek' in lower and ('yetersiz' in lower or 'yetmiyor' in lower):
        return 'İşlem için bellek yetmedi. Diğer uygulamaları kapatın veya daha kısa bir kayıtla deneyin. Ekran kartı kullanıyorsanız Ayarlar’dan işlemciyi seçebilirsiniz.'
    return text or 'İşlem tamamlanamadı. Ayrıntıları işlem günlüğünde bulabilirsiniz.'


def open_result_folder(window, folder):
    try:
        if not Path(folder).is_dir() or not wx.LaunchDefaultApplication(str(folder)):
            raise OSError('Klasör açılamadı: ' + str(folder))
    except Exception as error:
        log = getattr(window, 'LogMessage', None)
        if log:
            log('Sonuçlar kaydedildi; klasör otomatik açılamadı. ' + str(error))


def show_result(window, message, title, style, folder=None):
    wx.MessageBox(message, title, style, parent=window)
    if folder:
        open_result_folder(window, folder)


class OperationPreparation(wx.Panel):
    def __init__(self, owner, settings, required, summary=None):
        super().__init__(owner)
        self.owner, self.settings, self.required = owner, settings, required
        self.custom_summary = summary
        layout = wx.BoxSizer(wx.VERTICAL)
        self.summary = explanation_control(self, 'Çıktı ayarları', '')
        layout.Add(self.summary, 0, wx.EXPAND | wx.BOTTOM, 4)
        self.button = wx.Button(self, label='Bu işlem için eksik modelleri hazırla')
        self.button.Bind(wx.EVT_BUTTON, self.OnPrepare)
        layout.Add(self.button, 0, wx.BOTTOM, 4)
        self.SetSizer(layout)
        self.RefreshReadiness()

    def MissingModels(self):
        manager = getattr(self.settings, 'manager', None)
        if manager is None:
            return ()
        return tuple(key for key in dict.fromkeys(self.required()) if manager.status(key) != 'Hazır')

    def RefreshReadiness(self):
        channels = {'original': 'Kanal düzeni korunur', 'mono': 'Mono', 'stereo': 'Stereo'}
        device = 'Ekran kartı' if getattr(self.settings, 'preference', 'cpu') == 'gpu' else 'İşlemci'
        text = f"Çıktı: {selected_output_format(self.settings).upper()} · {channels[selected_output_channels(self.settings)]} · {device}"
        if self.custom_summary:
            text = self.custom_summary()
        self.summary.SetLabel(text)
        self.summary.SetName(text)
        self.summary.GetAccessible().name = text
        self.summary._ui_wrap_text = text
        visible = bool(self.MissingModels())
        changed = self.button.IsShown() != visible
        self.button.Show(visible)
        self.button.Enable(not JOB_LOCK.locked())
        self.Layout()
        if changed:
            self.owner.Layout()
            self.owner.FitInside()

    def OnPrepare(self, event):
        missing = self.MissingModels()
        if not missing or JOB_LOCK.locked():
            self.RefreshReadiness()
            return
        prepare = getattr(self.settings, 'prepare_models', None)
        if prepare:
            prepare(missing)
        else:
            self.settings.open_settings()
