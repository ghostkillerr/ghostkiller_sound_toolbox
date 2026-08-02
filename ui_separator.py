# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - Ses Ayrıştırma Modülü (ui_separator.py)

Bu modül, orijinal 'vocal_chain.py' içindeki VocalChainApp sınıfının ayrıştırma mantığını
ve arayüzünü modüler bir wx.Panel (SeparatorPanel) bileşenine dönüştürür.

Özellikler:
1. Standart wxPython bileşenleri ile tam NVDA/JAWS ekran okuyucu uyumluluğu (Erişilebilirlik - A11y).
2. Akıllı Model Kontrolcüsü: Önce işletim sistemi varsayılan model dizinlerine bakar; model varsa orayı kullanır,
   yoksa taşınabilir (portable) 'modeller' klasörünü oluşturur.
3. 5 Aşamalı ses temizleme zinciri (Enstrümantal, Ana Vokal Roformer, Arka Vokal Karaoke, DeReverb, DeNoise).
4. Arayüzün donmaması için threading ile iş parçacığı yönetimi ve OOM önlemleri.
"""

import wx
import os
import sys
import re
import gc
import traceback
import threading

try:
    from audio_separator.separator import Separator
except ImportError:
    Separator = None


def get_app_dir():
    """Uygulamanın çalıştığı kök dizini döndürür."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def setup_ffmpeg_paths(app_dir):
    """ffmpeg ve ffprobe yollarını ayarlar."""
    os.environ["PATH"] = app_dir + os.pathsep + os.environ.get("PATH", "")
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


def get_model_directory(app_dir):
    """
    Akıllı Model Kontrolcüsü (Smart Model Controller):
    1. Önce programın kurulu olduğu yerdeki 'modeller' klasöründe model var mı kontrol eder.
    2. Sonra işletim sistemindeki varsayılan önbellek/model dizinlerine bakar (.cache/audio-separator vb.).
       Eğer önceden indirilmiş modeller varsa tekrar indirmesin ki diskte yer kaplamasın.
    3. Hiçbir yerde model bulunamazsa, programın kurulu olduğu yerdeki 'modeller' klasörünü döndürür
       (modeller otomatik olarak buraya indirilir).
    """
    portable_dir = os.path.join(app_dir, "modeller")
    if os.path.exists(portable_dir) and os.path.isdir(portable_dir):
        try:
            files = os.listdir(portable_dir)
            if any(f.endswith((".ckpt", ".pth", ".onnx", ".yaml")) for f in files):
                return portable_dir
        except Exception:
            pass

    user_home = os.path.expanduser("~")
    possible_default_dirs = [
        os.path.join(user_home, ".cache", "audio-separator", "models"),
        os.path.join(user_home, ".cache", "audio-separator"),
        os.path.join(user_home, "AppData", "Local", "audio-separator", "models"),
        os.path.join(user_home, "AppData", "Local", "audio-separator"),
        os.path.join(os.environ.get("TEMP", ""), "audio-separator-models"),
    ]

    for d in possible_default_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            try:
                files = os.listdir(d)
                if any(f.endswith((".ckpt", ".pth", ".onnx", ".yaml")) for f in files):
                    return d
            except Exception:
                pass

    os.makedirs(portable_dir, exist_ok=True)
    return portable_dir


