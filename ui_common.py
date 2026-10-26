"""Shared native appearance and keyboard-accessible read-only details."""
import wx


class NamedAccessible(wx.Accessible):
    """Supply the native control's name while retaining its native role/state."""
    def __init__(self, window, name, help_text=''):
        super().__init__(window)
        self.name, self.help_text = name, help_text

    def GetName(self, child_id):
        if child_id == wx.ACC_SELF:
            return wx.ACC_OK, self.name
        return wx.ACC_NOT_IMPLEMENTED, ''

    def GetHelpText(self, child_id):
        if child_id == wx.ACC_SELF:
            return wx.ACC_OK, self.help_text
        return wx.ACC_NOT_IMPLEMENTED, ''

    def GetDescription(self, child_id):
        return self.GetHelpText(child_id)

def name_control(control, name, help_text=''):
    control.SetName(name)
    control.SetHelpText(help_text)
    control.SetAccessible(NamedAccessible(control,name,help_text))
    return control


class ToggleAccessible(wx.Accessible):
    """Expose a visual toggle as a checked/unchecked selection to MSAA.

    These controls select processing steps, stems or models. A push-button
    ``pressed`` state is ambiguous in NVDA, so expose their checkbox semantics
    while retaining the existing visual ToggleButton design.
    """
    def __init__(self, window, help_text=''):
        super().__init__(window)
        self.help_text = help_text

    def GetName(self, child_id):
        return (wx.ACC_OK, self.GetWindow().GetLabel()) if child_id == wx.ACC_SELF else (wx.ACC_NOT_IMPLEMENTED, '')

    def GetRole(self, child_id):
        return (wx.ACC_OK, wx.ROLE_SYSTEM_CHECKBUTTON) if child_id == wx.ACC_SELF else (wx.ACC_NOT_IMPLEMENTED, 0)

    def GetState(self, child_id):
        if child_id != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, 0
        control = self.GetWindow()
        state = wx.ACC_STATE_SYSTEM_FOCUSABLE
        if control.GetValue(): state |= wx.ACC_STATE_SYSTEM_CHECKED
        if control.HasFocus(): state |= wx.ACC_STATE_SYSTEM_FOCUSED
        if not control.IsEnabled(): state |= wx.ACC_STATE_SYSTEM_UNAVAILABLE
        if not control.IsShownOnScreen(): state |= wx.ACC_STATE_SYSTEM_INVISIBLE
        return wx.ACC_OK, state

    def GetHelpText(self, child_id):
        return (wx.ACC_OK, self.help_text) if child_id == wx.ACC_SELF else (wx.ACC_NOT_IMPLEMENTED, '')

    def GetDescription(self, child_id):
        return self.GetHelpText(child_id)

    def GetDefaultAction(self, child_id):
        if child_id == wx.ACC_SELF:
            return wx.ACC_OK, 'İşaretini kaldır' if self.GetWindow().GetValue() else 'İşaretle'
        return wx.ACC_NOT_IMPLEMENTED, ''

    def DoDefaultAction(self, child_id):
        control = self.GetWindow()
        if child_id != wx.ACC_SELF or not control.IsEnabled() or not control.IsShownOnScreen():
            return wx.ACC_FAIL
        control.SetValue(not control.GetValue())
        event = wx.CommandEvent(wx.EVT_TOGGLEBUTTON.typeId,control.GetId())
        event.SetEventObject(control)
        control.GetEventHandler().ProcessEvent(event)
        return wx.ACC_OK


class CheckBoxAccessible(NamedAccessible):
    """Report a real checkbox's current state instead of a cached MSAA state."""
    def GetRole(self, child_id):
        return (wx.ACC_OK, wx.ROLE_SYSTEM_CHECKBUTTON) if child_id == wx.ACC_SELF else (wx.ACC_NOT_IMPLEMENTED, 0)

    def GetState(self, child_id):
        if child_id != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, 0
        control = self.GetWindow()
        state = wx.ACC_STATE_SYSTEM_FOCUSABLE
        if control.GetValue():
            state |= wx.ACC_STATE_SYSTEM_CHECKED
        if control.HasFocus():
            state |= wx.ACC_STATE_SYSTEM_FOCUSED
        if not control.IsEnabled():
            state |= wx.ACC_STATE_SYSTEM_UNAVAILABLE
        if not control.IsShownOnScreen():
            state |= wx.ACC_STATE_SYSTEM_INVISIBLE
        return wx.ACC_OK, state

    def GetDefaultAction(self, child_id):
        if child_id == wx.ACC_SELF:
            return wx.ACC_OK, 'İşaretini kaldır' if self.GetWindow().GetValue() else 'İşaretle'
        return wx.ACC_NOT_IMPLEMENTED, ''

    def DoDefaultAction(self, child_id):
        control = self.GetWindow()
        if child_id != wx.ACC_SELF or not control.IsEnabled() or not control.IsShownOnScreen():
            return wx.ACC_FAIL
        control.SetValue(not control.GetValue())
        event = wx.CommandEvent(wx.EVT_CHECKBOX.typeId, control.GetId())
        event.SetEventObject(control)
        control.GetEventHandler().ProcessEvent(event)
        return wx.ACC_OK


