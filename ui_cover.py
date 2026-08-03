# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - AI Cover Modülü (ui_cover.py)

Bu modül, RVC (Retrieval-based Voice Conversion) yapay zeka cover çıkarım (inference) arayüzü
ve model yönetim sistemini modüler bir wx.Panel (CoverPanel) olarak sağlar.

Özellikler:
1. Erişilebilirlik (A11y): Ses Ayrıştırma (Sound Cleaner) modülüyle birebir aynı şekilde,
   her model için "basılı" / "basılı değil" ve "[AÇIK]" / "[KAPALI]" okumasına sahip
   wx.ToggleButton kullanan ModelToggleList bileşeni barındırır.
2. 'models.json' üzerinden kalıcı model (.pth ve opsiyonel .index) yönetimi (Ekle / Sil).
3. RTX 5060 Ti 16 GB VRAM sınırlarını korumak için tekli kuyruk (queue) threading mimarisi.
   Aynı anda birden fazla model asla çalıştırılmaz, her işlem arası VRAM/GC temizliği yapılır.
4. Pitch (Nota kaydırma), Donanım (cuda/cpu), F0 Algoritması (rmvpe / mangio-crepe) ve
   Index Rate ayarlarının erişilebilir biçimde yapılandırılması.
"""

import wx
import os
import sys
import json
import time
import gc
import threading
import subprocess


def get_app_dir():
    """Uygulamanın çalıştığı kök dizini döndürür."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_models_file_path(app_dir):
    """models.json dosyasının yolunu döndürür."""
    return os.path.join(app_dir, "models.json")


def load_models(app_dir):
    """models.json içinden kayıtlı modelleri yükler."""
    file_path = get_models_file_path(app_dir)
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_models(app_dir, models):
    """modelleri models.json dosyasına kaydeder."""
    file_path = get_models_file_path(app_dir)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(models, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"models.json kaydedilemedi: {e}")


def ensure_rvc_prerequisites(app_dir, log_func=None):
    """
    RVC için gereken temel model dosyalarını (rmvpe.pt ve contentvec/pytorch_model.bin)
    1. Önce programın 'rvc/models' klasöründe kontrol eder.
    2. Sonra sistemdeki olası önbellek/Applio klasörlerinde arar; bulursa kopyalar (internetten tekrar indirmez!).
    3. Hiçbir yerde bulamazsa HuggingFace'ten otomatik indirir.
    """
    import shutil
    import urllib.request

    pred_dir = os.path.join(app_dir, "rvc", "models", "predictors")
    os.makedirs(pred_dir, exist_ok=True)
    rmvpe_target = os.path.join(pred_dir, "rmvpe.pt")

    if not os.path.exists(rmvpe_target):
        possible_sources = [
            "D:\\modeller\\Applio\\rvc\\models\\predictors\\rmvpe.pt",
            os.path.join(os.path.expanduser("~"), ".cache", "audio-separator", "models", "rmvpe.pt"),
            os.path.join(os.path.expanduser("~"), ".cache", "rvc", "models", "predictors", "rmvpe.pt"),
        ]
        found = False
        for src in possible_sources:
            if os.path.exists(src):
                try:
                    shutil.copyfile(src, rmvpe_target)
                    found = True
                    if log_func:
                        log_func(f"[BİLGİ] 'rmvpe.pt' önbellekten kopyalandı (tekrar indirilmedi).")
                    break
                except Exception:
                    pass
        if not found:
            url = "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/rmvpe.pt"
            if log_func:
                log_func("[BİLGİ] 'rmvpe.pt' modeli indiriliyor...")
            try:
                urllib.request.urlretrieve(url, rmvpe_target)
            except Exception as e:
                if log_func:
                    log_func(f"[HATA] rmvpe.pt indirilemedi: {e}")

    embed_dir = os.path.join(app_dir, "rvc", "models", "embedders", "contentvec")
    os.makedirs(embed_dir, exist_ok=True)
    for fn in ["pytorch_model.bin", "config.json"]:
        target = os.path.join(embed_dir, fn)
        if not os.path.exists(target):
            src = os.path.join("D:\\modeller\\Applio\\rvc\\models\\embedders\\contentvec", fn)
            if os.path.exists(src):
                try:
                    shutil.copyfile(src, target)
                except Exception:
                    pass


