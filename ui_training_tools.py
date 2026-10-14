"""Native, keyboard-readable experiment lists and recording review dialogs."""
import json
from pathlib import Path
import wx
from ui_common import apply_native_style, name_control


class TableDialog(wx.Dialog):
    def __init__(self, parent, title, columns, rows, details=''):
        super().__init__(parent, title=title, size=(800,500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        layout = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self, label=title+'; ok tuşlarıyla satır seçin')
        layout.Add(label, 0, wx.ALL, 8)
        self.table = name_control(wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL), title)
        for i, column in enumerate(columns):
            self.table.InsertColumn(i, column, width=170 if i==0 else 120)
        for row in rows:
            index = self.table.InsertItem(self.table.GetItemCount(), str(row[0]))
            for i, value in enumerate(row[1:],1):
                self.table.SetItem(index,i,str(value))
        layout.Add(self.table, 1, wx.EXPAND | wx.ALL, 8)
        if details:
            text = name_control(wx.TextCtrl(self, value=details, style=wx.TE_MULTILINE | wx.TE_READONLY), 'Açıklama')
            layout.Add(text, 1, wx.EXPAND | wx.ALL, 8)
        layout.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL),0,wx.EXPAND | wx.ALL,8)
        self.SetSizer(layout)
        apply_native_style(self)
        if rows:
            self.table.Select(0)
        self.table.SetFocus()

    @property
    def selection(self):
        return self.table.GetFirstSelected()


def show_history(parent, job):
    path = Path(job)/'metrics.jsonl'
    rows = []
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                value = json.loads(line)
                rows.append((value['epoch'],value['step'],f"{value['holdout_mel_l1']:.5f}",
                             f"{value['loss_g']:.3f}" if 'loss_g' in value else '—',
                             f"{value['loss_d']:.3f}" if 'loss_d' in value else '—'))
            except (ValueError,KeyError,TypeError):
                continue
    with TableDialog(parent,'Eğitim değerlendirme geçmişi',('Epoch','Adım','Kontrol mel hatası','G kaybı','D kaybı'),rows,
                     'Düşük hata tek başına daha iyi ses demek değildir. Aynı kontrol kaydını farklı modellerle dinleyin. G ve D kayıpları son eğitim adımına aittir.') as dialog:
        dialog.ShowModal()
