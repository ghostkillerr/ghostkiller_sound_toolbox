# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - AI Cover Modülü (ui_cover.py)

Bu modül, RVC (Retrieval-based Voice Conversion) yapay zeka cover çıkarım (inference) arayüzü
ve model yönetim sistemini modüler bir wx.Panel (CoverPanel) olarak sağlar.

Özellikler:
1. Erişilebilirlik (A11y): Ses Ayrıştırma (Sound Cleaner) modülüyle aynı şekilde,
   her model için onay kutusu rolü, canlı işaretli/işaretsiz durumu ve
   "[AÇIK]" / "[KAPALI]" adını sunan ModelToggleList bileşeni barındırır.
2. 'models.json' üzerinden kalıcı model (.pth ve opsiyonel .index) yönetimi (Ekle / Sil).
3. RTX 5060 Ti 16 GB VRAM sınırlarını korumak için tekli kuyruk (queue) threading mimarisi.
   Aynı anda birden fazla model asla çalıştırılmaz, her işlem arası VRAM/GC temizliği yapılır.
4. Pitch (Nota kaydırma), Donanım (cuda/cpu), F0 Algoritması (rmvpe / crepe) ve
   Index Rate ayarlarının erişilebilir biçimde yapılandırılması.
"""

import wx
from ui_common import apply_native_style, add_intro, checkbox_control, ToggleAccessible
from audio_export import (export_audio, selected_output_format, normalize_output_format,
                          selected_output_channels, normalize_output_channels)
from ui_operation import OperationPreparation, show_result, operation_error
import os
import sys
import json
import gc
import math
import tempfile
import threading
from registry_store import validate_models
from app_runtime import (JOB_LOCK, post_ui, append_log, safe_filename, data_directory, model_directory,
                         copy_model, download_model, same_path, validate_audio_file, finish_job)


def get_app_dir():
    """Uygulamanın çalıştığı kök dizini döndürür."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_models_file_path(app_dir):
    """models.json dosyasının yolunu döndürür."""
    directory = data_directory() if getattr(sys, "frozen", False) else app_dir
    target = os.path.join(directory, "models.json")
    legacy = os.path.join(app_dir, "models.json")
    if target != legacy and not os.path.exists(target) and os.path.isfile(legacy):
        from registry_store import registry_lock
        with registry_lock(target):
            if not os.path.exists(target):
                copy_model(legacy, target)
    return target


def load_models(app_dir):
    """models.json içinden kayıtlı modelleri yükler."""
    try:
        file_path = get_models_file_path(app_dir)
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            models = json.load(f)
        return validate_models(models)
    except Exception as error:
        wx.MessageBox(f"Model kayıtları okunamadı. Dosya korunuyor; model eklemeden önce dosyayı onarın.\n{error}", "Model Kayıt Hatası", wx.OK | wx.ICON_ERROR)
        return {}


def save_models(app_dir, models, previous=None):
    """modelleri models.json dosyasına kaydeder."""
    try:
        from registry_store import apply_model_changes
        file_path = get_models_file_path(app_dir)
        validate_models(models)
        apply_model_changes(file_path,models,previous,validate_models)
        return True
    except Exception as e:
        wx.MessageBox(f"Model kayıtları kaydedilemedi:\n{e}", "Kayıt Hatası", wx.OK | wx.ICON_ERROR)
        return False


def ensure_rvc_prerequisites(app_dir, log_func=None, f0_method="rmvpe", cancelled=None, allow_download=False):
    """
    RVC için gereken temel model dosyalarını (rmvpe.pt ve contentvec/pytorch_model.bin)
    1. Programın 'models' klasöründe kontrol eder.
    2. Eski yerel model/önbellek klasörlerinde arar; bulursa atomik kopyalar.
    3. GUI indirme yapmaz; eksik dosyalar Ayarlar'dan hazırlanır.
       Eski API'nin indirme yolu yalnız allow_download=True ile kullanılabilir.
    """
    model_root = model_directory(app_dir)
    if not allow_download:
        required = [os.path.join(model_root, "embedders", "contentvec", filename)
                    for filename in ("pytorch_model.bin", "config.json")]
        if f0_method == "rmvpe":
            required.append(os.path.join(model_root, "predictors", "rmvpe.pt"))
        if any(not os.path.isfile(path) or not os.path.getsize(path) for path in required):
            raise FileNotFoundError("AI Cover yardımcı modelleri eksik. Ayarlar sekmesinden indirin veya onarın.")
        return
    from model_manager import ModelManager
    manager = ModelManager(app_dir)
    required = ['contentvec'] + (['rmvpe'] if f0_method == 'rmvpe' else [])
    failures = manager.process(required, 'install', cancelled=cancelled, log=log_func)
    if failures:
        raise RuntimeError('; '.join(f'{name}: {error}' for name,error in failures.items()))



