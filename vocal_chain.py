import wx
import os
import threading
import re
import sys
import gc
import traceback

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
os.environ["PATH"] = app_dir + os.pathsep + os.environ.get("PATH", "")

try:
    import pydub
    pydub.AudioSegment.converter = os.path.join(app_dir, "ffmpeg.exe")
    pydub.utils.get_prober_name = lambda: os.path.join(app_dir, "ffprobe.exe")
except:
    pass

from audio_separator.separator import Separator 

class VocalChainApp(wx.Frame):
    def __init__(self, parent, title):
        super(VocalChainApp, self).__init__(parent, title=title, size=(750, 800))
        
        self.current_input_file = ""
        self.output_directory = ""
        self.is_cancelled = False
        
        self.bg_main = wx.Colour(30, 30, 30)
        self.bg_panel = wx.Colour(40, 40, 40)
        self.bg_btn = wx.Colour(60, 60, 60)
        self.bg_btn_active = wx.Colour(0, 120, 215)
        self.fg_light = wx.Colour(240, 240, 240)
        self.fg_status = wx.Colour(100, 200, 255)
        self.fg_log = wx.Colour(0, 255, 128)
        
        self.InitUI()
        self.Centre()
        
        wx.CallAfter(self.ShowStartupMessage)
        
    def ShowStartupMessage(self):
        wx.MessageBox("Bu program Yasin Talha Gençsoy tarafından yapılmıştır.", "Bilgi", wx.OK | wx.ICON_INFORMATION)

    def InitUI(self):
        wx.SystemOptions.SetOption("msw.window.dark-mode", 1)
        
        font_large = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        font_normal = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        
        self.SetBackgroundColour(self.bg_main)
        
        panel = wx.Panel(self)
        panel.SetBackgroundColour(self.bg_main)
        panel.SetForegroundColour(self.fg_light)
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        file_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_file = wx.Button(panel, label="1. Ses Dosyası Seç", size=(-1, 45))
        self.btn_select_file.SetFont(font_large)
        self.btn_select_file.SetBackgroundColour(self.bg_btn)
        self.btn_select_file.SetForegroundColour(self.fg_light)
        self.btn_select_file.Bind(wx.EVT_BUTTON, self.OnFileSelect)
        
        self.txt_selected_file = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_file.SetBackgroundColour(self.bg_panel)
        self.txt_selected_file.SetForegroundColour(self.fg_light)
        self.txt_selected_file.SetFont(font_normal)
        
        file_box.Add(self.btn_select_file, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        file_box.Add(self.txt_selected_file, 1, wx.ALL | wx.EXPAND, 5)
        vbox.Add(file_box, 0, wx.EXPAND | wx.ALL, 5)

        dir_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_select_dir = wx.Button(panel, label="2. Çıktı Klasörü Seç", size=(-1, 45))
        self.btn_select_dir.SetFont(font_large)
        self.btn_select_dir.SetBackgroundColour(self.bg_btn)
        self.btn_select_dir.SetForegroundColour(self.fg_light)
        self.btn_select_dir.Bind(wx.EVT_BUTTON, self.OnDirSelect)
        
        self.txt_selected_dir = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_selected_dir.SetBackgroundColour(self.bg_panel)
        self.txt_selected_dir.SetForegroundColour(self.fg_light)
        self.txt_selected_dir.SetFont(font_normal)
        
        dir_box.Add(self.btn_select_dir, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        dir_box.Add(self.txt_selected_dir, 1, wx.ALL | wx.EXPAND, 5)
        vbox.Add(dir_box, 0, wx.EXPAND | wx.ALL, 5)
        
        box_options = wx.StaticBox(panel, label="3. Çıkarılacak Kanallar ve İşlemler")
        box_options.SetForegroundColour(self.fg_light)
        box_options.SetFont(font_large)
        sizer_options = wx.StaticBoxSizer(box_options, wx.VERTICAL)
        
        def CreateToggleBtn(label, is_active=False):
            state_text = "[AÇIK]" if is_active else "[KAPALI]"
            btn = wx.ToggleButton(panel, label=f"{label} - {state_text}", size=(-1, 40))
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

        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_start = wx.Button(panel, label="Ghostkiller İşlemlerini Başlat", size=(-1, 60))
        self.btn_start.SetFont(font_large)
        self.btn_start.SetBackgroundColour(wx.Colour(0, 150, 100))
        self.btn_start.SetForegroundColour(self.fg_light)
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)
        
        self.btn_cancel = wx.Button(panel, label="İptal Et", size=(150, 60))
        self.btn_cancel.SetFont(font_large)
        self.btn_cancel.SetBackgroundColour(wx.Colour(200, 50, 50))
        self.btn_cancel.SetForegroundColour(self.fg_light)
        self.btn_cancel.Enable(False)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        
        btn_box.Add(self.btn_start, 1, wx.EXPAND | wx.ALL, 5)
        btn_box.Add(self.btn_cancel, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(btn_box, 0, wx.EXPAND | wx.ALL, 5)
        
        self.txt_log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.BORDER_SIMPLE)
        self.txt_log.SetFont(font_normal)
        self.txt_log.SetBackgroundColour(self.bg_panel)
        self.txt_log.SetForegroundColour(self.fg_log)
        vbox.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 5)
        
        self.txt_status = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.BORDER_SIMPLE)
        self.txt_status.SetFont(font_large)
        self.txt_status.SetBackgroundColour(self.bg_main)
        self.txt_status.SetForegroundColour(self.fg_status)
        self.txt_status.SetValue("Durum: Bekliyor (Yüzde takibi için burayı okutun)")
        vbox.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 5)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(vbox)
        self.LogMessage("Sistem Hazır. İşlem yapmak için dosya seçin.")

    def OnCheckToggle(self, event):
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
        dlg = wx.DirDialog(self, message="Çıktı klasörünü seçin", defaultPath=os.getcwd())
        if dlg.ShowModal() == wx.ID_OK:
            self.output_directory = dlg.GetPath()
            self.txt_selected_dir.SetValue(self.output_directory)
            self.LogMessage(f"Çıktı klasörü ayarlandı: {self.output_directory}")
        dlg.Destroy()

    def LogMessage(self, message):
        clean_message = message.strip()
        if clean_message:
            wx.CallAfter(self.txt_log.AppendText, clean_message + "\n")
            wx.CallAfter(self.txt_log.ShowPosition, self.txt_log.GetLastPosition())

    def UpdateStatus(self, text, percent=None):
        status_msg = f"Durum: {text}"
        if percent is not None:
            status_msg += f" - %{percent}"
            wx.CallAfter(self.gauge.SetValue, percent)
        wx.CallAfter(self.txt_status.SetValue, status_msg)

    def EnableUI(self, enable):
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
        files_after = set(os.listdir(directory))
        return list(files_after - files_before)

    def RenameAndKeep(self, original_path, new_filename):
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
        self.is_cancelled = True
        self.UpdateStatus("İptal ediliyor... (Mevcut işlem bitince duracak)", 0)
        self.btn_cancel.Enable(False)

    def RunSeparatorCommand(self, input_file, model_name, step_name):
        self.UpdateStatus(f"{step_name} başlatılıyor...", 0)
        self.LogMessage(f"--- İŞLEM: {step_name} ---")
        
        try:
            class StderrCatcher:
                def __init__(self, app_instance, step_name):
                    self.app = app_instance
                    self.step_name = step_name
                    self.current_phase = "Model İndiriliyor/Hazırlanıyor"
                def write(self, text):
                    if self.app.is_cancelled: return
                    clean_line = text.strip()
                    if clean_line:
                        match = re.search(r'(\d+)%', clean_line)
                        if match:
                            percent = int(match.group(1))
                            self.app.UpdateStatus(f"{self.current_phase} ({self.step_name})", percent)
                        elif "Error" in clean_line or "Exception" in clean_line:
                            self.app.LogMessage(f"HATA: {clean_line}")
                def flush(self): pass

            catcher = StderrCatcher(self, step_name)
            old_stderr = sys.stderr
            sys.stderr = catcher
            
            separator = Separator(output_dir=self.output_directory, output_format="FLAC")
            
            # Model indirme/yükleme aşaması
            catcher.current_phase = "Model İndiriliyor/Hazırlanıyor"
            separator.load_model(model_filename=model_name)
            
            if self.is_cancelled:
                sys.stderr = old_stderr
                return False
                
            # Ses işleme aşaması
            catcher.current_phase = "Ses İşleniyor"
            self.UpdateStatus(f"Ses İşleniyor ({step_name})...", 0)
            separator.separate(input_file)
            
            del separator
            gc.collect()
            
            sys.stderr = old_stderr
            return True
            
        except Exception as e:
            self.LogMessage(f"SİSTEM HATASI: {str(e)}")
            try: sys.stderr = old_stderr
            except: pass
            
            try:
                del separator
                gc.collect()
            except: pass
            
            return False

    def ProcessChain(self):
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
                        try: os.remove(full_path)
                        except: pass

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
                        try: os.remove(full_path)
                        except: pass

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
        if not self.current_input_file:
            wx.MessageBox("Lütfen önce bir ses dosyası seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return
        if not self.output_directory:
            wx.MessageBox("Lütfen bir çıktı klasörü seçin.", "Eksik Bilgi", wx.OK | wx.ICON_WARNING)
            return
            
        self.txt_log.Clear()
        self.LogMessage("İşlemler başlıyor. İnternet hızınıza bağlı olarak eksik modeller indirilebilir.")
        
        thread = threading.Thread(target=self.ProcessChain)
        thread.start()

if __name__ == '__main__':
    def global_exception_handler(exc_type, exc_value, exc_tb):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            log_path = os.path.join(desktop_path, "Ghostkiller_CrashLog.txt")
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("--- GHOSTKILLER ÇÖKME RAPORU ---\n")
                f.write(error_msg + "\n\n")
                
            wx.MessageBox(
                f"Programda kritik bir hata oluştu ve kapandı!\n\nDetaylar masaüstündeki 'Ghostkiller_CrashLog.txt' dosyasına kaydedildi.\n\nKısa Hata: {exc_value}", 
                "Ölümcül Hata", 
                wx.OK | wx.ICON_ERROR
            )
        except:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        
    sys.excepthook = global_exception_handler

    app = wx.App(False)
    frame = VocalChainApp(None, "Ghostkiller Sound Cleaner")
    frame.Show(True)
    app.MainLoop()