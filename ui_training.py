# -*- coding: utf-8 -*-
"""Accessible native training UI; heavy operations run in an isolated process."""
from pathlib import Path
import json
import threading
import wx
from app_runtime import JOB_LOCK, post_ui, data_directory, finish_job
from training.config import TrainingOptions
from training.service import create_job, validate_resume, TrainingProcess, register_model


class TrainingPanel(wx.ScrolledWindow):
    def __init__(self, parent, settings):
        super().__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.settings = settings
        self.sources = []
        self.source_groups = {}
        self.job = self.result = self.runner = None
        self.busy = False
        self._last_stage = None
        self.analysis_cancel = None
        self.analysis_report = None
        self.SetScrollRate(0, 20)
        self.SetBackgroundColour(wx.Colour(30, 30, 30))
        self.SetForegroundColour(wx.Colour(240, 240, 240))
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label="Aynı kişiye ait temiz kayıtları seçin. Eğitim: RVC V2, ContentVec, HiFi-GAN, FP32.\nDonanım ve yardımcı modeller 4. Ayarlar sekmesinden hazırlanır."), 0, wx.ALL, 8)
        self.btn_settings = wx.Button(self, label="Donanım ve model ayarlarını aç")
        self.btn_settings.Bind(wx.EVT_BUTTON, lambda event: settings.open_settings())
        layout.Add(self.btn_settings, 0, wx.ALL, 8)
        self.source_list = wx.ListBox(self, size=(-1, 95))
        self.source_list.SetName("Aynı kişiye ait eğitim kayıtları")
        layout.Add(self.source_list, 0, wx.EXPAND | wx.ALL, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_add = wx.Button(self, label="Ses kayıtları ekle")
        self.btn_remove = wx.Button(self, label="Seçili kaydı kaldır")
        self.btn_group = wx.Button(self, label="Seçili kayda şarkı / oturum grubu ata")
        self.btn_add.Bind(wx.EVT_BUTTON, self.OnAdd)
        self.btn_remove.Bind(wx.EVT_BUTTON, self.OnRemove)
        self.btn_group.Bind(wx.EVT_BUTTON, self.OnGroup)
        for button in (self.btn_add, self.btn_remove):
            row.Add(button, 0, wx.ALL, 4)
        layout.Add(row, 0, wx.ALL, 4)
        layout.Add(self.btn_group, 0, wx.ALL, 8)
        layout.Add(wx.StaticText(self,label="Aynı şarkı veya kaynak vokalin farklı sürümlerine aynı grup adını verin; değerlendirmeye birlikte ayrılırlar."),0,wx.ALL,8)
        self.btn_analyze = wx.Button(self, label="Kayıtları analiz et")
        self.btn_analyze.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        layout.Add(self.btn_analyze, 0, wx.ALL, 8)
        self.txt_analysis = wx.TextCtrl(self, value="Kayıtları analiz ederek süre, seviye, tekrar ve kanal sorunlarını kontrol edin. Eğitimde analiz tekrar yapılır.", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 120))
        self.txt_analysis.SetName("Eğitim kayıtlarının analiz raporu")
        layout.Add(self.txt_analysis, 0, wx.EXPAND | wx.ALL, 8)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        grid.AddGrowableCol(1, 1)
        def field(label, control):
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control.SetName(label)
            grid.Add(control, 1, wx.EXPAND)
            return control
        self.model_name = field("Model adı", wx.TextCtrl(self))
        self.sample_rate = field("Örnekleme hızı", wx.Choice(self, choices=["32 kHz", "40 kHz", "48 kHz"]))
        self.sample_rate.SetSelection(1)
        self.epochs = field("Toplam epoch", wx.SpinCtrl(self, min=1, max=10000, initial=200))
        self.batch = field("Batch; 0 otomatik bellek ölçümü", wx.SpinCtrl(self, min=0, max=64, initial=0))
        self.interval = field("Checkpoint ve değerlendirme aralığı; epoch", wx.SpinCtrl(self, min=1, max=1000, initial=10))
        layout.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        self.advanced_toggle = wx.ToggleButton(self, label="Gelişmiş ayarlar [KAPALI]")
        self.advanced_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnAdvanced)
        layout.Add(self.advanced_toggle, 0, wx.ALL, 8)
        self.advanced = wx.Panel(self)
        advanced_layout = wx.FlexGridSizer(cols=2, vgap=8, hgap=10)
        advanced_layout.AddGrowableCol(1, 1)
        def advanced_field(label, control):
            advanced_layout.Add(wx.StaticText(self.advanced, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            control.SetName(label)
            advanced_layout.Add(control, 1, wx.EXPAND)
            return control
        self.learning_rate = advanced_field("Öğrenme hızı", wx.TextCtrl(self.advanced, value="0.0001"))
        self.segment = advanced_field("Hazırlama parçası süresi; saniye", wx.SpinCtrlDouble(self.advanced, min=1, max=6, initial=3, inc=.1))
        self.overlap = advanced_field("Parça örtüşmesi; saniye", wx.SpinCtrlDouble(self.advanced, min=0, max=1, initial=.3, inc=.1))
        self.holdout = advanced_field("Değerlendirme payı; yüzde", wx.SpinCtrl(self.advanced, min=5, max=30, initial=10))
        self.threads = advanced_field("İşlemci thread sınırı", wx.SpinCtrl(self.advanced, min=1, max=64, initial=4))
        self.f0 = advanced_field("Nota çıkarımı", wx.Choice(self.advanced, choices=["RMVPE", "CREPE", "CREPE Tiny"]))
        self.f0.SetSelection(0)
        self.checkpointing = wx.CheckBox(self.advanced, label="Gradyan checkpointing; daha az bellek, daha fazla hesaplama")
        self.checkpointing.SetValue(True)
        advanced_layout.Add(self.checkpointing, 0, wx.EXPAND)
        advanced_layout.AddSpacer(1)
        self.advanced.SetSizer(advanced_layout)
        layout.Add(self.advanced, 0, wx.EXPAND | wx.ALL, 8)
        self.advanced.Hide()
        self.txt_profile = wx.TextCtrl(self,style=wx.TE_MULTILINE | wx.TE_READONLY,size=(-1,60))
        self.txt_profile.SetName("Eğitim profili; hazırlama parçası ile optimizasyon parçasının farkı")
        layout.Add(self.txt_profile,0,wx.EXPAND | wx.ALL,8)
        self.txt_pitch = wx.TextCtrl(self,value="Perde kapsamı nota çıkarımı tamamlandığında gösterilir.",style=wx.TE_MULTILINE | wx.TE_READONLY,size=(-1,90))
        self.txt_pitch.SetName("Eğitim ve değerlendirme perde kapsamı; yaklaşık yüzdelikler")
        layout.Add(self.txt_pitch,0,wx.EXPAND | wx.ALL,8)
        self.sample_rate.Bind(wx.EVT_CHOICE,self.OnProfile)
        self.OnProfile(None)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label="Yeni model eğit")
        self.btn_resume = wx.Button(self, label="Eğitim oturumu seç ve devam et")
        self.btn_load = wx.Button(self, label="Kayıtlı eğitim oturumu aç")
        self.btn_cancel = wx.Button(self, label="Durdur ve devam noktası kaydet")
        self.btn_force_stop = wx.Button(self,label="Yanıt vermeyen eğitimi zorla durdur")
        self.btn_force_stop.SetName("Eğitimi zorla durdur; kaydedilmeyen adımlar kaybolabilir")
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)
        self.btn_resume.Bind(wx.EVT_BUTTON, self.OnResume)
        self.btn_load.Bind(wx.EVT_BUTTON, self.OnLoad)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.btn_force_stop.Bind(wx.EVT_BUTTON,self.OnForceStop)
        self.btn_cancel.Disable()
        self.btn_force_stop.Disable()
        for control in (self.btn_start, self.btn_resume, self.btn_cancel):
            buttons.Add(control, 0, wx.ALL, 4)
        layout.Add(buttons, 0, wx.ALL, 4)
        layout.Add(self.btn_force_stop,0,wx.ALL,8)
        layout.Add(self.btn_load, 0, wx.ALL, 8)
        self.gauge = wx.Gauge(self, range=100)
        self.gauge.SetName("Geçerli eğitim aşamasının ilerlemesi")
        layout.Add(self.gauge, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_status = wx.TextCtrl(self, value="Hazır. Ayarlar'dan ContentVec, RMVPE ve seçilen hızın eğitim G/D ağırlıklarını hazırlayın.", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 65))
        self.txt_status.SetName("Eğitim aşaması, epoch ve adım")
        layout.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_resources = wx.TextCtrl(self, value="Kaynak ölçümü eğitim başladığında gösterilir.", style=wx.TE_READONLY)
        self.txt_resources.SetName("İşlemci, RAM ve ekran kartı bellek kullanımı")
        layout.Add(self.txt_resources, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_timing = wx.TextCtrl(self, value="Kalan süre eğitim hızı ölçüldüğünde hesaplanır.", style=wx.TE_READONLY)
        self.txt_timing.SetName("Tahmini kalan eğitim süresi ve son kayıt")
        layout.Add(self.txt_timing, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_folder = wx.Button(self, label="Oturum klasörünü aç")
        self.btn_folder.Bind(wx.EVT_BUTTON, self.OnOpenFolder)
        self.btn_folder.Disable()
        layout.Add(self.btn_folder, 0, wx.ALL, 8)
        self.txt_job = wx.TextCtrl(self, value="Oturum seçilmedi.", style=wx.TE_READONLY)
        self.txt_job.SetName("Eğitim oturumu klasörü")
        layout.Add(self.txt_job, 0, wx.EXPAND | wx.ALL, 8)
        self.candidate = wx.Choice(self, choices=["Son epoch modeli", "En düşük değerlendirme mel hatalı model"])
        self.candidate.SetSelection(0)
        self.candidate.SetName("AI Cover'a eklenecek aday; mel hatası ses kalitesi garantisi değildir")
        self.candidate.Disable()
        layout.Add(self.candidate, 0, wx.EXPAND | wx.ALL, 8)
        self.test_mode = wx.Choice(self,choices=["Index kapalı: modelin kendi sesi", "Index açık: oturumun kayıtlı test sesi"])
        self.test_mode.SetSelection(0)
        self.test_mode.SetName("Dinlenecek uyumluluk sesi; kalite puanı değildir")
        self.test_mode.Disable()
        layout.Add(self.test_mode,0,wx.EXPAND | wx.ALL,8)
        self.btn_listen = wx.Button(self,label="Seçili adayın test sesini aç")
        self.btn_listen.Bind(wx.EVT_BUTTON,self.OnListen)
        self.btn_listen.Disable()
        layout.Add(self.btn_listen,0,wx.ALL,8)
        self.btn_register = wx.Button(self, label="Seçili modeli AI Cover'a ekle")
        self.btn_register.Bind(wx.EVT_BUTTON, self.OnRegister)
        self.btn_register.Disable()
        layout.Add(self.btn_register, 0, wx.ALL, 8)
        self.txt_log = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 150))
        self.txt_log.SetName("Eğitim günlüğü; tam günlük oturum klasöründe")
        layout.Add(self.txt_log, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(layout)
        self.FitInside()

    def OnAdvanced(self, event):
        enabled = self.advanced_toggle.GetValue()
        self.advanced_toggle.SetLabel("Gelişmiş ayarlar [AÇIK]" if enabled else "Gelişmiş ayarlar [KAPALI]")
        self.advanced.Show(enabled)
        self.Layout()
        self.FitInside()

    def OnAdd(self, event):
        with wx.FileDialog(self, "Aynı kişiye ait kayıtları seçin", wildcard="Ses kayıtları|*.wav;*.flac;*.mp3;*.ogg;*.m4a|Tüm dosyalar|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                for source in dialog.GetPaths():
                    if source not in self.sources:
                        self.sources.append(source)
                        self.source_list.Append(source)
                self.ClearAnalysis()
                self.source_list.SetFocus()

    def OnRemove(self, event):
        selected = self.source_list.GetSelection()
        if selected != wx.NOT_FOUND:
            self.source_groups.pop(self.sources[selected],None)
            del self.sources[selected]
            self.source_list.Delete(selected)
            self.ClearAnalysis()
        self.source_list.SetFocus()

    def RefreshSources(self):
        selection = self.source_list.GetSelection()
        self.source_list.Set([source+(f" | Grup: {self.source_groups[source]}" if self.source_groups.get(source) else " | Ayrı kayıt") for source in self.sources])
        if 0 <= selection < len(self.sources): self.source_list.SetSelection(selection)

    def OnGroup(self,event):
        selected = self.source_list.GetSelection()
        if selected == wx.NOT_FOUND:
            self.txt_status.SetValue("Önce gruplandırılacak kaydı seçin.")
            return
        source = self.sources[selected]
        with wx.TextEntryDialog(self,"Aynı şarkı/oturum/stem sürümleri için aynı adı kullanın. Boş bırakırsanız ayrı kayıt sayılır.","Kayıt grubu",self.source_groups.get(source,"")) as dialog:
            if dialog.ShowModal()!=wx.ID_OK: return
            group=dialog.GetValue().strip()
        if len(group)>100:
            self.txt_status.SetValue("Grup adı en fazla 100 karakter olmalı.")
            return
        if group: self.source_groups[source]=group
        else: self.source_groups.pop(source,None)
        self.RefreshSources()
        self.ClearAnalysis()
        self.source_list.SetFocus()

    def OnProfile(self,event):
        from training.config import architecture
        rate=(32000,40000,48000)[self.sample_rate.GetSelection()]
        config=architecture(rate)
        seconds=config['train']['segment_size']/rate
        self.txt_profile.SetValue(f"{rate//1000} kHz, RVC V2, FP32. Hazırlama parçası kaydı böler; optimizasyon parçası profilde {seconds:.3f} saniyedir. Yüksek örnekleme hızı kayıtta olmayan ayrıntıyı geri getirmez.")

    def Options(self):
        try:
            learning_rate = float(self.learning_rate.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Öğrenme hızı sayısal olmalı; örneğin 0.0001.")
        return TrainingOptions(name=self.model_name.GetValue().strip(), sources=tuple(self.sources),
                               sample_rate=(32000, 40000, 48000)[self.sample_rate.GetSelection()],
                               epochs=self.epochs.GetValue(), batch_size=self.batch.GetValue(),
                               save_every=self.interval.GetValue(), learning_rate=learning_rate,
                               segment_seconds=self.segment.GetValue(), overlap_seconds=self.overlap.GetValue(),
                               holdout_fraction=self.holdout.GetValue()/100, cpu_threads=self.threads.GetValue(),
                               f0_method=("rmvpe", "crepe", "crepe-tiny")[self.f0.GetSelection()],
                               checkpointing=self.checkpointing.GetValue(),
                               source_groups=tuple(self.source_groups.get(source,"") for source in self.sources) if self.source_groups else ()).validate()

    def EnableUI(self, enable):
        self.busy = not enable
        for control in (self.source_list, self.btn_add, self.btn_remove, self.model_name, self.sample_rate,
                        self.epochs, self.batch, self.interval, self.advanced_toggle, self.advanced,
                        self.btn_start, self.btn_resume, self.btn_analyze, self.btn_load, self.btn_group):
            control.Enable(enable)
        self.btn_cancel.Enable(not enable)
        self.btn_force_stop.Disable()
        self.candidate.Enable(enable and self.result is not None)
        self.btn_register.Enable(enable and self.result is not None)
        self.test_mode.Enable(enable and self.result is not None)
        self.btn_listen.Enable(enable and self.result is not None)

    def OnListen(self,event):
        if self.busy or not self.result: return
        candidate=("latest.pth","best_validation.pth")[self.candidate.GetSelection()]
        record=next((model for model in self.result['models'] if model['file']==candidate),{})
        key='test_audio_no_index' if self.test_mode.GetSelection()==0 else 'test_audio'
        path=record.get(key)
        if path and Path(path).is_file(): wx.LaunchDefaultApplication(path)
        else: self.txt_status.SetValue("Bu oturumda seçilen test sesi bulunmuyor. Yeni oturumlar index kapalı/açık test sesleri üretir.")

    def ShowPitch(self,report):
        lines=[]
        for split,label in (("train","Eğitim"),("holdout","Değerlendirme")):
            summary=report[split]
            def frequency(key):
                return f"{summary[key]:.1f} Hz" if summary.get(key) is not None else "ölçülmedi"
            lines.append(f"{label}: sesli çerçeve %{summary['voiced_fraction']*100:.1f}; yaklaşık %5 {frequency('p05_hz')}, medyan {frequency('median_hz')}, %95 {frequency('p95_hz')}; 50–1100 Hz dışı %{summary['out_of_range_fraction']*100:.2f}.")
        lines.append("Sıfır F0 nefes/ünsüz olabilir. Örtüşen parçalardaki çerçeveler benzersiz sesli süre değildir.")
        self.txt_pitch.SetValue("\n".join(lines))

    def ClearAnalysis(self):
        self.analysis_report = None
        self.txt_analysis.SetValue("Kayıt listesi değişti; güncel kayıtları analiz edin.")

    def OnAnalyze(self, event):
        if self.busy:
            return
        if not self.sources:
            self.txt_status.SetValue("Önce aynı kişiye ait ses kayıtları ekleyin.")
            return
        if not JOB_LOCK.acquire(blocking=False):
            self.txt_status.SetValue("Başka bir işlem sürüyor. Bitmesini bekleyin.")
            return
        sources = tuple(self.sources)
        rate = (32000, 40000, 48000)[self.sample_rate.GetSelection()]
        self.analysis_cancel = threading.Event()
        cancelled = self.analysis_cancel
        self.EnableUI(False)
        self.gauge.SetValue(0)
        self.txt_status.SetValue("Kayıtlar analiz ediliyor; özgün dosyalar değiştirilmeyecek.")
        def worker():
            try:
                from ui_separator import setup_ffmpeg_paths
                from app_runtime import app_directory
                from training.analysis import analyze_sources
                setup_ffmpeg_paths(app_directory())
                report = analyze_sources(sources, rate, cancelled.is_set,
                    lambda stage, **values: post_ui(self, self.OnProgress, dict(stage=stage, **values)))
                post_ui(self, self.OnAnalyzed, report)
            except Exception as error:
                post_ui(self, self.OnOperationError, str(error), "Kayıt analizi durdu")
            finally:
                post_ui(self, self.AnalysisStopped)
                finish_job(self)
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception as error:
            self.analysis_cancel = None
            self.EnableUI(True)
            JOB_LOCK.release()
            self.txt_status.SetValue(str(error))

    def AnalysisStopped(self):
        self.analysis_cancel = None

    def OnAnalyzed(self, report, announce=True):
        from training.analysis import report_text
        self.analysis_report = report
        self.txt_analysis.SetValue(report_text(report))
        self.txt_status.SetValue("Analiz tamamlandı. Uyarıları okuyun; kayıtları dinleyerek kontrol edin.")
        if announce:
            self.NotifyResult(self.txt_status.GetValue(),"Kayıt analizi tamamlandı",self.txt_analysis)

    def NotifyResult(self,message,title,focus=None,error=False):
        """A native focused dialog exposes terminal results to screen readers."""
        self.txt_status.SetValue(message)
        wx.MessageBox(message,title,wx.OK | (wx.ICON_ERROR if error else wx.ICON_INFORMATION),parent=self)
        (focus or self.txt_status).SetFocus()

    def OnOperationError(self,message,title):
        self.NotifyResult(message or "İşlem açıklamasız bir hatayla durdu; günlüğü kontrol edin.",title,error=True)

    def OnOpenFolder(self, event):
        if self.job and Path(self.job).is_dir():
            wx.LaunchDefaultApplication(self.job)

    def OnStart(self, event):
        self.Start(False)

    def OnResume(self, event):
        if self.busy:
            return
        with wx.DirDialog(self, "manifest.json içeren eğitim oturumunu seçin", defaultPath=str(Path(data_directory())/"training_runs")) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.Start(True, dialog.GetPath())

    def ShowOptions(self, options):
        self.sources = list(options.sources)
        self.source_groups = {source:group for source,group in zip(options.sources,options.source_groups) if group}
        self.RefreshSources()
        self.model_name.SetValue(options.name)
        self.sample_rate.SetSelection((32000,40000,48000).index(options.sample_rate))
        self.OnProfile(None)
        for control, value in ((self.epochs,options.epochs),(self.batch,options.batch_size),
                               (self.interval,options.save_every),(self.segment,options.segment_seconds),
                               (self.overlap,options.overlap_seconds),(self.holdout,round(options.holdout_fraction*100)),
                               (self.threads,options.cpu_threads)):
            control.SetValue(value)
        self.learning_rate.SetValue(str(options.learning_rate))
        self.f0.SetSelection(("rmvpe","crepe","crepe-tiny").index(options.f0_method))
        self.checkpointing.SetValue(options.checkpointing)

    def OnLoad(self, event):
        if self.busy:
            return
        with wx.DirDialog(self, "Kayıtlı eğitim oturumunu seçin", defaultPath=str(Path(data_directory())/"training_runs")) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            job = Path(dialog.GetPath())
        try:
            from training.storage import read_manifest
            manifest = read_manifest(job)
            options = TrainingOptions.from_dict(manifest["options"])
            result = json.loads((job/"result.json").read_text(encoding="utf-8")) if manifest.get("status")=="completed" else None
            report = json.loads((job/"quality_report.json").read_text(encoding="utf-8")) if (job/"quality_report.json").exists() else None
            self.ShowOptions(options)
            self.job, self.result = str(job), result
            self.runner = None
            self.txt_job.SetValue(str(job))
            self.btn_folder.Enable()
            if (job/"pitch_report.json").exists():
                self.ShowPitch(json.loads((job/"pitch_report.json").read_text(encoding="utf-8")))
            else:
                self.txt_pitch.SetValue("Bu oturumda perde kapsamı raporu yok.")
            if report:
                self.OnAnalyzed(report,announce=False)
            else:
                self.ClearAnalysis()
            self.txt_status.SetValue("Tamamlanan oturum açıldı; adayı AI Cover'a ekleyebilirsiniz." if result else "Oturum açıldı. Devam düğmesi kayıtlı ayarlarla eğitimi sürdürür.")
            self.txt_timing.SetValue(f"Son kayıtlı adım: {manifest.get('last_checkpoint_step','bilinmiyor')}.")
            self.gauge.SetValue(100 if result else 0)
            self.EnableUI(True)
        except Exception as error:
            self.txt_status.SetValue(str(error))

    def Start(self, resume, job=None):
        if self.busy or not JOB_LOCK.acquire(blocking=False):
            self.txt_status.SetValue("Başka bir işlem sürüyor. Bitmesini bekleyin.")
            return
        try:
            if resume:
                self.ShowOptions(validate_resume(job, self.settings))
            else:
                job = create_job(self.Options(), self.settings)
            self.job, self.result = job, None
            self.runner = TrainingProcess()
            self.runner.job = job
            cancel = Path(job)/"cancel.request"
            if cancel.exists():
                cancel.unlink()
            self._last_stage = None
            self.EnableUI(False)
            self.gauge.SetValue(0)
            self.txt_job.SetValue(job)
            self.txt_pitch.SetValue("Perde kapsamı nota çıkarımı tamamlandığında gösterilir.")
            self.btn_folder.Enable()
            self.txt_timing.SetValue("Kalan süre hesaplanıyor. Devam noktaları eğitim sırasında yaklaşık beş dakikada bir ve durdurmada kaydedilir.")
            self.txt_status.SetValue("Eğitim alt işlemi başlatılıyor...")
            threading.Thread(target=self.Run, args=(resume,), daemon=True).start()
        except Exception as error:
            JOB_LOCK.release()
            self.EnableUI(True)
            self.txt_status.SetValue(str(error))
            wx.MessageBox(str(error), "Eğitim başlatılamadı", wx.OK | wx.ICON_ERROR)

    def Run(self, resume):
        try:
            result = self.runner.run(self.job, lambda value: post_ui(self, self.OnProgress, value), resume)
            post_ui(self, self.OnFinished, result, "Eğitim tamamlandı. Test sesleri oturum klasöründedir; dinleyip adayı AI Cover'a ekleyin.")
        except Exception as error:
            post_ui(self, self.OnFinished, None, str(error))
        finally:
            finish_job(self)

    def OnProgress(self, value):
        stage = value.get("stage")
        if stage == "unresponsive":
            self.btn_force_stop.Enable(self.busy and self.runner is not None)
        elif stage == "responsive" and self.runner and not self.runner.cancel_requested:
            self.btn_force_stop.Disable()
        if stage == 'pitch_summary':
            self.ShowPitch(value['report'])
            return
        if stage == "checkpoint":
            self.txt_timing.SetValue(value.get("message", "Devam noktası kaydedildi."))
        elif stage == "train" and value.get("eta_seconds") is not None:
            minutes = max(0, round(value["eta_seconds"]/60))
            self.txt_timing.SetValue(f"Tahmini kalan eğitim: {minutes//60} saat {minutes%60} dakika. Index ve uyumluluk testleri bu süreye dahil değildir.")
        if stage == "resources":
            text = f"CPU %{value['cpu_percent']:.0f} (bir çekirdek %100)"
            for key, label in (("rss_mb", "RAM"), ("available_ram_mb", "Boş RAM"),
                               ("vram_allocated_mb", "VRAM"), ("vram_peak_mb", "Tepe VRAM"),
                               ("vram_free_mb", "Boş VRAM")):
                if key in value:
                    text += f"; {label} {value[key]:.0f} MB"
            self.txt_resources.SetValue(text)
            return
        message = value.get("message", "")
        if stage != "log":
            if stage not in ("checkpoint", "evaluate", "quality"):
                if stage != self._last_stage:
                    self.gauge.SetValue(0)
                self._last_stage = stage
            self.txt_status.SetValue(message)
            if "percent" in value:
                self.gauge.SetValue(max(0, min(100, int(value["percent"]))))
        if message:
            if self.txt_log.GetLastPosition() > 48000:
                self.txt_log.SetValue(self.txt_log.GetValue()[-24000:])
            self.txt_log.AppendText(message+"\n")

    def OnFinished(self, result, message):
        self.result = result
        self.txt_status.SetValue(message)
        if result:
            self.gauge.SetValue(100)
        self.btn_force_stop.Disable()
        self.NotifyResult(message,"Eğitim tamamlandı" if result else "Eğitim durdu",error=not result)

    def OnCancel(self, event):
        if self.analysis_cancel is not None:
            self.analysis_cancel.set()
            self.btn_cancel.Disable()
            self.txt_status.SetValue("Kayıt analizi durduruluyor...")
            return
        if self.runner:
            self.runner.cancel()
            self.btn_cancel.Disable()
            self.txt_status.SetValue("İptal istendi; mevcut tam optimizasyon adımı bitince devam noktası kaydedilecek.")
            self.btn_force_stop.Enable()
            self.txt_status.SetFocus()

    def OnForceStop(self,event):
        if not self.busy or self.analysis_cancel is not None or self.runner is None:
            return
        message = "Zorla durdurma henüz kaydedilmeyen adımları kaybettirir. Yalnız son tamamlanmış atomik kontrol noktası korunur. Eğitimi zorla durdurmak istiyor musunuz?"
        if wx.MessageBox(message,"Eğitimi zorla durdur",wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,parent=self) != wx.YES:
            self.btn_force_stop.SetFocus()
            return
        self.runner.force_stop()
        self.btn_force_stop.Disable()
        self.btn_cancel.Disable()
        self.txt_status.SetValue("Eğitim alt işlemi zorla durduruluyor; son sağlam devam noktası korunacak.")
        self.txt_status.SetFocus()

    def OnRegister(self, event):
        if not self.result or self.busy or not JOB_LOCK.acquire(blocking=False):
            return
        self.EnableUI(False)
        self.btn_cancel.Disable()
        candidate = ("latest.pth", "best_validation.pth")[self.candidate.GetSelection()]
        def worker():
            try:
                from ui_cover import get_models_file_path, get_app_dir
                name = register_model(self.job, candidate, get_models_file_path(get_app_dir()))
                post_ui(self, self.OnRegistered, name)
            except Exception as error:
                post_ui(self, self.OnOperationError, str(error), "Model kaydedilemedi")
            finally:
                finish_job(self)
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            JOB_LOCK.release()
            self.EnableUI(True)
            raise

    def OnRegistered(self, name):
        self.txt_status.SetValue(f"{name} AI Cover model listesine eklendi.")
        refresh = getattr(self.settings, "refresh_cover", None)
        if refresh:
            refresh()
        self.NotifyResult(self.txt_status.GetValue(),"Model kaydı tamamlandı")