def checkbox_control(control, name=None, help_text=''):
    """Apply explicit, dynamically queried checkbox accessibility semantics."""
    name = name or control.GetLabel()
    control.SetName(name)
    control.SetHelpText(help_text)
    control.SetAccessible(CheckBoxAccessible(control, name, help_text))
    return control


class ExplanationAccessible(NamedAccessible):
    def GetRole(self, child_id):
        if child_id == wx.ACC_SELF:
            return wx.ACC_OK, wx.ROLE_SYSTEM_STATICTEXT
        return wx.ACC_NOT_IMPLEMENTED, 0

    def GetState(self, child_id):
        if child_id == wx.ACC_SELF:
            state = wx.ACC_STATE_SYSTEM_FOCUSABLE
            if self.GetWindow().HasFocus(): state |= wx.ACC_STATE_SYSTEM_FOCUSED
            return wx.ACC_OK, state
        return wx.ACC_NOT_IMPLEMENTED, 0


class ExplanationText(wx.StaticText):
    """Native plain text with keyboard focus and a static-text accessibility role."""
    def __init__(self, parent, text):
        super().__init__(parent,label=text,style=wx.WANTS_CHARS)
        self.SetCanFocus(True)
        self.SetName(text)
        self.SetAccessible(ExplanationAccessible(self,text))
        self.Bind(wx.EVT_CHAR,self.OnChar)
        self.Bind(wx.EVT_SET_FOCUS,self.OnFocus)

    def AcceptsFocus(self):
        return True

    def AcceptsFocusFromKeyboard(self):
        return True

    def OnChar(self,event):
        if event.GetKeyCode()==wx.WXK_TAB:
            self.Navigate(wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward)
        else:
            event.Skip()

    def OnFocus(self,event):
        event.Skip()
        wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_FOCUS,self,wx.OBJID_CLIENT,wx.ACC_SELF)


def explanation_control(parent, name, text):
    control = ExplanationText(parent,text)
    control._ui_wrap_text = text
    control.Wrap(parent.FromDIP(620))
    return control


def window_theme(window):
    current = window
    while current:
        settings = getattr(current,'settings',None)
        if settings is not None:
            return getattr(settings,'theme','light')
        current = current.GetParent()
    return 'light'


def high_contrast_enabled():
    import ctypes
    import os
    if os.name != 'nt':
        return False
    from ctypes import wintypes
    class HighContrast(ctypes.Structure):
        _fields_ = [('size', wintypes.UINT), ('flags', wintypes.DWORD), ('scheme', wintypes.LPWSTR)]
    value = HighContrast()
    value.size = ctypes.sizeof(value)
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x0042, value.size, ctypes.byref(value), 0)
                and value.flags & 1)