def resolve_model_file_path(app_dir, file_path):
    """
    Eğer models.json içindeki yol (pth/index) bu bilgisayarda doğrudan mevcut değilse
    (örneğin başka bir arkadaşın bilgisayarı), programın kurulu olduğu yerdeki 'modeller'
    klasöründe bu dosyayı arayarak bulur.
    """
    if not file_path:
        return ""
    if os.path.exists(file_path):
        return file_path
    filename = os.path.basename(file_path)
    p1 = os.path.join(app_dir, "modeller", filename)
    if os.path.exists(p1):
        return p1
    modeller_dir = os.path.join(app_dir, "modeller")
    if os.path.exists(modeller_dir):
        for root, dirs, files in os.walk(modeller_dir):
            if filename in files:
                return os.path.join(root, filename)
    return file_path


class ModelToggleList(wx.ScrolledWindow):
    """
    Sound Cleaner (ui_separator.py) ile birebir aynı A11y / NVDA mantığına sahip
    Model Seçim Listesi Bileşeni.
    Her model için standart bir wx.ToggleButton (Aç/Kapat Düğmesi) oluşturulur.
    Ekran okuyucular (NVDA/JAWS) her öğe için 'basılı' / 'basılı değil' ve
    '[AÇIK]' / '[KAPALI]' durumunu net bir şekilde okur.
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

    def SetModels(self, model_names):
        """Mevcut butonları temizler ve her model için yeni wx.ToggleButton oluşturur."""
        self.sizer.Clear(True)
        self.buttons = []

        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        if not model_names:
            lbl_empty = wx.StaticText(
                self,
                label="Kayıtlı model bulunmamaktadır. 'Yeni Model Ekle' butonu ile ekleyebilirsiniz."
            )
            lbl_empty.SetFont(font_normal)
            lbl_empty.SetForegroundColour(wx.Colour(180, 180, 180))
            self.sizer.Add(lbl_empty, 0, wx.ALL, 10)
        else:
            for i, name in enumerate(model_names):
                btn = wx.ToggleButton(self, label=f"{name} - [KAPALI]", size=(-1, 42))
                btn.SetFont(font_normal)
                btn.SetForegroundColour(self.fg_light)
                btn.SetBackgroundColour(self.bg_btn)
                btn.SetValue(False)
                btn.model_name = name
                btn.Bind(wx.EVT_TOGGLEBUTTON, self.OnToggleModel)
                btn.Bind(wx.EVT_KEY_DOWN, lambda event, idx=i: self.OnKeyDown(event, idx))
                self.buttons.append(btn)
                self.sizer.Add(btn, 0, wx.EXPAND | wx.ALL, 4)

        self.Layout()
        self.FitInside()
        self.Refresh()

    def OnToggleModel(self, event):
        """Bir model düğmesine tıklandığında [AÇIK]/[KAPALI] etiketini ve rengini günceller."""
        btn = event.GetEventObject()
        if btn.GetValue():
            btn.SetLabel(f"{btn.model_name} - [AÇIK]")
            btn.SetBackgroundColour(self.bg_btn_active)
        else:
            btn.SetLabel(f"{btn.model_name} - [KAPALI]")
            btn.SetBackgroundColour(self.bg_btn)
        btn.Refresh()

    def OnKeyDown(self, event, idx):
        """Klavye Yukarı/Aşağı ok tuşları ile model listesi arasında NVDA erişilebilir dolaşımı sağlar."""
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DOWN:
            if idx + 1 < len(self.buttons):
                self.buttons[idx + 1].SetFocus()
        elif keycode == wx.WXK_UP:
            if idx - 1 >= 0:
                self.buttons[idx - 1].SetFocus()
        else:
            event.Skip()

    def GetCheckedModels(self):
        """[AÇIK] / Basılı durumda olan model adlerinin listesini döndürür."""
        return [btn.model_name for btn in self.buttons if btn.GetValue()]


class CoverPanel(wx.Panel):
    """
    AI Cover Sekmesi Paneli (wx.Notebook ile uyumlu)
    """
    def __init__(self, parent):
        """AI Cover paneli değişkenlerini, modellerini ve renk paletini başlatır."""
        super(CoverPanel, self).__init__(parent)

        self.app_dir = get_app_dir()
        self.models = load_models(self.app_dir)

        self.input_audio_path = ""
        self.output_folder_path = ""
        self.is_cancelled = False

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
        wx.SystemOptions.SetOption("msw.window.dark-mode", 1)

        font_large = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.SetBackgroundColour(self.bg_main)
        self.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. MODEL YÖNETİMİ BÖLÜMÜ
        box_models = wx.StaticBox(self, label="1. Vokal Model Kütüphanesi & Çoklu Çıkarım (Batch Inference)")
        box_models.SetForegroundColour(self.fg_light)
        box_models.SetFont(font_large)
        sizer_models = wx.StaticBoxSizer(box_models, wx.VERTICAL)

        btn_model_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add_model = wx.Button(self, label="Stüdyo Vokal Modeli Ekle (.pth & .index)", size=(-1, 40))
        self.btn_add_model.SetFont(font_normal)
        self.btn_add_model.SetBackgroundColour(self.bg_btn)
        self.btn_add_model.SetForegroundColour(self.fg_light)
        self.btn_add_model.Bind(wx.EVT_BUTTON, self.OnAddModel)

        self.btn_del_model = wx.Button(self, label="Seçili Modeli Kütüphaneden Kaldır", size=(-1, 40))
        self.btn_del_model.SetFont(font_normal)
        self.btn_del_model.SetBackgroundColour(wx.Colour(150, 60, 60))
        self.btn_del_model.SetForegroundColour(self.fg_light)
        self.btn_del_model.Bind(wx.EVT_BUTTON, self.OnDelModel)

        btn_model_box.Add(self.btn_add_model, 1, wx.ALL | wx.EXPAND, 5)
        btn_model_box.Add(self.btn_del_model, 0, wx.ALL | wx.EXPAND, 5)
        sizer_models.Add(btn_model_box, 0, wx.EXPAND | wx.ALL, 5)

        lbl_select_info = wx.StaticText(
            self,
            label="Sentezleme Yapılacak Vokal Modellerini Seçin ([AÇIK]/[KAPALI] ve basılı/basılı değil olarak okur):"
        )
        lbl_select_info.SetFont(font_normal)
        sizer_models.Add(lbl_select_info, 0, wx.ALL, 5)

        # A11y (Erişilebilirlik): Sound Cleaner (ui_separator.py) sekmesiyle birebir aynı
        # [AÇIK] / [KAPALI] ve basılı/basılı değil okuma mantığına sahip ModelToggleList.
        self.model_list = ModelToggleList(self)
        self.UpdateModelCheckList()
        sizer_models.Add(self.model_list, 1, wx.EXPAND | wx.ALL, 5)

        vbox.Add(sizer_models, 1, wx.EXPAND | wx.ALL, 5)

        # 2. DOSYA YOLLARI (Girdi ve Çıktı)
        box_paths = wx.StaticBox(self, label="2. Ses Kaynak & Hedef Dizin Ayarları")
        box_paths.SetForegroundColour(self.fg_light)
        box_paths.SetFont(font_large)
        sizer_paths = wx.StaticBoxSizer(box_paths, wx.VERTICAL)

        # Girdi Dosyası (.wav)
        input_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_input = wx.Button(self, label="Kılavuz Vokal Kaynağı Seç (.wav / .flac)", size=(-1, 40))
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
        self.btn_select_output = wx.Button(self, label="Hedef Çıktı Dizini Seç", size=(-1, 40))
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
        box_settings = wx.StaticBox(self, label="3. SOTA Vokal Sentez & DSP Akustik Parametreleri")
        box_settings.SetForegroundColour(self.fg_light)
        box_settings.SetFont(font_large)
        sizer_settings = wx.StaticBoxSizer(box_settings, wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=2, cols=4, vgap=10, hgap=10)
        grid.AddGrowableCol(1, 1)
        grid.AddGrowableCol(3, 1)

        # Pitch
        lbl_pitch = wx.StaticText(self, label="Tonlandırma / Pitch (Yarım Ses):")
        lbl_pitch.SetFont(font_normal)
        grid.Add(lbl_pitch, 0, wx.ALIGN_CENTER_VERTICAL)
        self.pitch_ctrl = wx.SpinCtrl(self, value="0", min=-24, max=24)
        self.pitch_ctrl.SetFont(font_normal)
        grid.Add(self.pitch_ctrl, 1, wx.EXPAND)

        # Donanım
        lbl_device = wx.StaticText(self, label="Sentez Motoru / Donanım (CUDA/CPU):")
        lbl_device.SetFont(font_normal)
        grid.Add(lbl_device, 0, wx.ALIGN_CENTER_VERTICAL)
        self.device_choice = wx.Choice(self, choices=["cuda", "cpu"])
        self.device_choice.SetSelection(0)
        self.device_choice.SetFont(font_normal)
        grid.Add(self.device_choice, 1, wx.EXPAND)

        # F0 Algoritması
        lbl_f0 = wx.StaticText(self, label="F0 Algılayıcı (Pitch Tracker):")
        lbl_f0.SetFont(font_normal)
        grid.Add(lbl_f0, 0, wx.ALIGN_CENTER_VERTICAL)
        self.f0_choice = wx.Choice(self, choices=["rmvpe", "mangio-crepe"])
        self.f0_choice.SetSelection(0)
        self.f0_choice.SetFont(font_normal)
        grid.Add(self.f0_choice, 1, wx.EXPAND)

        # Index Rate
        lbl_index = wx.StaticText(self, label="Tını Harmanlama (FAISS Index Rate):")
        lbl_index.SetFont(font_normal)
        grid.Add(lbl_index, 0, wx.ALIGN_CENTER_VERTICAL)
        self.index_rate_ctrl = wx.TextCtrl(self, value="0.75")
        self.index_rate_ctrl.SetFont(font_normal)
        grid.Add(self.index_rate_ctrl, 1, wx.EXPAND)

        sizer_settings.Add(grid, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(sizer_settings, 0, wx.EXPAND | wx.ALL, 5)

        # 4. İŞLEM BUTONLARI (Başlat / İptal)
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label="SOTA AI Vokal Sentezleme Kuyruğunu Başlat", size=(-1, 60))
        self.btn_start.SetFont(font_large)
        self.btn_start.SetBackgroundColour(wx.Colour(0, 150, 100))
        self.btn_start.SetForegroundColour(self.fg_light)
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)

        self.btn_cancel = wx.Button(self, label="İptal Et", size=(150, 60))
        self.btn_cancel.SetFont(font_large)
        self.btn_cancel.SetBackgroundColour(wx.Colour(200, 50, 50))
        self.btn_cancel.SetForegroundColour(self.fg_light)
        self.btn_cancel.Enable(False)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        btn_box.Add(self.btn_start, 1, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_cancel, 0, wx.EXPAND | wx.ALL, 5)
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
        self.txt_status.SetValue("Durum: Bekliyor...")
        vbox.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 5)

        self.gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(vbox)
        self.LogMessage("Sistem Hazır. İşlem yapmak için dosya seçin.")

    def UpdateModelCheckList(self):
        """Kayıtlı modelleri listeye yansıtır."""
        self.model_list.SetModels(list(self.models.keys()))

    def OnAddModel(self, event):
        """Yeni model ekleme penceresi ve veritabanı kaydı."""
        name_dlg = wx.TextEntryDialog(
            self,
            "Model için açıklayıcı bir stüdyo etiketi girin (Örn: Stüdyo_Vokal_Lead, Erkek_Vokal_48k, Solo_Soprano vb.):",
            "Stüdyo Vokal Modeli Ekle (RVC)"
        )
        if name_dlg.ShowModal() == wx.ID_OK:
            model_name = name_dlg.GetValue().strip()
            if not model_name:
                wx.MessageBox("Model adı boş olamaz.", "Uyarı", wx.OK | wx.ICON_WARNING)
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
                    style=wx.FD_OPEN
                )
                index_path = ""
                if index_dlg.ShowModal() == wx.ID_OK:
                    index_path = index_dlg.GetPath()
                index_dlg.Destroy()

                self.models[model_name] = {"pth": pth_path, "index": index_path}
                save_models(self.app_dir, self.models)
                self.UpdateModelCheckList()
                self.LogMessage(f"Yeni model eklendi: {model_name}")
                wx.MessageBox(f"'{model_name}' başarıyla eklendi.", "Bilgi", wx.OK | wx.ICON_INFORMATION)
            pth_dlg.Destroy()
        name_dlg.Destroy()

    def OnDelModel(self, event):
        """Seçili/İşaretli modelleri listeden ve models.json dosyasından siler."""
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
            for name in selected_names:
                if name in self.models:
                    del self.models[name]
            save_models(self.app_dir, self.models)
            self.UpdateModelCheckList()
            self.LogMessage(f"Silinen modeller: {', '.join(selected_names)}")

    def OnSelectInput(self, event):
        """Kılavuz vokal .wav dosyasını seçtirir."""
        wildcard = "Ses Dosyaları (*.wav;*.flac;*.mp3)|*.wav;*.flac;*.mp3|Tüm Dosyalar (*.*)|*.*"
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
            wx.CallAfter(self.txt_log.AppendText, clean_message + "\n")
            wx.CallAfter(self.txt_log.ShowPosition, self.txt_log.GetLastPosition())

    def UpdateStatus(self, text, percent=None):
        """Durum çubuğu metnini ve opsiyonel ilerleme yüzdesini günceller."""
        status_msg = f"Durum: {text}"
        if percent is not None:
            status_msg += f" - %{percent}"
            wx.CallAfter(self.gauge.SetValue, percent)
        wx.CallAfter(self.txt_status.SetValue, status_msg)

    def EnableUI(self, enable):
        """İşlem sürerken veya bittiğinde arayüz butonlarını ve kontrollerini kilitler/açar."""
        wx.CallAfter(self.btn_add_model.Enable, enable)
        wx.CallAfter(self.btn_del_model.Enable, enable)
        wx.CallAfter(self.btn_select_input.Enable, enable)
        wx.CallAfter(self.btn_select_output.Enable, enable)
        wx.CallAfter(self.btn_start.Enable, enable)
        wx.CallAfter(self.btn_cancel.Enable, not enable)
        wx.CallAfter(self.model_list.Enable, enable)

    def OnCancel(self, event):
        """Devam eden yapay zeka cover çıkarım kuyruğunu iptal etme bayrağını tetikler."""
        self.is_cancelled = True
        self.UpdateStatus("İptal ediliyor... (Mevcut model işlemi bitince duracak)", 0)
        self.btn_cancel.Enable(False)

    def OnStart(self, event):
        """Seçili modeller ve ayarlar için çıkarım kuyruğunu (threading) başlatır."""
        selected_model_names = self.model_list.GetCheckedModels()
        if not selected_model_names:
            wx.MessageBox("Lütfen işlem yapılacak en az bir modeli listeden basarak [AÇIK] duruma getirin.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        if not self.input_audio_path:
            wx.MessageBox("Lütfen kılavuz vokali (.wav) seçin.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        if not self.output_folder_path:
            wx.MessageBox("Lütfen çıktı klasörünü seçin.", "Hata", wx.OK | wx.ICON_ERROR)
            return

        try:
            index_rate_val = float(self.index_rate_ctrl.GetValue().strip())
        except ValueError:
            index_rate_val = 0.75

        settings = {
            "pitch": int(self.pitch_ctrl.GetValue()),
            "device": self.device_choice.GetStringSelection(),
            "f0_method": self.f0_choice.GetStringSelection(),
            "index_rate": index_rate_val
        }

        self.txt_log.Clear()
        self.LogMessage(f"Seçilen {len(selected_model_names)} model için toplu çıkarım kuyruğu başlatılıyor...")
        self.LogMessage(f"Ayarlar: Pitch={settings['pitch']}, Cihaz={settings['device']}, F0={settings['f0_method']}, IndexRate={settings['index_rate']}")

        self.EnableUI(False)
        self.is_cancelled = False

        thread = threading.Thread(
            target=self.run_inference_queue,
            args=(selected_model_names, settings),
            daemon=True
        )
        thread.start()

    def run_inference_queue(self, model_names, settings):
        """
        VRAM & OOM Korumalı Çıkarım Kuyruğu (Inference Queue):
        Modeller kesinlikle sırayla (tekli iş parçacığı üzerinden) çalıştırılır.
        Her model bitiminde gc.collect() çağrılır.
        """
        input_filename = os.path.basename(self.input_audio_path)
        base_name, ext = os.path.splitext(input_filename)
        total_models = len(model_names)

        # Ön koşulları (rmvpe.pt, contentvec) kontrol et/hazırla
        ensure_rvc_prerequisites(self.app_dir, self.LogMessage)

        for idx, model_name in enumerate(model_names, 1):
            if self.is_cancelled:
                self.LogMessage("[İPTAL] Kullanıcı tarafından işlem kuyruğu durduruldu.")
                break

            percent_start = int(((idx - 1) / total_models) * 100)
            self.UpdateStatus(f"[{idx}/{total_models}] İşleniyor -> {model_name}", percent_start)
            self.LogMessage(f"\n--- [{idx}/{total_models}] MODEL İŞLENİYOR: {model_name} ---")

            model_data = self.models.get(model_name, {})
            pth_path = resolve_model_file_path(self.app_dir, model_data.get("pth", ""))
            index_path = resolve_model_file_path(self.app_dir, model_data.get("index", ""))
            output_name = f"{base_name}_{model_name}.wav"
            output_path = os.path.join(self.output_folder_path, output_name)

            if not os.path.exists(pth_path):
                self.LogMessage(f"[HATA] Model dosyası bulunamadı: '{model_name}' ({pth_path}). Lütfen modeli kontrol edin veya listeden tekrar ekleyin.")
                continue

            if index_path and os.path.exists(index_path):
                self.LogMessage(f"[BİLGİ] FAISS İndeks Dosyası Aktif: {os.path.basename(index_path)} (İndeks Oranı: {settings['index_rate']})")
            else:
                self.LogMessage(f"[UYARI] İndeks dosyası bulunamadı ('{index_path}'). Ses dönüşümü indeks olmadan gerçekleştirilecek.")

            try:
                from rvc.infer.infer import VoiceConverter
                self.LogMessage(f"RVC Yapay Zeka Motoru Çalıştırılıyor ({model_name})...")
                vc = VoiceConverter()
                vc.convert_audio(
                    audio_input_path=self.input_audio_path,
                    audio_output_path=output_path,
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
                    proposed_pitch_threshold=0.05,
                    clean_audio=False,
                    clean_strength=0.7,
                    export_format="WAV",
                    embedder_model="contentvec",
                    post_process=False
                )
                if os.path.exists(output_path):
                    self.LogMessage(f"[BAŞARILI] {output_name} başarıyla oluşturuldu.")
                else:
                    self.LogMessage(f"[HATA] {output_name} dosyası oluşturulamadı.")

            except Exception as e:
                self.LogMessage(f"[KRİTİK HATA] {model_name}: {str(e)}")
            finally:
                # VRAM ve Çöp Toplayıcı Temizliği (OOM Koruması)
                gc.collect()

        if self.is_cancelled:
            self.UpdateStatus("İşlem Kuyruğu İptal Edildi", 0)
            wx.CallAfter(wx.MessageBox, "AI Cover dönüştürme işlemi iptal edildi.", "İptal", wx.OK | wx.ICON_WARNING)
        else:
            self.UpdateStatus("Tüm Modeller Başarıyla İşlendi", 100)
            self.LogMessage("\n--- AI COVER TOPLU İŞLEM KUYRUĞU TAMAMLANDI ---")
            wx.CallAfter(wx.MessageBox, "Seçilen tüm modeller için dönüştürme tamamlandı.", "İşlem Bitti", wx.OK | wx.ICON_INFORMATION)

        self.EnableUI(True)


if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None, title="Ghostkiller Sound Cleaner - AI Cover Test Paneli", size=(750, 800))
    panel = CoverPanel(frame)
    frame.Centre()
    frame.Show(True)
    app.MainLoop()
