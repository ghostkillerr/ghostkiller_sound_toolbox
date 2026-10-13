# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - Ses Ayrıştırma Modülü (ui_separator.py)

Bu modül, orijinal 'vocal_chain.py' içindeki VocalChainApp sınıfının ayrıştırma mantığını
ve arayüzünü modüler bir wx.Panel (SeparatorPanel) bileşenine dönüştürür.

Özellikler:
1. Standart wxPython kontrolleriyle ekran okuyucu erişilebilirliğini hedefler; gerçek NVDA/JAWS testi ayrıca gerekir.
2. Modeller uygulama altındaki 'models' klasörüne indirilir; eski önbellekler gerektiğinde kopyalanır.
3. 5 Aşamalı ses temizleme zinciri (Enstrümantal, Ana Vokal Roformer, Arka Vokal Karaoke, DeReverb, DeNoise).
4. Arayüzün donmaması için threading ile iş parçacığı yönetimi ve OOM önlemleri.
"""

import wx
import os
import sys
import re
import gc
import tempfile
import threading
import importlib.util
from app_runtime import (JOB_LOCK, post_ui, append_log, model_directory, copy_model,
                         same_path, validate_audio_file, finish_job, output_filename)

from separation_steps import SEPARATION_STEPS

def separator_factory(**kwargs):
    # The GUI can open even if a native motor DLL cannot be imported.
    from separator_backend import LocalSeparator
    return LocalSeparator(**kwargs)


if (('separator_backend' in sys.modules and sys.modules['separator_backend'] is None)
        or importlib.util.find_spec('audio_separator') is None):
    Separator = None
else:
    Separator = separator_factory


def get_app_dir():
    """Uygulamanın çalıştığı kök dizini döndürür."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_ffmpeg_paths(app_dir):
    """ffmpeg ve ffprobe yollarını ayarlar."""
    tools_dir = os.path.join(app_dir, "tools", "ffmpeg")
    os.environ["PATH"] = app_dir + os.pathsep + tools_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        import pydub
        ffmpeg_path = os.path.join(app_dir, "ffmpeg.exe")
        ffprobe_path = os.path.join(app_dir, "ffprobe.exe")
        if os.path.exists(ffmpeg_path):
            pydub.AudioSegment.converter = ffmpeg_path
        if os.path.exists(ffprobe_path):
            pydub.utils.get_prober_name = lambda: ffprobe_path
    except Exception:
        pass


def model_cache_directories(app_dir):
    user_home = os.path.expanduser("~")
    return [
        os.path.join(app_dir, "modeller"),
        os.path.join(os.environ.get('LOCALAPPDATA', user_home), 'GhostkillerSoundToolbox', 'modeller'),
        os.path.join(user_home, ".cache", "audio-separator", "models"),
        os.path.join(user_home, ".cache", "audio-separator"),
        os.path.join(user_home, "AppData", "Local", "audio-separator", "models"),
        os.path.join(user_home, "AppData", "Local", "audio-separator"),
        os.path.join(os.environ.get("TEMP", ""), "audio-separator-models"),
    ]

def get_model_directory(app_dir):
    return model_directory(app_dir)


def prepare_separator_model(app_dir, model_dir, model_name):
    os.makedirs(model_dir, exist_ok=True)
    target = os.path.join(model_dir, model_name)
    if os.path.isfile(target) and os.path.getsize(target):
        return
    for directory in model_cache_directories(app_dir):
        source = os.path.join(directory, model_name)
        if os.path.isfile(source) and os.path.getsize(source) and not same_path(source, target):
            # Metadata maps model hashes and their YAML configs to the right architecture.
            for filename in os.listdir(directory):
                if filename.endswith(('.json', '.yaml')):
                    metadata = os.path.join(directory, filename)
                    destination = os.path.join(model_dir, filename)
                    if os.path.isfile(metadata) and os.path.getsize(metadata) and (not os.path.isfile(destination) or not os.path.getsize(destination)):
                        copy_model(metadata, destination)
            copy_model(source, target)
            return


