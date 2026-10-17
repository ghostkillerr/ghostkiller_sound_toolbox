"""Explain the optional model's terms before downloading or using it."""
import wx
from restoration import MODEL_LICENSE_URL, MODEL_USAGE_NOTICE
from ui_common import explanation_control, apply_native_style


class ModelTermsDialog(wx.Dialog):
    def __init__(self, parent, title, notice, url, publisher):
        super().__init__(parent, title=title)
        layout = wx.BoxSizer(wx.VERTICAL)
        text = explanation_control(self, 'Model kullanım koşulları', notice)
        layout.Add(text, 0, wx.EXPAND | wx.ALL, 16)
        source = wx.Button(self, label=publisher+' model koşullarını tarayıcıda aç')
        source.Bind(wx.EVT_BUTTON, lambda event: wx.LaunchDefaultBrowser(url))
        layout.Add(source, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
        buttons = wx.StdDialogButtonSizer()
        accept = wx.Button(self, wx.ID_OK, 'Koşulları kabul ederek devam et')
        cancel = wx.Button(self, wx.ID_CANCEL, 'Vazgeç')
        buttons.AddButton(accept)
        buttons.AddButton(cancel)
        buttons.Realize()
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 16)
        apply_native_style(self)
        text.SetLabel(notice)
        text.Wrap(self.FromDIP(560))
        self.SetSizerAndFit(layout)
        self.SetEscapeId(wx.ID_CANCEL)
        cancel.SetDefault()
        text.SetFocus()
        self.CentreOnParent()


class RestorationTermsDialog(ModelTermsDialog):
    def __init__(self, parent):
        super().__init__(parent, 'Vokal onarım modelinin kullanım koşulları',
                         MODEL_USAGE_NOTICE, MODEL_LICENSE_URL, 'NVIDIA')


class DemucsTermsDialog(ModelTermsDialog):
    def __init__(self, parent):
        from instruments import DEMUCS_USAGE_NOTICE, DEMUCS_TERMS_URL
        super().__init__(parent, 'Altı kanallı modelin kullanım koşulları',
                         DEMUCS_USAGE_NOTICE, DEMUCS_TERMS_URL, 'Demucs')


def _confirm_terms(parent, dialog_type, attribute):
    root = wx.GetTopLevelParent(parent)
    if getattr(root, attribute, False):
        return True
    with dialog_type(parent) as dialog:
        accepted = dialog.ShowModal() == wx.ID_OK
    if accepted:
        setattr(root, attribute, True)
    return accepted


def confirm_restoration_terms(parent):
    """Accept once per application window; checking local files needs no consent."""
    return _confirm_terms(parent, RestorationTermsDialog, '_a2sb_terms_accepted')


def confirm_demucs_terms(parent):
    return _confirm_terms(parent, DemucsTermsDialog, '_demucs_terms_accepted')