class SeparatorPanel(wx.Panel):
    """
    Ses Ayrıştırma Sekmesi Paneli (wx.Notebook ile uyumlu)
    """
    def __init__(self, parent):
        """Ses Ayrıştırma paneli yollarını, renk paletini ve durumlarını başlatır."""
        super(SeparatorPanel, self).__init__(parent)

        self.app_dir = get_app_dir()
        setup_ffmpeg_paths(self.app_dir)
        self.model_dir = get_model_directory(self.app_dir)

        self.current_input_file = ""
        self.output_directory = ""
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
        """Ayrıştırma paneli butonlarını, kanal toggle düğmelerini ve log ekranını oluşturur."""
        wx.SystemOptions.SetOption("msw.window.dark-mode", 1)

        font_large = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        self.SetBackgroundColour(self.bg_main)
        self.SetForegroundColour(self.fg_light)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Ses Dosyası Seçimi
        file_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_file = wx.Button(self, label="1. Ses Dosyası Seç", size=(-1, 45))
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
        self.btn_select_dir = wx.Button(self, label="2. Çıktı Klasörü Seç", size=(-1, 45))
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
        box_options = wx.StaticBox(self, label="3. Çıkarılacak Kanallar ve İşlemler")
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

        self.chk_inst = CreateToggleBtn("Kusursuz Enstrümantal Çıkar (MelBand Kim Inst)", False)
        sizer_options.Add(self.chk_inst, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step1 = CreateToggleBtn("Ana Vokali Ayır (Roformer)", True)
        sizer_options.Add(self.chk_step1, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step2 = CreateToggleBtn("Arka Vokalleri Temizle (Mel Band Karaoke)", False)
        sizer_options.Add(self.chk_step2, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step3 = CreateToggleBtn("Yankıyı Gider (DeReverb)", False)
        sizer_options.Add(self.chk_step3, 0, wx.EXPAND | wx.ALL, 5)

        self.chk_step4 = CreateToggleBtn("Gürültü Gider (DeNoise)", False)
        sizer_options.Add(self.chk_step4, 0, wx.EXPAND | wx.ALL, 5)

        vbox.Add(sizer_options, 0, wx.EXPAND | wx.ALL, 5)

        # 4. İşlem Butonları (Başlat / İptal)
        btn_box = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_start = wx.Button(self, label="Ghostkiller İşlemlerini Başlat", size=(-1, 60))
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
            wx.CallAfter(self.txt_log.AppendText, clean_message + "\n")
            wx.CallAfter(self.txt_log.ShowPosition, self.txt_log.GetLastPosition())

    def UpdateStatus(self, text, percent=None):
        """Durum göstergesini ve ilerleme çubuğunu (gauge) günceller."""
        status_msg = f"Durum: {text}"
        if percent is not None:
            status_msg += f" - %{percent}"
            wx.CallAfter(self.gauge.SetValue, percent)
        wx.CallAfter(self.txt_status.SetValue, status_msg)

    def EnableUI(self, enable):
        """İşlem sürerken veya bittiğinde arayüz kontrollerini aktif/pasif yapar."""
        wx.CallAfter(self.btn_select_file.Enable, enable)
        wx.CallAfter(self.btn_select_dir.Enable, enable)
        wx.CallAfter(self.btn_start.Enable, enable)
        wx.CallAfter(self.btn_cancel.Enable, not enable)
        wx.CallAfter(self.chk_inst.Enable, enable)
        wx.CallAfter(self.chk_step1.Enable, enable)
        wx.CallAfter(self.chk_step2.Enable, enable)
        wx.CallAfter(self.chk_step3.Enable, enable)
        wx.CallAfter(self.chk_step4.Enable, enable)

    def GetNewFiles(self, directory, files_before):
        """Klasörde işlem öncesine göre yeni oluşturulmuş dosyaların listesini döndürür."""
        files_after = set(os.listdir(directory))
        return list(files_after - files_before)

    def RenameAndKeep(self, original_path, new_filename):
        """Çıktı dosyasını tutarlı biçimde yeniden adlandırır ve mevcutsa üzerine yazar."""
        final_path = os.path.join(self.output_directory, new_filename)
        try:
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(original_path, final_path)
            self.LogMessage(f"Oluşturuldu: {new_filename}")
            return final_path
        except Exception as e:
            self.LogMessage(f"HATA (İsimlendirme): {str(e)}")
            return original_path

    def OnCancel(self, event):
        """Devam eden ayrıştırma zincirini iptal etme bayrağını tetikler."""
        self.is_cancelled = True
        self.UpdateStatus("İptal ediliyor... (Mevcut işlem bitince duracak)", 0)
        self.btn_cancel.Enable(False)

    def RunSeparatorCommand(self, input_file, model_name, step_name):
        """Belirtilen model ile tekli ses ayırma adımını çalıştırır ve VRAM/GC temizliği yapar."""
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
                    self.current_phase = "Model İndiriliyor/Hazırlanıyor"

                def write(self, text):
                    """Standart hata akışına yazılan çıktıda yüzde arar ve panel durumunu yeniler."""
                    if self.panel.is_cancelled:
                        return
                    clean_line = text.strip()
                    if clean_line:
                        match = re.search(r'(\d+)%', clean_line)
                        if match:
                            percent = int(match.group(1))
                            self.panel.UpdateStatus(f"{self.current_phase} ({self.step_name})", percent)
                        elif "Error" in clean_line or "Exception" in clean_line:
                            self.panel.LogMessage(f"HATA: {clean_line}")

                def flush(self):
                    """Akışı temizler (boş metod)."""
                    pass

            catcher = StderrCatcher(self, step_name)
            sys.stderr = catcher

            # Akıllı model kontrolcüsünün belirlediği dizini kullan
            separator = Separator(
                output_dir=self.output_directory,
                output_format="FLAC",
                model_file_dir=self.model_dir
            )

            # Model indirme/yükleme aşaması
            catcher.current_phase = "Model İndiriliyor/Hazırlanıyor"
            separator.load_model(model_filename=model_name)

            if self.is_cancelled:
                return False

            # Ses işleme aşaması
            catcher.current_phase = "Ses İşleniyor"
            self.UpdateStatus(f"Ses İşleniyor ({step_name})...", 0)
            separator.separate(input_file)
            return True

        except Exception as e:
            self.LogMessage(f"SİSTEM HATASI: {str(e)}")
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

    def ProcessChain(self):
        """Seçilen kanallar için sırasıyla ses ayrıştırma adımlarını tekli iş parçacığında çalıştırır."""
        self.EnableUI(False)
        self.is_cancelled = False
        working_file = self.current_input_file
        base_filename = os.path.splitext(os.path.basename(self.current_input_file))[0]

        if self.chk_inst.GetValue() and not self.is_cancelled:
            files_before = set(os.listdir(self.output_directory))
            success = self.RunSeparatorCommand(self.current_input_file, "melband_roformer_inst_v2.ckpt", "Enstrümantal Çıkarma")

            if success and not self.is_cancelled:
                new_files = self.GetNewFiles(self.output_directory, files_before)
                for f in new_files:
                    full_path = os.path.join(self.output_directory, f)
                    if "(Instrumental)" in f:
                        self.RenameAndKeep(full_path, f"{base_filename}_Ghostkiller_Enstrumantal.flac")
                    else:
                        try:
                            os.remove(full_path)
                        except Exception:
                            pass

        steps = [
            (self.chk_step1, "model_bs_roformer_ep_317_sdr_12.9755.ckpt", "Ana Vokal Ayrıştırma", "(Vocals)", "_Ghostkiller_1_Ayrilmis_Vokal.flac"),
            (self.chk_step2, "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", "Arka Vokal Temizliği", "(Vocals)", "_Ghostkiller_2_ArkaSes_Silinmis.flac"),
            (self.chk_step3, "UVR-DeEcho-DeReverb.pth", "Yankı (Reverb) Temizliği", "(No Reverb)", "_Ghostkiller_3_Yankisiz_Vokal.flac"),
            (self.chk_step4, "UVR-DeNoise.pth", "Gürültü (Noise) Temizliği", "(No Noise)", "_Ghostkiller_4_Gurultusuz_Vokal.flac")
        ]

        for chk, model, step_name, keep_keyword, suffix in steps:
            if chk.GetValue() and not self.is_cancelled:
                files_before = set(os.listdir(self.output_directory))
                success = self.RunSeparatorCommand(working_file, model, step_name)

                if self.is_cancelled:
                    break

                if not success:
                    self.LogMessage(f"{step_name} durduruldu. Zincir iptal edildi.")
                    break

                new_files = self.GetNewFiles(self.output_directory, files_before)
                found_next_file = False

                for f in new_files:
                    full_path = os.path.join(self.output_directory, f)
                    if keep_keyword in f:
                        working_file = self.RenameAndKeep(full_path, base_filename + suffix)
                        found_next_file = True
                    else:
                        try:
                            os.remove(full_path)
                        except Exception:
                            pass

                if not found_next_file:
                    self.LogMessage(f"HATA: {step_name} çıktısı bulunamadı.")
                    break

        if self.is_cancelled:
            self.UpdateStatus("İşlem İptal Edildi", 0)
            self.LogMessage("\n--- İŞLEM KULLANICI TARAFINDAN İPTAL EDİLDİ ---")
            wx.CallAfter(wx.MessageBox, "İşlem iptal edildi.", "İptal", wx.OK | wx.ICON_WARNING)
        else:
            self.UpdateStatus("Tüm İşlemler Tamamlandı", 100)
            self.LogMessage("\n--- GHOSTKILLER İŞLEM ZİNCİRİ TAMAMLANDI ---")
            wx.CallAfter(wx.MessageBox, "Seçilen tüm işlemler başarıyla tamamlandı.", "İşlem Bitti", wx.OK | wx.ICON_INFORMATION)

        self.EnableUI(True)

    def OnStart(self, event):
        """Ayrıştırma işlemini arka plan iş parçacığı (threading) olarak başlatır."""
        if not self.current_input_file:
            wx.MessageBox("Lütfen önce bir ses dosyası seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return
        if not self.output_directory:
            wx.MessageBox("Lütfen bir çıktı klasörü seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return

        self.txt_log.Clear()
        self.LogMessage("İşlemler başlıyor. İnternet hızınıza bağlı olarak eksik modeller indirilebilir.")

        thread = threading.Thread(target=self.ProcessChain, daemon=True)
        thread.start()


if __name__ == '__main__':
    app = wx.App(False)
    frame = wx.Frame(None, title="Ghostkiller Sound Cleaner - Ses Ayrıştırma Test Paneli", size=(750, 800))
    panel = SeparatorPanel(frame)
    frame.Centre()
    frame.Show(True)
    app.MainLoop()