class SeparatorPanel(wx.ScrolledWindow):
    """
    Ses Ayrıştırma Sekmesi Paneli (wx.Notebook ile uyumlu)
    """
    def __init__(self, parent, settings=None):
        """Ses Ayrıştırma paneli yollarını, renk paletini ve durumlarını başlatır."""
        super(SeparatorPanel, self).__init__(parent)
        self.SetScrollRate(0,20)
        from app_settings import AppSettings
        self.settings = settings or AppSettings()

        self.app_dir = get_app_dir()
        setup_ffmpeg_paths(self.app_dir)
        self.model_dir = get_model_directory(self.app_dir)

        self.current_input_file = ""
        self.output_directory = ""
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
        """Ayrıştırma paneli butonlarını, kanal toggle düğmelerini ve log ekranını oluşturur."""
        wx.SystemOptions.SetOption("msw.window.dark-mode", 1)

        font_large = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.SetBackgroundColour(self.bg_main)
        self.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Ses Dosyası Seçimi
        file_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_file = wx.Button(self, label="1. Şarkı veya Ses Dosyası Seç (.mp3 / .wav / .flac)", size=(-1, 45))
        self.btn_select_file.SetFont(font_large)
        self.btn_select_file.SetBackgroundColour(self.bg_btn)
        self.btn_select_file.SetForegroundColour(self.fg_light)
        self.btn_select_file.Bind(wx.EVT_BUTTON, self.OnFileSelect)

        self.txt_selected_file = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_file.SetBackgroundColour(self.bg_panel)
        self.txt_selected_file.SetForegroundColour(self.fg_light)
        self.txt_selected_file.SetFont(font_normal)

        file_box.Add(self.btn_select_file, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        file_box.Add(self.txt_selected_file, 1, wx.ALL | wx.EXPAND, 5)
        vbox.Add(file_box, 0, wx.EXPAND | wx.ALL, 5)

        # 2. Çıktı Klasörü Seçimi
        dir_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_dir = wx.Button(self, label="2. Kaydedilecek Klasörü Seç", size=(-1, 45))
        self.btn_select_dir.SetFont(font_large)
        self.btn_select_dir.SetBackgroundColour(self.bg_btn)
        self.btn_select_dir.SetForegroundColour(self.fg_light)
        self.btn_select_dir.Bind(wx.EVT_BUTTON, self.OnDirSelect)

        self.txt_selected_dir = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_dir.SetBackgroundColour(self.bg_panel)
        self.txt_selected_dir.SetForegroundColour(self.fg_light)
        self.txt_selected_dir.SetFont(font_normal)

        dir_box.Add(self.btn_select_dir, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        dir_box.Add(self.txt_selected_dir, 1, wx.ALL | wx.EXPAND, 5)
        vbox.Add(dir_box, 0, wx.EXPAND | wx.ALL, 5)

        # 3. İşlem Seçenekleri (Kanallar)
        box_options = wx.StaticBox(self, label="3. Yapılacak Temizleme İşlemleri")
        box_options.SetForegroundColour(self.fg_light)
        box_options.SetFont(font_large)
        sizer_options = wx.StaticBoxSizer(box_options, wx.VERTICAL)

        def CreateToggleBtn(label, is_active=False):
            """NVDA uyumlu [AÇIK]/[KAPALI] durumunu barındıran wx.ToggleButton üretir."""
            state_text = "[AÇIK]" if is_active else "[KAPALI]"
            btn = wx.ToggleButton(self, label=f"{label} - {state_text}", size=(-1, 40))
            btn.SetFont(font_normal)
            btn.SetForegroundColour(self.fg_light)
            btn.SetValue(is_active)
            btn.SetBackgroundColour(self.bg_btn_active if is_active else self.bg_btn)
            btn.Bind(wx.EVT_TOGGLEBUTTON, self.OnCheckToggle)
            return btn

        self.chk_inst = CreateToggleBtn("1. Müziği Ayır (Sadece Enstrümantal Müzik Kalsın)", False)
        sizer_options.Add(self.chk_inst, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step1 = CreateToggleBtn("2. İnsan Sesini Ayır (Sadece Vokal Kalsın)", True)
        sizer_options.Add(self.chk_step1, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step2 = CreateToggleBtn("3. Arka Vokalleri ve Harmoni Seslerini Temizle", False)
        sizer_options.Add(self.chk_step2, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step3 = CreateToggleBtn("4. Yankıyı ve Eko Seslerini Temizle", False)
        sizer_options.Add(self.chk_step3, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step4 = CreateToggleBtn("5. Arka Plan Gürültüsünü ve Hışırtıyı Temizle", False)
        sizer_options.Add(self.chk_step4, 0, wx.EXPAND | wx.ALL, 5)

        vbox.Add(sizer_options, 0, wx.EXPAND | wx.ALL, 5)

        # 4. İşlem Butonları (Başlat / İptal)
        btn_box = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_start = wx.Button(self, label="Temizleme İşlemini Başlat", size=(-1, 60))
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
        self.btn_force_stop = wx.Button(self, label="Zorla Durdur")
        self.btn_force_stop.Enable(False)
        self.btn_force_stop.Bind(wx.EVT_BUTTON, self.OnForceStop)

        btn_box.Add(self.btn_start, 1, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_cancel, 0, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_force_stop, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(btn_box, 0, wx.EXPAND | wx.ALL, 5)

        # 5. Log ve Durum Göstergesi
        self.txt_log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.BORDER_SIMPLE)
        self.txt_log.SetFont(font_normal)
        self.txt_log.SetBackgroundColour(self.bg_panel)
        self.txt_log.SetForegroundColour(self.fg_log)
        vbox.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 5)

        self.txt_status = wx.TextCtrl(self, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_status.SetFont(font_large)
        self.txt_status.SetBackgroundColour(self.bg_main)
        self.txt_status.SetForegroundColour(self.fg_status)
        self.txt_status.SetValue("Durum: Bekliyor (Yüzde takibi için burayı okutun)")
        vbox.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 5)

        self.gauge = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(vbox)
        self.FitInside()
        self.txt_selected_file.SetName("Seçilen ses dosyası")
        self.txt_selected_dir.SetName("Çıktı klasörü")
        self.txt_log.SetName("İşlem günlüğü")
        self.txt_status.SetName("İşlem durumu ve yüzde")
        self.gauge.SetName("İşlem ilerlemesi")
        self.LogMessage("Sistem Hazır. İşlem yapmak için dosya seçin.")

    def OnCheckToggle(self, event):
        """Kanal seçim düğmesi basıldığında [AÇIK]/[KAPALI] durum ve rengini NVDA uyumlu günceller."""
        btn = event.GetEventObject()
        base_label = btn.GetLabel().split(" - ")[0]

        if btn.GetValue():
            btn.SetLabel(f"{base_label} - [AÇIK]")
            btn.SetBackgroundColour(self.bg_btn_active)
        else:
            btn.SetLabel(f"{base_label} - [KAPALI]")
            btn.SetBackgroundColour(self.bg_btn)

        btn.Refresh()

    def OnFileSelect(self, event):
        """İşlenecek ses dosyasını (.wav, .flac, .mp3) seçtirir."""
        wildcard = "Ses Dosyaları (*.wav;*.flac;*.mp3)|*.wav;*.flac;*.mp3|Tüm Dosyalar (*.*)|*.*"
        dlg = wx.FileDialog(self, message="İşlenecek ses dosyasını seçin",
                            defaultDir=os.getcwd(), wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

        if dlg.ShowModal() == wx.ID_OK:
            self.current_input_file = dlg.GetPath()
            self.txt_selected_file.SetValue(self.current_input_file)

            if not self.output_directory:
                self.output_directory = os.path.dirname(self.current_input_file)
                self.txt_selected_dir.SetValue(self.output_directory)

            self.LogMessage(f"Dosya seçildi: {os.path.basename(self.current_input_file)}")
        dlg.Destroy()

    def OnDirSelect(self, event):
        """Çıktı klasörünü seçtirir."""
        dlg = wx.DirDialog(self, message="Çıktı klasörünü seçin", defaultPath=os.getcwd())
        if dlg.ShowModal() == wx.ID_OK:
            self.output_directory = dlg.GetPath()
            self.txt_selected_dir.SetValue(self.output_directory)
            self.LogMessage(f"Çıktı klasörü ayarlandı: {self.output_directory}")
        dlg.Destroy()

    def LogMessage(self, message):
        """Log ekranına yeni satır eklendiğinde ekrana basar ve en alta kaydırır."""
        clean_message = message.strip()
        if clean_message:
            append_log(self, clean_message)

    def UpdateStatus(self, text, percent=None):
        """Durum göstergesini ve ilerleme çubuğunu (gauge) günceller."""
        status_msg = f"Durum: {text}"
        if percent is not None:
            percent = max(0, min(100, int(percent)))
            status_msg += f" - %{percent}"
            post_ui(self, self.gauge.SetValue, percent)
        post_ui(self, self.txt_status.SetValue, status_msg)

    def EnableUI(self, enable):
        """İşlem sürerken veya bittiğinde arayüz kontrollerini aktif/pasif yapar."""
        post_ui(self, self.btn_select_file.Enable, enable)
        post_ui(self, self.btn_select_dir.Enable, enable)
        post_ui(self, self.btn_start.Enable, enable)
        post_ui(self, self.btn_cancel.Enable, not enable)
        post_ui(self, self.btn_force_stop.Enable, False)
        post_ui(self, self.chk_inst.Enable, enable)
        post_ui(self, self.chk_step1.Enable, enable)
        post_ui(self, self.chk_step2.Enable, enable)
        post_ui(self, self.chk_step3.Enable, enable)
        post_ui(self, self.chk_step4.Enable, enable)

    def OnCancel(self, event):
        """Devam eden ayrıştırma zincirini iptal etme bayrağını tetikler."""
        self.is_cancelled = True
        self.UpdateStatus("İptal ediliyor... (Mevcut işlem bitince duracak)", 0)
        self.btn_cancel.Enable(False)
        self.btn_force_stop.Enable(True)

    def OnForceStop(self, event):
        self.is_cancelled = True
        if self.audio_session is not None:
            self.audio_session.request_force_stop()
        self.btn_force_stop.Enable(False)
        self.UpdateStatus("Ses motoru durduruluyor...", 0)

    def RunSeparatorCommand(self, input_file, model_name, step_name, output_dir):
        """Belirtilen model ile tekli ses ayırma adımını çalıştırır ve VRAM/GC temizliği yapar."""
        if getattr(self, 'audio_session', None) is not None:
            return self.audio_session.execute('separate', {
                'input_file':input_file,'model_name':model_name,'output_dir':output_dir,
                'model_dir':self.model_dir,'device':self.job_device},
                cancelled=lambda:self.is_cancelled, progress=lambda text:self.UpdateStatus(f'{step_name}: {text}'))
        if Separator is None:
            self.LogMessage("HATA: audio-separator kütüphanesi yüklü değil veya bulunamadı!")
            return False

        self.UpdateStatus(f"{step_name} başlatılıyor...", 0)
        self.LogMessage(f"--- İŞLEM: {step_name} ---")

        separator = None
        old_stderr = sys.stderr
        try:
            class StderrCatcher:
                """tqdm ilerleme loglarını yakalar ve GUI yüzdesine (gauge) çevirir."""
                def __init__(self, panel_instance, step_name):
                    self.panel = panel_instance
                    self.step_name = step_name
                    self.current_phase = "Model Hazırlanıyor"

                def write(self, text):
                    """Standart hata akışına yazılan çıktıda yüzde arar ve panel durumunu yeniler."""
                    if self.panel.is_cancelled:
                        return len(text)
                    clean_line = text.strip()
                    if clean_line:
                        match = re.search(r'(\d+)%', clean_line)
                        if match:
                            percent = int(match.group(1))
                            self.panel.UpdateStatus(f"{self.current_phase} ({self.step_name})", percent)
                        elif "Error" in clean_line or "Exception" in clean_line:
                            self.panel.LogMessage(f"HATA: {clean_line}")
                    return len(text)

                def flush(self):
                    """Akışı temizler (boş metod)."""
                    pass

                def isatty(self):
                    return False

                encoding = 'utf-8'

            catcher = StderrCatcher(self, step_name)
            sys.stderr = catcher

            if self.is_cancelled:
                return False
            separator = Separator(
                output_dir=output_dir,
                output_format="FLAC",
                model_file_dir=self.model_dir,
                device=getattr(self, "job_device", "cpu"),
                use_autocast=False,
            )

            # Missing downloads are prohibited during inference by LocalSeparator.
            catcher.current_phase = "Model Hazırlanıyor"
            separator.load_model(model_filename=model_name)

            if self.is_cancelled:
                return False

            # Ses işleme aşaması
            catcher.current_phase = "Ses İşleniyor"
            self.UpdateStatus(f"Ses İşleniyor ({step_name})...", 0)
            outputs = separator.separate(input_file)
            if not isinstance(outputs, (list, tuple)) or not outputs:
                raise RuntimeError("Ayrıştırma motoru çıktı dosyası döndürmedi.")
            paths = []
            for output in outputs:
                path = os.path.realpath(output if os.path.isabs(output) else os.path.join(output_dir, output))
                root = os.path.realpath(output_dir)
                if os.path.normcase(os.path.commonpath([root, path])) != os.path.normcase(root) or not os.path.isfile(path):
                    raise RuntimeError("Geçersiz ayrıştırma çıktısı.")
                paths.append(path)
            return paths

        except (Exception, SystemExit) as e:
            self.LogMessage(f"SİSTEM HATASI: {type(e).__name__}: {str(e) or 'Motor beklenmeden sonlandı.'}")
            return False
        finally:
            try:
                sys.stderr = old_stderr
            except Exception:
                pass
            try:
                if separator is not None:
                    del separator
            except Exception:
                pass
            gc.collect()

    def ProcessChain(self, selected_steps, input_file=None, output_directory=None, device="cpu"):
        completed = 0
        failed = False
        self.job_device = device
        input_file = input_file or self.current_input_file
        output_directory = output_directory or self.output_directory
        working_file = input_file
        base_name = os.path.splitext(os.path.basename(working_file))[0]
        steps = SEPARATION_STEPS
        try:
            factory = getattr(self, 'audio_session_factory', None)
            if factory is not None:
                self.audio_session = factory()
            else:
                from hardware import configure_runtime
                configure_runtime(device)
            for idx, (model, label, keyword, suffix) in enumerate(steps):
                if not selected_steps[idx]:
                    continue
                if self.is_cancelled:
                    break
                # Only files owned by this job can be removed by TemporaryDirectory.
                with tempfile.TemporaryDirectory(prefix="ghostkiller_", dir=output_directory) as stage:
                    source = input_file if idx == 0 else working_file
                    outputs = self.RunSeparatorCommand(source, model, label, stage)
                    if self.is_cancelled:
                        break
                    if not outputs:
                        raise RuntimeError(f"{label} başarısız oldu.")
                    # The input basename can itself contain a stem label such as '(Vocals)'.
                    matches = [path for path in outputs if re.findall(r'_\([^()]*\)', os.path.basename(path))[-1:] == ['_' + keyword]]
                    if len(matches) != 1:
                        raise RuntimeError(f"{label}: beklenen çıktı bulunamadı veya belirsiz.")
                    destination = os.path.join(output_directory, output_filename(base_name,suffix))
                    if same_path(destination, input_file):
                        raise RuntimeError("Çıktı giriş dosyasının üzerine yazamaz.")
                    validate_audio_file(matches[0])
                    if self.is_cancelled:
                        break
                    os.replace(matches[0], destination)
                    completed += 1
                    self.LogMessage(f"Oluşturuldu: {os.path.basename(destination)}")
                    if idx != 0:
                        working_file = destination
        except Exception as error:
            failed = True
            self.LogMessage(f"HATA: {error}")
        finally:
            try:
                if getattr(self, 'audio_session', None) is not None:
                    try:
                        self.audio_session.close()
                    except Exception as error:
                        self.LogMessage(f'Worker kapatılamadı: {error}')
                    finally:
                        self.audio_session = None
                if self.is_cancelled:
                    summary = f"İşlem iptal edildi. Tamamlanan adım: {completed}."
                elif failed:
                    summary = f"İşlem başarısız. Tamamlanan adım: {completed}. Ayrıntılar günlükte."
                else:
                    summary = f"Seçilen {completed} işlem başarıyla tamamlandı."
                self.UpdateStatus(summary, 0 if failed or self.is_cancelled else 100)
                post_ui(self, wx.MessageBox, summary, "İşlem Sonucu", wx.OK | (wx.ICON_WARNING if failed or self.is_cancelled else wx.ICON_INFORMATION))
            finally:
                finish_job(self)

    def OnStart(self, event):
        """Ayrıştırma işlemini arka plan iş parçacığı (threading) olarak başlatır."""
        if not self.current_input_file:
            wx.MessageBox("Lütfen önce bir ses dosyası seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return
        if not self.output_directory:
            wx.MessageBox("Lütfen bir çıktı klasörü seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return

        selected_steps = tuple(control.GetValue() for control in
                               (self.chk_inst, self.chk_step1, self.chk_step2, self.chk_step3, self.chk_step4))
        if not any(selected_steps):
            wx.MessageBox("En az bir temizleme işlemi seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return
        if not os.path.isfile(self.current_input_file) or not os.path.isdir(self.output_directory):
            wx.MessageBox("Giriş dosyası veya çıktı klasörü bulunamadı.", "Hata", wx.OK | wx.ICON_ERROR)
            return
        try:
            required = [step[0] for enabled, step in zip(selected_steps, SEPARATION_STEPS) if enabled]
            device = self.settings.prepare_job(required)
        except Exception as error:
            wx.MessageBox(str(error), "Donanım ve model kontrolü", wx.OK | wx.ICON_WARNING)
            self.settings.open_settings()
            return
        if not JOB_LOCK.acquire(blocking=False):
            wx.MessageBox("Başka bir ses işlemi çalışıyor. Bitmesini bekleyin.", "İşlem Sürüyor", wx.OK | wx.ICON_INFORMATION)
            return
        try:
            self.is_cancelled = False
            self.EnableUI(False)
            self.txt_log.Clear()
            self.LogMessage(f"İşlemler başlıyor. Kullanılacak cihaz: {device}. Modeller yerel klasörden yüklenecek.")
            thread = threading.Thread(target=self.ProcessChain, args=(selected_steps, self.current_input_file, self.output_directory, device), daemon=True)
            thread.start()
        except Exception:
            JOB_LOCK.release()
            self.EnableUI(True)
            raise


if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None, title="Ghostkiller Sound Cleaner - Ses Ayrıştırma Test Paneli", size=(750, 800))
    panel = SeparatorPanel(frame)
    frame.Centre()
    frame.Show(True)
    app.MainLoop()