def add_intro(window, layout, title, description):
    heading = wx.StaticText(window, label=title)
    heading._ui_heading = True
    text = wx.StaticText(window, label=description)
    text._ui_wrap_text = description
    text.Wrap(window.FromDIP(620))
    layout.Insert(0, text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
    layout.Insert(0, heading, 0, wx.EXPAND | wx.ALL, 12)


def section_title(window, layout, text):
    heading = wx.StaticText(window, label=text)
    heading._ui_section = True
    layout.Add(heading, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
    return heading


def fit_panel_text(panel):
    width = max(panel.FromDIP(240), panel.GetClientSize().width - panel.FromDIP(32))
    if getattr(panel, '_ui_wrap_width', None) == width:
        return
    panel._ui_wrap_width = width
    for child in panel.GetChildren():
        if isinstance(child, wx.StaticText) and (hasattr(child, '_ui_wrap_text') or len(child.GetLabel()) > 70):
            if not hasattr(child, '_ui_wrap_text'):
                child._ui_wrap_text = child.GetLabel()
            child.SetLabel(child._ui_wrap_text)
            child.Wrap(width)
    panel.Layout()
    panel.FitInside()


def apply_native_style(window, contrast=None, theme=None):
    """Use Windows colours, including the user's high-contrast palette."""
    if contrast is None:
        contrast = high_contrast_enabled()
        if isinstance(window, wx.ScrolledWindow) and not getattr(window, '_ui_style_bound', False):
            window._ui_style_bound = True
            def on_size(event):
                fit_panel_text(window)
                event.Skip()
            def on_colours(event):
                apply_native_style(window)
                window.Refresh()
                event.Skip()
            window.Bind(wx.EVT_SIZE, on_size)
            window.Bind(wx.EVT_SYS_COLOUR_CHANGED, on_colours)
    theme = theme or window_theme(window)
    dark = theme == 'dark'
    background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE) if contrast else wx.Colour('#202733' if dark else '#F3F5F9')
    foreground = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT) if contrast else wx.Colour('#EDF2FA' if dark else '#243247')
    font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    font.SetPointSize(11)
    window.SetFont(font)
    window.SetForegroundColour(foreground)
    is_field = isinstance(window, (wx.TextCtrl, wx.ListBox, wx.Choice))
    field_background = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW) if contrast else wx.Colour('#303B4B' if dark else '#FFFFFF')
    window.SetBackgroundColour(field_background if is_field else background)
    if isinstance(window, wx.StaticBox) or getattr(window, '_ui_section', False):
        window.SetFont(font.Bold())
    if getattr(window, '_ui_heading', False):
        heading_font = font.Bold()
        heading_font.SetPointSize(18)
        window.SetFont(heading_font)
        if not contrast:
            window.SetForegroundColour(wx.Colour('#A7CFFF' if dark else '#174A8B'))
    if isinstance(window, (wx.Button, wx.ToggleButton)):
        # Native Windows hover/pressed backgrounds do not honor custom dark
        # foregrounds consistently. Keep a readable native button palette.
        window.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT))
        window.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE))
        if getattr(window, '_ui_primary', False):
            window.SetFont(font.Bold())
        # Let labels determine width; use one compact height across all panels.
        window.SetMinSize((-1, window.FromDIP(36)))
    for child in window.GetChildren():
        apply_native_style(child, contrast, theme)


class RadioChoice(wx.Panel):
    """Native radio buttons whose individual labels can follow the theme."""
    def __init__(self, parent, label, choices, **kwargs):
        super().__init__(parent, style=wx.TAB_TRAVERSAL)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label=label), 0, wx.BOTTOM, 4)
        self.buttons = []
        row = wx.WrapSizer(wx.HORIZONTAL)
        for index, text in enumerate(choices):
            button = wx.RadioButton(self, label=text, style=wx.RB_GROUP if index == 0 else 0)
            button.Bind(wx.EVT_RADIOBUTTON, self.OnChoice)
            self.buttons.append(button)
            row.Add(button, 0, wx.RIGHT | wx.BOTTOM, 16)
        layout.Add(row, 0, wx.EXPAND)
        self.SetSizer(layout)

    def GetSelection(self):
        return next((i for i, button in enumerate(self.buttons) if button.GetValue()), 0)

    def GetCount(self):
        return len(self.buttons)

    def SetSelection(self, index):
        self.buttons[index].SetValue(True)

    def SetFocus(self):
        self.buttons[self.GetSelection()].SetFocus()

    def OnChoice(self, event):
        changed = wx.CommandEvent(wx.EVT_RADIOBOX.typeId, self.GetId())
        changed.SetEventObject(self)
        changed.SetInt(self.GetSelection())
        self.GetEventHandler().ProcessEvent(changed)


def fold_controls(owner, layout, controls, label='İşlem günlüğünü göster'):
    """Keep detailed, keyboard-accessible content off the basic task path."""
    toggle = wx.ToggleButton(owner, label=label + ' [KAPALI]')
    layout.Add(toggle, 0, wx.ALL, 6)
    for control in controls:
        layout.Detach(control)
        layout.Add(control, 0, wx.EXPAND | wx.ALL, 6)
        control.Hide()
    def changed(event):
        for control in controls:
            control.Show(toggle.GetValue())
        toggle.SetLabel(label + (' [AÇIK]' if toggle.GetValue() else ' [KAPALI]'))
        owner.Layout()
        owner.FitInside()
    toggle.Bind(wx.EVT_TOGGLEBUTTON, changed)
    return toggle


def request_field(owner, message, control):
    """Ordinary incomplete input is guidance, not an application failure."""
    owner.txt_status.SetValue(message)
    control.SetFocus()
    wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_VALUECHANGE, owner.txt_status,
                              wx.OBJID_CLIENT, wx.ACC_SELF)


class DetailsDialog(wx.Dialog):
    def __init__(self, parent, title, text):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.SetSize(self.FromDIP((620, 430)))
        layout = wx.BoxSizer(wx.VERTICAL)
        self.details = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.details.SetName(title)
        layout.Add(self.details, 1, wx.EXPAND | wx.ALL, 12)
        close = wx.Button(self, wx.ID_CANCEL, label="Kapat")
        close.SetDefault()
        layout.Add(close, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        self.SetSizer(layout)
        apply_native_style(self)
        self.CentreOnParent()
        self.details.SetFocus()
