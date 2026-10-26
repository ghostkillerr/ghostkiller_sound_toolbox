"""One reusable local RVC model import form, without changing source files."""
from pathlib import Path
import wx
from ui_common import apply_native_style, name_control


class AddModelDialog(wx.Dialog):
    def __init__(self, parent, names):
        super().__init__(parent, title='Ses modeli ekle', style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.names = set(names)
        self.SetSize(self.FromDIP((620, 420)))
        layout = wx.BoxSizer(wx.VERTICAL)
        intro = wx.StaticText(self, label='Hazır RVC model dosyanızı ekleyin. Modeliniz yoksa Model Eğitimi sekmesinden kendi kayıtlarınızla oluşturabilirsiniz.')
        intro.Wrap(self.FromDIP(560))
        layout.Add(intro, 0, wx.ALL, 12)
        layout.Add(wx.StaticText(self, label='Ses modelinin adı'), 0, wx.LEFT, 12)
        self.model_name = name_control(wx.TextCtrl(self), 'Ses modelinin adı')
        layout.Add(self.model_name, 0, wx.EXPAND | wx.ALL, 12)
        self.paths = {}
        for key, label, extension in (('pth', 'RVC model dosyası (.pth, zorunlu)', 'pth'),
                                       ('index', 'Eğitim desteği (.index, isteğe bağlı)', 'index')):
            layout.Add(wx.StaticText(self, label=label), 0, wx.LEFT, 12)
            row = wx.BoxSizer(wx.HORIZONTAL)
            field = name_control(wx.TextCtrl(self), label)
            self.paths[key] = field
            row.Add(field, 1, wx.EXPAND | wx.RIGHT, 8)
            browse = wx.Button(self, label='Dosya seç')
            browse.Bind(wx.EVT_BUTTON, lambda event, k=key, ext=extension: self.Browse(k, ext))
            row.Add(browse, 0)
            layout.Add(row, 0, wx.EXPAND | wx.ALL, 12)
        layout.Add(wx.StaticText(self, label='Index yoksa alanı boş bırakın; model index olmadan kullanılabilir.'), 0, wx.ALL, 12)
        self.error = wx.StaticText(self, label='')
        layout.Add(self.error, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        self.FindWindow(wx.ID_OK).SetLabel('Modeli ekle')
        self.Bind(wx.EVT_BUTTON, self.OnSave, id=wx.ID_OK)
        layout.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizer(layout)
        apply_native_style(self)
        layout.SetSizeHints(self)
        self.CentreOnParent()
        self.model_name.SetFocus()

    def Browse(self, key, extension):
        with wx.FileDialog(self, 'Model dosyasını seçin' if key == 'pth' else 'Index dosyasını seçin',
                           wildcard=f'{extension} dosyaları|*.{extension}',
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.paths[key].SetValue(dialog.GetPath())
                if key == 'pth' and not self.model_name.GetValue().strip():
                    self.model_name.SetValue(Path(dialog.GetPath()).stem)

    def Value(self):
        return self.model_name.GetValue().strip(), {key: field.GetValue().strip() for key, field in self.paths.items()}

    def OnSave(self, event):
        name, paths = self.Value()
        message, control = '', None
        if not name or name in self.names:
            message, control = 'Boş olmayan, listede kullanılmayan bir ad yazın.', self.model_name
        else:
            for key in ('pth', 'index'):
                value = paths[key]
                if (key == 'pth' or value) and (not Path(value).is_file() or Path(value).suffix.lower() != '.' + key):
                    message, control = f'Geçerli bir .{key} dosyası seçin.', self.paths[key]
                    break
        if message:
            self.error.SetLabel(message)
            control.SetFocus()
            self.Layout()
            return
        self.EndModal(wx.ID_OK)