def resolve_model_file_path(app_dir, file_path):
    """
    Eğer models.json içindeki yol (pth/index) bu bilgisayarda doğrudan mevcut değilse
    (örneğin başka bir arkadaşın bilgisayarı), programın kurulu olduğu yerdeki 'modeller'
    klasöründe bu dosyayı arayarak bulur.
    """
    if not file_path:
        return ""
    if not os.path.isabs(file_path):
        file_path = os.path.join(app_dir, file_path)
    if os.path.isfile(file_path):
        return file_path
    filename = os.path.basename(file_path)
    directories = [os.path.join(app_dir, "models"), os.path.join(app_dir, "modeller")]
    matches = []
    for modeller_dir in dict.fromkeys(directories):
        for root, dirs, files in os.walk(modeller_dir):
            if filename in files:
                matches.append(os.path.join(root, filename))
    if len(matches) > 1:
        raise ValueError(f"Aynı isimde birden fazla model dosyası bulundu: {filename}. Modeli tam yoluyla tekrar ekleyin.")
    if matches:
        return matches[0]
    return file_path


class ModelToggleList(wx.ScrolledWindow):
    """
    Sound Cleaner (ui_separator.py) ile birebir aynı A11y / NVDA mantığına sahip
    Model Seçim Listesi Bileşeni.
    Her model için standart bir wx.ToggleButton (Aç/Kapat Düğmesi) oluşturulur.
    Ekran okuyucular (NVDA/JAWS) her öğeyi onay kutusu olarak ve
    '[AÇIK]' / '[KAPALI]' durumuyla okur.
    Yukarı/Aşağı ok tuşları ve Tab ile dolaşım desteklenir.
    """
    def __init__(self, parent):
        """ModelToggleList arayüzünü ve kaydırma özelliklerini başlatır."""
        super(ModelToggleList, self).__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.SetBackgroundColour(wx.Colour(40, 40, 40))
        self.SetForegroundColour(wx.Colour(240, 240, 240))
        self.SetScrollRate(5, 20)
        self.buttons = []
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.bg_btn = wx.Colour(60, 60, 60)
        self.bg_btn_active = wx.Colour(0, 120, 215)
        self.fg_light = wx.Colour(240, 240, 240)

    def SetModels(self, model_names, labels=None, checked_models=None):
        """Mevcut butonları temizler ve her model için yeni wx.ToggleButton oluşturur."""
        checked = set(self.GetCheckedModels() if checked_models is None else checked_models)
        labels = labels or {}
        if model_names and model_names == [button.model_name for button in self.buttons]:
            for button in self.buttons:
                button.display_name = labels.get(button.model_name, button.model_name)
                button.SetValue(button.model_name in checked)
                self.UpdateModelButton(button)
            return
        self.sizer.Clear(True)
        self.buttons = []

        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        if not model_names:
            lbl_empty = wx.StaticText(
                self,
                label="Henüz ses modeli eklenmedi. Ses modeli ekle düğmesini kullanın."
            )
            lbl_empty.SetFont(font_normal)
            lbl_empty.SetForegroundColour(wx.Colour(180, 180, 180))
            self.sizer.Add(lbl_empty, 0, wx.ALL, 10)
        else:
            for i, name in enumerate(model_names):
                selected = name in checked
                display_name = labels.get(name, name)
                btn = wx.ToggleButton(self, label=f"{display_name} - [{'AÇIK' if selected else 'KAPALI'}]", size=(-1, 42))
                btn.SetFont(font_normal)
                btn.SetForegroundColour(self.fg_light)
                btn.SetBackgroundColour(self.bg_btn_active if selected else self.bg_btn)
                btn.SetValue(selected)
                btn.model_name = name
                btn.display_name = display_name
                btn.SetAccessible(ToggleAccessible(btn))
                btn.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggleModel)
                btn.Bind(wx.EVT_KEY_DOWN, lambda event, idx=i: self.OnKeyDown(event, idx))
                self.buttons.append(btn)
                self.sizer.Add(btn, 0, wx.EXPAND | wx.ALL, 4)

        apply_native_style(self)
        self.Layout()
        self.FitInside()
        self.Refresh()

    def OnToggleModel(self, event):
        """Bir model düğmesine tıklandığında [AÇIK]/[KAPALI] etiketini ve rengini günceller."""
        btn = event.GetEventObject()
        self.UpdateModelButton(btn)

    def UpdateModelButton(self, btn):
        if btn.GetValue():
            btn.SetLabel(f"{btn.display_name} - [AÇIK]")
            btn.SetBackgroundColour(self.bg_btn_active)
        else:
            btn.SetLabel(f"{btn.display_name} - [KAPALI]")
            btn.SetBackgroundColour(self.bg_btn)
        apply_native_style(btn)
        btn.Refresh()
        wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_NAMECHANGE, btn, wx.OBJID_CLIENT, wx.ACC_SELF)
        wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_STATECHANGE, btn, wx.OBJID_CLIENT, wx.ACC_SELF)

    def OnKeyDown(self, event, idx):
        """Klavye Yukarı/Aşağı ok tuşları ile model listesi arasında NVDA erişilebilir dolaşımı sağlar."""
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DOWN:
            if idx + 1 < len(self.buttons):
                self.FocusModel(idx + 1)
        elif keycode == wx.WXK_UP:
            if idx - 1 >= 0:
                self.FocusModel(idx - 1)
        else:
            event.Skip()

    def FocusModel(self, idx):
        button = self.buttons[idx]
        button.SetFocus()
        _, top = self.CalcUnscrolledPosition(button.GetPosition())
        _, unit = self.GetScrollPixelsPerUnit()
        _, view = self.GetViewStart()
        height = self.GetClientSize().height
        bottom = top + button.GetSize().height
        if unit and top < view * unit:
            self.Scroll(-1, top // unit)
        elif unit and bottom > view * unit + height:
            self.Scroll(-1, max(0, math.ceil((bottom - height) / unit)))

    def GetCheckedModels(self):
        """[AÇIK] / Basılı durumda olan model adlerinin listesini döndürür."""
        return [btn.model_name for btn in self.buttons if btn.GetValue()]


class CoverPanel(wx.ScrolledWindow):
    """
    AI Cover Sekmesi Paneli (wx.Notebook ile uyumlu)
    """
    def __init__(self, parent, settings=None):
        """AI Cover paneli değişkenlerini, modellerini ve renk paletini başlatır."""
        super(CoverPanel, self).__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.SetScrollRate(0,20)
        from app_settings import AppSettings
        self.settings = settings or AppSettings()

        self.app_dir = get_app_dir()
        self.models = load_models(self.app_dir)

        self.input_audio_path = ""
        self.output_folder_path = ""
        self.is_cancelled = False
        from audio_service import NativeAudioSession
        self.audio_session_factory = NativeAudioSession
        self.audio_session = None

        # Temalı Renk Tanımlamaları
        self.bg_main = wx.Colour(30, 30, 30)
        self.bg_panel = wx.Colour(40, 40, 40)
        self.bg_btn = wx.Colour(60, 60, 60)
        self.bg_btn_active = wx.Colour(0, 120, 215)
        self.fg_light = wx.Colour(240, 240, 240)
        self.fg_status = wx.Colour(100, 200, 255)
        self.fg_log = wx.Colour(0, 255, 128)

        self.InitUI()

    def InitUI(self):
        """Tüm paneli, model seçim listesini, ayar kontrollerini ve butonları inşa eder."""

        font_large = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.SetBackgroundColour(self.bg_main)
        self.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. MODEL YÖNETİMİ BÖLÜMÜ
        box_models = wx.StaticBox(self, label="1. Ses Modeli Seçimi")
        box_models.SetForegroundColour(self.fg_light)
        box_models.SetFont(font_large)
        sizer_models = wx.StaticBoxSizer(box_models, wx.VERTICAL)

        btn_model_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_model = wx.Button(self, label="Ses modeli ekle", size=(-1, 40))
        self.btn_add_model.SetFont(font_normal)
        self.btn_add_model.SetBackgroundColour(self.bg_btn)
        self.btn_add_model.SetForegroundColour(self.fg_light)
        self.btn_add_model.Bind(wx.EVT_BUTTON, self.OnAddModel)

        self.btn_del_model = wx.Button(self, label="Seçili modeli listeden kaldır", size=(-1, 40))
        self.btn_del_model.SetFont(font_normal)
        self.btn_del_model.SetBackgroundColour(wx.Colour(150, 60, 60))
        self.btn_del_model.SetForegroundColour(self.fg_light)
        self.btn_del_model.Bind(wx.EVT_BUTTON, self.OnDelModel)

        btn_model_box.Add(self.btn_add_model, 1, wx.ALL | wx.EXPAND, 5)
        btn_model_box.Add(self.btn_del_model, 0, wx.ALL | wx.EXPAND, 5)
        sizer_models.Add(btn_model_box, 0, wx.EXPAND | wx.ALL, 5)

        lbl_select_info = wx.StaticText(
            self,
            label="Kullanacağınız ses modellerini Boşluk ile seçin. Ok tuşlarıyla listede dolaşın."
        )
        lbl_select_info.SetFont(font_normal)
        sizer_models.Add(lbl_select_info, 0, wx.ALL, 5)

        # A11y (Erişilebilirlik): Sound Cleaner (ui_separator.py) sekmesiyle birebir aynı
        # [AÇIK] / [KAPALI] ve basılı/basılı değil okuma mantığına sahip ModelToggleList.
        self.model_list = ModelToggleList(self)
        self.model_list.SetMinSize((-1, 100))
        self.UpdateModelCheckList()
        sizer_models.Add(self.model_list, 1, wx.EXPAND | wx.ALL, 5)

        vbox.Add(sizer_models, 1, wx.EXPAND | wx.ALL, 5)

        # 2. DOSYA YOLLARI (Girdi ve Çıktı)
        box_paths = wx.StaticBox(self, label="2. Dosya Seçimi")
        box_paths.SetForegroundColour(self.fg_light)
        box_paths.SetFont(font_large)
        sizer_paths = wx.StaticBoxSizer(box_paths, wx.VERTICAL)

        # Girdi ses dosyası
        input_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_input = wx.Button(self, label="Ses dosyası seç", size=(-1, 40))
        self.btn_select_input.SetFont(font_normal)
        self.btn_select_input.SetBackgroundColour(self.bg_btn)
        self.btn_select_input.SetForegroundColour(self.fg_light)
        self.btn_select_input.Bind(wx.EVT_BUTTON, self.OnSelectInput)

        self.txt_selected_input = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_input.SetBackgroundColour(self.bg_panel)
        self.txt_selected_input.SetForegroundColour(self.fg_light)
        self.txt_selected_input.SetFont(font_normal)

        input_box.Add(self.btn_select_input, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        input_box.Add(self.txt_selected_input, 1, wx.ALL | wx.EXPAND, 5)
        sizer_paths.Add(input_box, 0, wx.EXPAND | wx.ALL, 5)

        # Çıktı Klasörü
        output_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_output = wx.Button(self, label="Çıktı klasörü seç", size=(-1, 40))
        self.btn_select_output.SetFont(font_normal)
        self.btn_select_output.SetBackgroundColour(self.bg_btn)
        self.btn_select_output.SetForegroundColour(self.fg_light)
        self.btn_select_output.Bind(wx.EVT_BUTTON, self.OnSelectOutput)

        self.txt_selected_output = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_output.SetBackgroundColour(self.bg_panel)
        self.txt_selected_output.SetForegroundColour(self.fg_light)
        self.txt_selected_output.SetFont(font_normal)

        output_box.Add(self.btn_select_output, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        output_box.Add(self.txt_selected_output, 1, wx.ALL | wx.EXPAND, 5)
        sizer_paths.Add(output_box, 0, wx.EXPAND | wx.ALL, 5)

        vbox.Add(sizer_paths, 0, wx.EXPAND | wx.ALL, 5)

        # 3. ÇIKARIM (INFERENCE) AYARLARI
        box_settings = wx.StaticBox(self, label="3. Ses Ayarları")
        box_settings.SetForegroundColour(self.fg_light)
        box_settings.SetFont(font_large)
        sizer_settings = wx.StaticBoxSizer(box_settings, wx.VERTICAL)

        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)

        # Pitch
        lbl_pitch = wx.StaticText(self, label="Sesin inceliği / kalınlığı:")
        lbl_pitch.SetFont(font_normal)
        grid.Add(lbl_pitch, 0, wx.ALIGN_CENTER_VERTICAL)
        self.pitch_ctrl = wx.SpinCtrl(self, value="0", min=-24, max=24)
        self.pitch_ctrl.SetFont(font_normal)
        grid.Add(self.pitch_ctrl, 1, wx.EXPAND)

        # F0 Algoritması
        self.advanced_toggle = wx.ToggleButton(self, label="Gelişmiş ses ayarları [KAPALI]")
        self.advanced_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnAdvanced)
        self.advanced_options = wx.Panel(self)
        advanced_layout = wx.BoxSizer(wx.VERTICAL)
        advanced_grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        advanced_grid.AddGrowableCol(1, 1)
        lbl_f0 = wx.StaticText(self.advanced_options, label="Nota algılama yöntemi:")
        lbl_f0.SetFont(font_normal)
        advanced_grid.Add(lbl_f0, 0, wx.ALIGN_CENTER_VERTICAL)
        self.f0_choice = wx.Choice(self.advanced_options, choices=["rmvpe", "crepe"])
        self.f0_choice.SetSelection(0)
        self.f0_choice.Bind(wx.EVT_CHOICE, lambda event: self.preparation.RefreshReadiness())
        self.f0_choice.SetFont(font_normal)
        advanced_grid.Add(self.f0_choice, 1, wx.EXPAND)

        # Index Rate
        lbl_index = wx.StaticText(self.advanced_options, label="Model sesine benzerlik (0–1):")
        lbl_index.SetFont(font_normal)
        advanced_grid.Add(lbl_index, 0, wx.ALIGN_CENTER_VERTICAL)
        self.index_rate_ctrl = wx.TextCtrl(self.advanced_options, value="0.75")
        self.index_rate_ctrl.SetFont(font_normal)
        advanced_grid.Add(self.index_rate_ctrl, 1, wx.EXPAND)

        sizer_settings.Add(grid, 0, wx.EXPAND | wx.ALL, 5)
        sizer_settings.Add(self.advanced_toggle, 0, wx.ALL, 5)
        advanced_layout.Add(wx.StaticText(self.advanced_options, label="Emin değilseniz varsayılan değerleri kullanın."), 0, wx.ALL, 5)
        advanced_layout.Add(advanced_grid, 0, wx.EXPAND | wx.ALL, 5)
        self.quality_controls = {}
        for key, label in (('input_highpass_80hz', '80 Hz altındaki giriş sesini filtrele'),
                           ('pipeline_highpass_48hz', '48 Hz altındaki sesi filtrele'),
                           ('smooth_pitch', 'Nota geçişlerini yumuşat')):
            control = checkbox_control(wx.CheckBox(self.advanced_options, label=label))
            control.SetValue(True)
            self.quality_controls[key] = control
            advanced_layout.Add(control, 0, wx.ALL, 3)
        self.advanced_options.SetSizer(advanced_layout)
        sizer_settings.Add(self.advanced_options, 0, wx.EXPAND | wx.ALL, 5)
        self.advanced_options.Hide()
        vbox.Add(sizer_settings, 0, wx.EXPAND | wx.ALL, 5)

        # 4. İŞLEM BUTONLARI (Başlat / İptal)
        self.preparation = OperationPreparation(self, self.settings, self.RequiredModels)
        vbox.Add(self.preparation, 0, wx.EXPAND | wx.ALL, 8)
        btn_box = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label="Ses değiştirmeyi başlat", size=(-1, 60))
        self.btn_start.SetFont(font_large)
        self.btn_start.SetBackgroundColour(wx.Colour(0, 150, 100))
        self.btn_start.SetForegroundColour(self.fg_light)
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)

        self.btn_cancel = wx.Button(self, label="İptal et", size=(150, 60))
        self.btn_cancel.SetFont(font_large)
        self.btn_cancel.SetBackgroundColour(wx.Colour(200, 50, 50))
        self.btn_cancel.SetForegroundColour(self.fg_light)
        self.btn_cancel.Enable(False)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.btn_force_stop = wx.Button(self, label="Zorla durdur")
        self.btn_force_stop.Enable(False)
        self.btn_force_stop.Bind(wx.EVT_BUTTON, self.OnForceStop)

        btn_box.Add(self.btn_start, 1, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_cancel, 0, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_force_stop, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(btn_box, 0, wx.EXPAND | wx.ALL, 5)

        # 5. LOG VE DURUM GÖSTERGESİ
        self.txt_log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.BORDER_SIMPLE)
        self.txt_log.SetFont(font_normal)
        self.txt_log.SetBackgroundColour(self.bg_panel)
        self.txt_log.SetForegroundColour(self.fg_log)
        vbox.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 5)

        self.txt_status = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_status.SetFont(font_large)
        self.txt_status.SetBackgroundColour(self.bg_main)
        self.txt_status.SetForegroundColour(self.fg_status)
        self.txt_status.SetValue("Hazır. Ses dosyasını ve kullanacağınız modeli seçin.")
        vbox.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 5)

        self.gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 5)
        for control in (self.txt_log, self.txt_status, self.gauge):
            vbox.Detach(control)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)
        vbox.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 8)
        vbox.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 8)
        self.txt_status.MoveAfterInTabOrder(self.gauge)
        self.txt_log.MoveAfterInTabOrder(self.txt_status)

        self.SetSizer(vbox)
        add_intro(self, vbox, "Ses değiştirme", "Bir ses modeli ve kayıt seçin. Program, kaydı seçtiğiniz modelin sesiyle dönüştürür.")
        apply_native_style(self)
        self.FitInside()
        self.pitch_ctrl.SetName("Ses tonu, yarım ses")
        self.f0_choice.SetName("Ses algılama yöntemi")
        self.index_rate_ctrl.SetName("Ses benzerlik oranı, 0 ile 1 arası")
        self.txt_selected_input.SetName("Seçilen ses dosyası")
        self.txt_selected_output.SetName("Çıktı klasörü")
        self.txt_log.SetName("İşlem günlüğü")
        self.txt_status.SetName("İşlem durumu ve yüzde")
        self.gauge.SetName("İşlem ilerlemesi")
        self.LogMessage("Hazır. Başlamak için bir ses dosyası seçin.")

    def OnAdvanced(self, event):
        enabled = self.advanced_toggle.GetValue()
        self.advanced_toggle.SetLabel(f"Gelişmiş ses ayarları [{'AÇIK' if enabled else 'KAPALI'}]")
        self.advanced_options.Show(enabled)
        self.Layout()
        self.FitInside()

    def UpdateModelCheckList(self):
        """Kayıtlı modelleri listeye yansıtır."""
        self.model_list.SetModels(list(self.models.keys()))

    def RequiredModels(self):
        return ['contentvec'] + (['rmvpe'] if self.f0_choice.GetStringSelection() == 'rmvpe' else [])

    def OnAddModel(self, event):
        """Yeni model ekleme penceresi ve veritabanı kaydı."""
        if JOB_LOCK.locked():
            wx.MessageBox("İşlem bitmeden model kayıtları değiştirilemez.", "İşlem sürüyor", wx.OK | wx.ICON_INFORMATION)
            return
        name_dlg = wx.TextEntryDialog(
            self,
            "Model için kolay anlaşılır bir isim girin (Örn: Ahmet Sesi, Ayşe Sesi vb.):",
            "Yeni Ses Modeli Ekle"
        )
        if name_dlg.ShowModal() == wx.ID_OK:
            model_name = name_dlg.GetValue().strip()
            if not model_name:
                wx.MessageBox("Model adı boş olamaz.", "Uyarı", wx.OK | wx.ICON_WARNING)
                name_dlg.Destroy()
                return

            if model_name in self.models:
                wx.MessageBox("Bu isimde bir model zaten var. Farklı bir isim girin.", "Model Adı", wx.OK | wx.ICON_WARNING)
                name_dlg.Destroy()
                return

            pth_dlg = wx.FileDialog(
                self,
                "PTH Dosyasını Seçin",
                wildcard="PTH dosyaları (*.pth)|*.pth|Tüm Dosyalar (*.*)|*.*",
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
            )
            if pth_dlg.ShowModal() == wx.ID_OK:
                pth_path = pth_dlg.GetPath()

                index_dlg = wx.FileDialog(
                    self,
                    "Index Dosyasını Seçin (Opsiyonel, iptal edilebilir)",
                    wildcard="Index dosyaları (*.index)|*.index|Tüm Dosyalar (*.*)|*.*",
                    style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
                )
                index_path = ""
                if index_dlg.ShowModal() == wx.ID_OK:
                    index_path = index_dlg.GetPath()
                index_dlg.Destroy()

                updated = dict(self.models)
                updated[model_name] = {"pth": pth_path, "index": index_path}
                if not save_models(self.app_dir, updated, previous=self.models):
                    pth_dlg.Destroy()
                    name_dlg.Destroy()
                    return
                self.models = load_models(self.app_dir)
                self.UpdateModelCheckList()
                self.LogMessage(f"Yeni model eklendi: {model_name}")
                wx.MessageBox(f"'{model_name}' başarıyla eklendi.", "Bilgi", wx.OK | wx.ICON_INFORMATION)
            pth_dlg.Destroy()
        name_dlg.Destroy()

    def OnDelModel(self, event):
        """Seçili/İşaretli modelleri listeden ve models.json dosyasından siler."""
        if JOB_LOCK.locked():
            wx.MessageBox("İşlem bitmeden model kayıtları değiştirilemez.", "İşlem sürüyor", wx.OK | wx.ICON_INFORMATION)
            return
        selected_names = self.model_list.GetCheckedModels()
        if not selected_names:
            wx.MessageBox("Lütfen silmek istediğiniz model(ler)i listeden basarak [AÇIK] duruma getirin.", "Uyarı", wx.OK | wx.ICON_WARNING)
            return

        confirm = wx.MessageBox(
            f"{len(selected_names)} model kaydını silmek istediğinize emin misiniz?\n\n" + ", ".join(selected_names),
            "Silme Onayı",
            wx.YES_NO | wx.ICON_QUESTION
        )
        if confirm == wx.YES:
            updated = {name: data for name, data in self.models.items() if name not in selected_names}
            if not save_models(self.app_dir, updated, previous=self.models):
                return
            self.models = load_models(self.app_dir)
            self.UpdateModelCheckList()
            self.LogMessage(f"Silinen modeller: {', '.join(selected_names)}")

    def OnSelectInput(self, event):
        """Desteklenen biçimlerdeki kılavuz vokal dosyasını seçtirir."""
        wildcard = "Ses Dosyaları (*.mp3;*.wav;*.flac;*.ogg)|*.mp3;*.wav;*.flac;*.ogg|Tüm Dosyalar (*.*)|*.*"
        dlg = wx.FileDialog(
            self,
            message="Kılavuz Vokal Dosyasını Seçin",
            defaultDir=os.getcwd(),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.input_audio_path = dlg.GetPath()
            self.txt_selected_input.SetValue(self.input_audio_path)
            if not self.output_folder_path:
                self.output_folder_path = os.path.dirname(self.input_audio_path)
                self.txt_selected_output.SetValue(self.output_folder_path)
            self.LogMessage(f"Kılavuz vokal seçildi: {os.path.basename(self.input_audio_path)}")
        dlg.Destroy()

    def OnSelectOutput(self, event):
        """Çıktı klasörünü seçtirir."""
        dlg = wx.DirDialog(self, message="Çıktı klasörünü seçin", defaultPath=os.getcwd())
        if dlg.ShowModal() == wx.ID_OK:
            self.output_folder_path = dlg.GetPath()
            self.txt_selected_output.SetValue(self.output_folder_path)
            self.LogMessage(f"Çıktı klasörü ayarlandı: {self.output_folder_path}")
        dlg.Destroy()

    def LogMessage(self, message):
        """Log ekranına zaman damgalı/satır sonlu metin ekler ve en alta kaydırır."""
        clean_message = message.strip()
        if clean_message:
            append_log(self, clean_message)

    def UpdateStatus(self, text, percent=None):
        """Durum çubuğu metnini ve opsiyonel ilerleme yüzdesini günceller."""
        status_msg = f"Durum: {text}"
        if percent is not None:
            percent = max(0, min(100, int(percent)))
            status_msg += f" - %{percent}"
            post_ui(self, self.gauge.SetValue, percent)
        post_ui(self, self.txt_status.SetValue, status_msg)

    def EnableUI(self, enable):
        """İşlem sürerken veya bittiğinde arayüz butonlarını ve kontrollerini kilitler/açar."""
        post_ui(self, self.btn_add_model.Enable, enable)
        post_ui(self, self.btn_del_model.Enable, enable)
        post_ui(self, self.btn_select_input.Enable, enable)
        post_ui(self, self.btn_select_output.Enable, enable)
        post_ui(self, self.btn_start.Enable, enable)
        post_ui(self, self.btn_cancel.Enable, not enable)
        post_ui(self, self.btn_force_stop.Enable, False)
        for control in self.quality_controls.values():
            post_ui(self, control.Enable, enable)
        post_ui(self, self.model_list.Enable, enable)
        post_ui(self, self.pitch_ctrl.Enable, enable)
        post_ui(self, self.advanced_toggle.Enable, enable)
        post_ui(self, self.f0_choice.Enable, enable)
        post_ui(self, self.index_rate_ctrl.Enable, enable)

    def OnCancel(self, event):
        """Devam eden yapay zeka cover çıkarım kuyruğunu iptal etme bayrağını tetikler."""
        self.is_cancelled = True
        self.UpdateStatus("İptal ediliyor... (Mevcut model işlemi bitince duracak)", 0)
        self.btn_cancel.Enable(False)
        self.btn_force_stop.Enable(True)

    def OnForceStop(self, event):
        self.is_cancelled = True
        if self.audio_session is not None:
            self.audio_session.request_force_stop()
        self.btn_force_stop.Enable(False)
        self.UpdateStatus("Ses motoru durduruluyor...", 0)

    def OnStart(self, event):
        """Seçili modeller ve ayarlar için çıkarım kuyruğunu (threading) başlatır."""
        selected_model_names = self.model_list.GetCheckedModels()
        if not selected_model_names:
            wx.MessageBox("Lütfen işlem yapılacak en az bir modeli listeden basarak [AÇIK] duruma getirin.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        if not self.input_audio_path:
            wx.MessageBox("Lütfen kılavuz vokal dosyasını seçin.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        if not self.output_folder_path:
            wx.MessageBox("Lütfen çıktı klasörünü seçin.", "Hata", wx.OK | wx.ICON_ERROR)
            return

        try:
            index_rate_val = float(self.index_rate_ctrl.GetValue().strip().replace(',', '.'))
        except ValueError:
            index_rate_val = float("nan")
        if not math.isfinite(index_rate_val) or not 0 <= index_rate_val <= 1:
            wx.MessageBox("Ses benzerlik oranı 0 ile 1 arasında bir sayı olmalıdır.", "Hata", wx.OK | wx.ICON_ERROR)
            self.index_rate_ctrl.SetFocus()
            return

        settings = {
            "pitch": int(self.pitch_ctrl.GetValue()),
            "device": "cpu",
            "f0_method": self.f0_choice.GetStringSelection(),
            "index_rate": index_rate_val,
            "quality_policy": {key:control.GetValue() for key,control in self.quality_controls.items()},
            "input_path": self.input_audio_path,
            "output_directory": self.output_folder_path,
            "output_format": selected_output_format(self.settings),
            "output_channels": selected_output_channels(self.settings),
            "models": {name: dict(self.models[name]) for name in selected_model_names}
        }

        if not os.path.isfile(self.input_audio_path) or not os.path.isdir(self.output_folder_path):
            wx.MessageBox("Giriş dosyası veya çıktı klasörü bulunamadı.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        names = [safe_filename(os.path.splitext(os.path.basename(self.input_audio_path))[0]) + "_" + safe_filename(name) + "." + settings['output_format'] for name in selected_model_names]
        if len({name.casefold() for name in names}) != len(names):
            wx.MessageBox("Seçilen model adları aynı çıktı adına dönüşüyor. Model adlarını değiştirin.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        if any(same_path(os.path.join(self.output_folder_path, name), self.input_audio_path) for name in names):
            wx.MessageBox("Çıktı giriş dosyasının üzerine yazamaz.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        try:
            required = ["contentvec"] + (["rmvpe"] if settings["f0_method"] == "rmvpe" else [])
            settings["device"] = self.settings.prepare_job(required)
        except Exception as error:
            wx.MessageBox(str(error), "Donanım ve model kontrolü", wx.OK | wx.ICON_WARNING)
            self.settings.open_settings()
            return
        if not JOB_LOCK.acquire(blocking=False):
            wx.MessageBox("Başka bir ses işlemi çalışıyor. Bitmesini bekleyin.", "İşlem Sürüyor", wx.OK | wx.ICON_INFORMATION)
            return
        try:
            self.txt_log.Clear()
            self.LogMessage(f"Seçilen {len(selected_model_names)} model için toplu çıkarım kuyruğu başlatılıyor...")
            self.LogMessage(f"Ayarlar: Pitch={settings['pitch']}, Cihaz={settings['device']}, F0={settings['f0_method']}, IndexRate={settings['index_rate']}")
            self.EnableUI(False)
            self.is_cancelled = False
            thread = threading.Thread(target=self.run_inference_queue, args=(selected_model_names, settings), daemon=True)
            thread.start()
        except Exception:
            JOB_LOCK.release()
            self.EnableUI(True)
            raise

    def run_inference_queue(self, model_names, settings):
        try:
            self._run_inference_queue(model_names, settings)
        except Exception as error:
            self.LogMessage(f"[HATA] {error}")
            self.UpdateStatus("İşlem Kuyruğu İptal Edildi" if self.is_cancelled else "İşlem başarısız", 0)
            post_ui(self, wx.MessageBox, operation_error(error), "İşlem Hatası", wx.OK | wx.ICON_WARNING)
        finally:
            try:
                if getattr(self, 'audio_session', None) is not None:
                    self.audio_session.close()
                    self.audio_session = None
            except Exception as error:
                self.LogMessage(f"[UYARI] Worker kapatılamadı: {error}")
            finish_job(self)

    def _run_inference_queue(self, model_names, settings):
        """
        VRAM & OOM Korumalı Çıkarım Kuyruğu (Inference Queue):
        Modeller kesinlikle sırayla (tekli iş parçacığı üzerinden) çalıştırılır.
        Her model bitiminde gc.collect() çağrılır.
        """
        factory = getattr(self, 'audio_session_factory', None)
        if factory is not None:
            self.audio_session = factory()
        else:
            from hardware import configure_runtime
            configure_runtime(settings["device"])
        input_path = settings.get("input_path", self.input_audio_path)
        output_directory = settings.get("output_directory", self.output_folder_path)
        models = settings.get("models", self.models)
        # Direct legacy callers retain WAV; the GUI captures the shared preference.
        output_format = normalize_output_format(settings.get('output_format', 'wav'))
        output_channels = normalize_output_channels(settings.get('output_channels', 'original'))
        input_filename = os.path.basename(input_path)
        base_name, ext = os.path.splitext(input_filename)
        total_models = len(model_names)
        succeeded = 0
        failures = []

        prerequisites_ready = False
        for idx, model_name in enumerate(model_names, 1):
            if self.is_cancelled:
                self.LogMessage("[İPTAL] Kullanıcı tarafından işlem kuyruğu durduruldu.")
                break

            percent_start = int(((idx - 1) / total_models) * 100)
            self.UpdateStatus(f"[{idx}/{total_models}] İşleniyor -> {model_name}", percent_start)
            self.LogMessage(f"\n--- [{idx}/{total_models}] MODEL İŞLENİYOR: {model_name} ---")

            output_name = f"{safe_filename(base_name)}_{safe_filename(model_name)}.{output_format}"
            output_path = os.path.join(output_directory, output_name)
            vc = None
            temporary_path = None
            try:
                model_data = models.get(model_name, {})
                pth_path = resolve_model_file_path(self.app_dir, model_data.get("pth", ""))
                index_path = resolve_model_file_path(self.app_dir, model_data.get("index", ""))
                if not os.path.isfile(pth_path):
                    raise FileNotFoundError(f"Model dosyası bulunamadı: {pth_path}. Modeli tekrar ekleyin.")
                if same_path(output_path, input_path) or same_path(output_path, pth_path) or (index_path and same_path(output_path, index_path)):
                    raise ValueError("Çıktı, giriş veya model dosyasının üzerine yazamaz.")
                if index_path and os.path.isfile(index_path):
                    self.LogMessage(f"[BİLGİ] FAISS İndeks Dosyası Aktif: {os.path.basename(index_path)} (İndeks Oranı: {settings['index_rate']})")
                else:
                    if index_path:
                        self.LogMessage(f"[UYARI] İndeks bulunamadı: {index_path}. Dönüşüm indeks olmadan yapılacak.")
                    index_path = ""
                if not prerequisites_ready:
                    ensure_rvc_prerequisites(self.app_dir, self.LogMessage, f0_method=settings["f0_method"], cancelled=lambda: self.is_cancelled)
                    prerequisites_ready = True
                if self.is_cancelled:
                    break
                self.LogMessage(f"RVC Yapay Zeka Motoru Çalıştırılıyor ({model_name})...")
                fd, temporary_path = tempfile.mkstemp(suffix=".wav", dir=output_directory)
                os.close(fd)
                options = dict(
                    audio_input_path=input_path,
                    audio_output_path=temporary_path,
                    model_path=pth_path,
                    index_path=index_path,
                    pitch=settings["pitch"],
                    index_rate=settings["index_rate"],
                    volume_envelope=1.0,
                    protect=0.33,
                    f0_method=settings["f0_method"],
                    split_audio=False,
                    f0_autotune=False,
                    f0_autotune_strength=1.0,
                    proposed_pitch=False,
                    proposed_pitch_threshold=155.0,
                    clean_audio=False,
                    clean_strength=0.7,
                    export_format="WAV",
                    embedder_model="contentvec",
                    post_process=False
                )
                if getattr(self, 'audio_session', None) is not None:
                    self.audio_session.execute('cover', {'device':settings['device'], 'options':options,
                        'quality_policy':settings.get('quality_policy',{})}, cancelled=lambda:self.is_cancelled,
                        progress=lambda text:self.UpdateStatus(f'{model_name}: {text}'))
                else:
                    from rvc.infer.infer import VoiceConverter
                    vc = VoiceConverter(device=settings["device"])
                    vc.allow_model_download = False
                    if 'quality_policy' in settings:
                        from rvc.infer.quality_policy import InferenceQualityPolicy
                        options['quality_policy'] = InferenceQualityPolicy(**settings['quality_policy'])
                    vc.convert_audio(**options)
                if self.is_cancelled:
                    break
                validate_audio_file(temporary_path)
                if self.is_cancelled:
                    break
                output_path = export_audio(temporary_path,output_path,output_format,cancelled=lambda:self.is_cancelled,
                                           output_channels=output_channels)
                succeeded += 1
                self.LogMessage(f"[BAŞARILI] {os.path.basename(output_path)} başarıyla oluşturuldu.")

            except Exception as e:
                self.LogMessage(f"[KRİTİK HATA] {model_name}: {str(e)}")
                failures.append(f'{model_name}: {operation_error(e)}')
            finally:
                # VRAM ve Çöp Toplayıcı Temizliği (OOM Koruması)
                try:
                    if temporary_path and os.path.exists(temporary_path):
                        os.remove(temporary_path)
                except OSError as error:
                    self.LogMessage(f"[UYARI] Geçici dosya silinemedi: {error}")
                try:
                    if vc is not None:
                        vc.cleanup_model()
                except Exception as error:
                    self.LogMessage(f"[UYARI] Model temizliği başarısız: {error}")
                vc = None
                gc.collect()

        if self.is_cancelled:
            self.UpdateStatus("İşlem Kuyruğu İptal Edildi", 0)
            post_ui(self, wx.MessageBox, "AI Cover dönüştürme işlemi iptal edildi.", "İptal", wx.OK | wx.ICON_WARNING)
        else:
            failed = total_models - succeeded
            summary = f"Başarılı: {succeeded}, başarısız: {failed}."
            if failures:
                summary += '\n' + '\n'.join(failures)
            self.UpdateStatus(summary, int(succeeded / total_models * 100) if total_models else 0)
            self.LogMessage(summary)
            post_ui(self, show_result, self, summary, "İşlem Sonucu",
                    wx.OK | (wx.ICON_WARNING if failed else wx.ICON_INFORMATION),
                    output_directory if succeeded else None)

if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None, title="Ghostkiller Sound Cleaner - AI Cover Test Paneli", size=(750, 800))
    panel = CoverPanel(frame)
    frame.Centre()
    frame.Show(True)
    app.MainLoop()
