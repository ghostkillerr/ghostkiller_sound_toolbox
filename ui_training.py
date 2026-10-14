# -*- coding: utf-8 -*-
"""Accessible native training UI; heavy operations run in an isolated process."""
from pathlib import Path
import json
import threading
import wx
from ui_common import apply_native_style, add_intro, section_title, name_control, explanation_control
from app_runtime import JOB_LOCK, post_ui, data_directory, finish_job
from training.config import TrainingOptions
from training.service import create_job, validate_resume, TrainingProcess, register_model


class TrainingPanel(wx.ScrolledWindow):
    def __init__(self, parent, settings):
        super().__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.settings = settings
        self.sources, self.source_groups = [], {}
        self.job = self.result = self.runner = None
        self.busy = False
        self._last_stage = None
        self.analysis_cancel = self.analysis_report = None
        self.field_explanations = {}
        self.SetScrollRate(0,20)
        layout = wx.BoxSizer(wx.VERTICAL)
        add_intro(self,layout,"Ses modeli eğitimi","Aynı kişinin ses kayıtlarını ekleyin, modelinize ad verin ve eğitimi başlatın. Kayıtlar eğitimden önce otomatik kontrol edilir.")
        section_title(self,layout,"Ses kayıtları")
        self.btn_add = wx.Button(self,label="Ses kayıtları ekle")
        self.btn_add.Bind(wx.EVT_BUTTON,self.OnAdd)
        layout.Add(self.btn_add,0,wx.ALL,8)
        wx_label = wx.StaticText(self,label="Eklenen ses kayıtları")
        layout.Add(wx_label,0,wx.LEFT | wx.RIGHT,8)
        self.empty_sources = wx.StaticText(self,label="Henüz ses kaydı eklenmedi.")
        layout.Add(self.empty_sources,0,wx.ALL,8)
        self.source_list = name_control(wx.ListBox(self,size=(-1,95)),"Eklenen ses kayıtları; ok tuşlarıyla kayıt seçin")
        layout.Add(self.source_list,0,wx.EXPAND | wx.ALL,8)
        self.source_list.Hide()
        self.btn_remove = wx.Button(self,label="Seçili ses kaydını listeden kaldır")
        self.btn_remove.Bind(wx.EVT_BUTTON,self.OnRemove)
        self.btn_remove.Disable()
        layout.Add(self.btn_remove,0,wx.ALL,8)
        section_title(self,layout,"Eğitim ayarları")

        def field(parent,sizer,label,create,explanation='',focus_explanation=True):
            # Native Windows label association needs the label HWND first.
            title = wx.StaticText(parent,label=label)
            sizer.Add(title,0,wx.LEFT | wx.RIGHT | wx.TOP,8)
            control = name_control(create(),label,'' if focus_explanation else explanation)
            sizer.Add(control,0,wx.EXPAND | wx.ALL,8)
            if explanation:
                text = explanation_control(parent,label+' açıklaması',explanation) if focus_explanation else wx.StaticText(parent,label=explanation)
                if focus_explanation:
                    text.MoveAfterInTabOrder(control)
                    self.field_explanations[control] = text
                sizer.Add(text,0,wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,8)
            return control

        self.model_name = field(self,layout,"Model adı",lambda:wx.TextCtrl(self),"Yeni ses modeline vereceğiniz adı yazın.",False)
        self.sample_rate = field(self,layout,"Ses örnekleme hızı (kHz)",lambda:wx.Choice(self,choices=["32 kHz","40 kHz","48 kHz"]),"Emin değilseniz 40 kHz seçili kalsın.",False)
        self.sample_rate.SetSelection(1)
        self.epochs = field(self,layout,"Eğitim tekrar sayısı (epoch)",lambda:wx.SpinCtrl(self,min=1,max=10000,initial=200),"200 epoch, kayıtların eğitim sırasında 200 kez işlenmesi demektir. Daha fazla tekrar daha uzun sürer. Gereğinden fazla tekrar sonucu kötüleştirebilir.")
        self.advanced_toggle = wx.ToggleButton(self,label="Gelişmiş eğitim ayarları [KAPALI]")
        self.advanced_toggle.Bind(wx.EVT_TOGGLEBUTTON,self.OnAdvanced)
        layout.Add(self.advanced_toggle,0,wx.ALL,8)
        self.advanced = wx.Panel(self,style=wx.TAB_TRAVERSAL)
        advanced_layout = wx.BoxSizer(wx.VERTICAL)
        field_advanced = lambda label,create,help_text,focus=True:field(self.advanced,advanced_layout,label,create,help_text,focus)
        self.batch = field_advanced("Aynı anda işlenen parça sayısı; 0 otomatik",lambda:wx.SpinCtrl(self.advanced,min=0,max=64,initial=0),"0 seçilirse program belleğe uygun sayıyı ölçer. Sayıyı artırmak daha çok bellek kullanır.")
        self.interval = field_advanced("Kaydetme ve değerlendirme aralığı (epoch)",lambda:wx.SpinCtrl(self.advanced,min=1,max=1000,initial=10),"10 seçilirse her 10 eğitim tekrarında model kaydedilir ve değerlendirilir. Devam kaydı ayrıca yaklaşık beş dakikada bir alınır.")
        self.learning_rate = field_advanced("Öğrenme hızı",lambda:wx.TextCtrl(self.advanced,value="0.0001"),"Modelin bir adımda ne kadar değişeceğini belirler. 0.0001 küçük bir değişimdir; emin değilseniz değiştirmeyin.")
        self.segment = field_advanced("Hazırlanan ses parçalarının süresi (saniye)",lambda:wx.TextCtrl(self.advanced,value='3.0'),"3.0 değeri, kayıtların hazırlıkta üç saniyelik parçalara bölünmesi demektir. 1 ile 6 saniye arasında bir değer yazın.")
        self.overlap = field_advanced("Ardışık parçaların ortak süresi (saniye)",lambda:wx.TextCtrl(self.advanced,value='0.3'),"0.3 değeri, iki komşu parçada aynı sesin 0.3 saniyesinin bulunması demektir. 0 ile 1 saniye arasında bir değer yazın.")
        self.holdout = field_advanced("Kontrol için ayrılan kayıt payı (yüzde)",lambda:wx.SpinCtrl(self.advanced,min=5,max=30,initial=10),"10 seçilirse verinin yaklaşık yüzde 10'u modele öğretilmez; sonucu kontrol etmek için ayrılır.")
        self.threads = field_advanced("Kullanılacak işlemci iş parçacığı sayısı",lambda:wx.SpinCtrl(self.advanced,min=1,max=64,initial=4),"4 seçilirse en fazla dört işlemci iş parçacığı kullanılır. Artırmak bazı işleri hızlandırabilir; her bilgisayarda daha hızlı olmaz ve bilgisayarı daha fazla meşgul edebilir.")
        self.f0 = field_advanced("Nota algılama yöntemi",lambda:wx.Choice(self.advanced,choices=["RMVPE","CREPE","CREPE Tiny"]),"Sesin notasını bulur. Emin değilseniz RMVPE seçili kalsın.",False)
        self.f0.SetSelection(0)
        self.checkpointing = wx.CheckBox(self.advanced,label="Bellek tasarrufu kullan; eğitim daha yavaş olabilir")
        self.checkpointing.SetValue(True)
        advanced_layout.Add(self.checkpointing,0,wx.ALL,8)
        self.group_intro = wx.StaticText(self.advanced,label="Yalnız aynı şarkının birden fazla kaydını eklediyseniz bunlara aynı eşleştirme adını verin. Böylece modelin kontrolü, öğrendiği şarkının başka kopyasıyla yapılmaz. Farklı şarkılarda eşleştirme gerekmez.")
        self.group_intro.Wrap(self.FromDIP(620))
        advanced_layout.Add(self.group_intro,0,wx.EXPAND | wx.ALL,8)
        self.btn_group = wx.Button(self.advanced,label="Seçili kaydı aynı şarkının diğer kayıtlarıyla eşleştir")
        name_control(self.btn_group,'Seçili kaydı aynı şarkının diğer kayıtlarıyla eşleştir',self.group_intro.GetLabel())
        self.btn_group.Bind(wx.EVT_BUTTON,self.OnGroup)
        self.btn_group.Disable()
        self.group_intro.Hide()
        self.btn_group.Hide()
        advanced_layout.Add(self.btn_group,0,wx.ALL,8)
        self.advanced.SetSizer(advanced_layout)
        layout.Add(self.advanced,0,wx.EXPAND | wx.ALL,8)
        self.advanced.Hide()

        self.btn_start = wx.Button(self,label="Yeni ses modeli eğit")
        self.btn_start.Bind(wx.EVT_BUTTON,self.OnStart)
        layout.Add(self.btn_start,0,wx.ALL,8)
        self.btn_resume = wx.Button(self,label="Yarım kalan eğitime devam et")
        self.btn_resume.Bind(wx.EVT_BUTTON,self.OnResume)
        name_control(self.btn_resume,'Yarım kalan eğitime devam et. Daha önce durdurduğunuz eğitimi, son kaydedilen noktadan sürdürür.')
        layout.Add(self.btn_resume,0,wx.ALL,8)
        self.btn_load = wx.Button(self,label="Kayıtlı eğitimin sonuçlarını aç")
        self.btn_load.Bind(wx.EVT_BUTTON,self.OnLoad)
        layout.Add(self.btn_load,0,wx.ALL,8)

        self.progress_panel = wx.Panel(self,style=wx.TAB_TRAVERSAL)
        progress_layout = wx.BoxSizer(wx.VERTICAL)
        section_title(self.progress_panel,progress_layout,"Eğitim durumu")
        self.gauge = wx.Gauge(self.progress_panel,range=100)
        self.gauge.SetName("Eğitim ilerlemesi")
        progress_layout.Add(self.gauge,0,wx.EXPAND | wx.ALL,8)
        def report_field(name,multiline=True):
            control = name_control(wx.TextCtrl(self.progress_panel,style=wx.TE_READONLY | (wx.TE_MULTILINE if multiline else 0),size=(-1,70 if multiline else -1)),name)
            progress_layout.Add(control,0,wx.EXPAND | wx.ALL,8)
            return control
        self.txt_status = report_field("Eğitim durumu ve yapılan işlem")
        self.txt_resources = report_field("İşlemci ve bellek kullanımı",False)
        self.txt_timing = report_field("Kalan süre ve son kayıt",False)
        self.txt_job = report_field("Eğitim kayıt klasörü",False)
        self.txt_analysis = report_field("Otomatik kayıt kontrolünün sonucu")
        self.txt_pitch = report_field("Ölçülen sesin nota aralığı")
        self.txt_log = report_field("Eğitim işlem günlüğü")
        for control in (self.txt_resources,self.txt_timing,self.txt_job,self.txt_analysis,self.txt_pitch,self.txt_log): control.Hide()
        self.btn_cancel = wx.Button(self.progress_panel,label="Eğitimi durdur ve devam etmek için kaydet")
        self.btn_cancel.Bind(wx.EVT_BUTTON,self.OnCancel)
        self.btn_cancel.Disable()
        progress_layout.Add(self.btn_cancel,0,wx.ALL,8)
        self.btn_force_stop = wx.Button(self.progress_panel,label="Yanıt vermeyen eğitimi zorla durdur")
        self.btn_force_stop.Bind(wx.EVT_BUTTON,self.OnForceStop)
        self.btn_force_stop.Disable()
        progress_layout.Add(self.btn_force_stop,0,wx.ALL,8)
        self.btn_folder = wx.Button(self.progress_panel,label="Eğitim kayıt klasörünü aç")
        self.btn_folder.Bind(wx.EVT_BUTTON,self.OnOpenFolder)
        self.btn_folder.Disable()
        progress_layout.Add(self.btn_folder,0,wx.ALL,8)
        self.progress_panel.SetSizer(progress_layout)
        layout.Add(self.progress_panel,0,wx.EXPAND | wx.ALL,8)
        self.progress_panel.Hide()

        self.result_panel = wx.Panel(self,style=wx.TAB_TRAVERSAL)
        result_layout = wx.BoxSizer(wx.VERTICAL)
        section_title(self.result_panel,result_layout,"Sonucu dinle ve kullan")
        self.candidate = field(self.result_panel,result_layout,"Dinlenecek ses modeli",lambda:wx.Choice(self.result_panel,choices=["Son eğitim modeli","Kontrol hatası en düşük model"]),"İkinci seçenek mutlaka daha iyi ses demek değildir; iki sonucu da dinleyin.")
        self.candidate.SetSelection(0)
        self.test_mode = field(self.result_panel,result_layout,"Dinlenecek test kaydı",lambda:wx.Choice(self.result_panel,choices=["Modelin kendi sesi (index kapalı)","Eğitim kayıtlarından destekli ses (index açık)"]))
        self.test_mode.SetSelection(0)
        self.btn_listen = wx.Button(self.result_panel,label="Seçili modelin test sesini dinle")
        self.btn_listen.Bind(wx.EVT_BUTTON,self.OnListen)
        result_layout.Add(self.btn_listen,0,wx.ALL,8)
        self.btn_register = wx.Button(self.result_panel,label="Seçili modeli ses değiştirme listesine ekle")
        self.btn_register.Bind(wx.EVT_BUTTON,self.OnRegister)
        result_layout.Add(self.btn_register,0,wx.ALL,8)
        for control in (self.candidate,self.test_mode,self.btn_listen,self.btn_register):control.Disable()
        self.result_panel.SetSizer(result_layout)
        layout.Add(self.result_panel,0,wx.EXPAND | wx.ALL,8)
        self.result_panel.Hide()
        self.SetSizer(layout)
        apply_native_style(self)
        self.FitInside()

    def ShowProgress(self):
        self.progress_panel.Show()
        self.Layout()
        self.FitInside()

    def RefreshSections(self):
        self.result_panel.Show(self.result is not None)
        for control in (self.txt_resources,self.txt_timing,self.txt_job,self.txt_analysis,self.txt_pitch,self.txt_log):
            control.Show(bool(control.GetValue()))
        self.Layout()
        self.FitInside()

    def OnAdvanced(self, event):
        enabled = self.advanced_toggle.GetValue()
        self.advanced_toggle.SetLabel("Gelişmiş eğitim ayarları [AÇIK]" if enabled else "Gelişmiş eğitim ayarları [KAPALI]")
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
                self.RefreshSources()
                if self.sources: self.source_list.SetFocus()

    def OnRemove(self, event):
        selected = self.source_list.GetSelection()
        if selected != wx.NOT_FOUND:
            self.source_groups.pop(self.sources[selected],None)
            del self.sources[selected]
            self.source_list.Delete(selected)
            self.ClearAnalysis()
        self.RefreshSources()
        (self.source_list if self.sources else self.btn_add).SetFocus()

    def RefreshSources(self):
        selection = self.source_list.GetSelection()
        self.source_list.Show(bool(self.sources))
        self.empty_sources.Show(not self.sources)
        self.btn_remove.Enable(bool(self.sources) and not self.busy)
        self.btn_group.Enable(bool(self.sources) and not self.busy)
        self.group_intro.Show(len(self.sources)>1 or bool(self.source_groups))
        self.btn_group.Show(len(self.sources)>1 or bool(self.source_groups))
        self.Layout()
        self.FitInside()
        self.source_list.Set([f"{i+1}. {Path(source).name}"+(f" | Aynı şarkı: {self.source_groups[source]}" if self.source_groups.get(source) else " | Ayrı kayıt") for i,source in enumerate(self.sources)])
        if 0 <= selection < len(self.sources): self.source_list.SetSelection(selection)
        elif self.sources: self.source_list.SetSelection(0)

    def OnGroup(self,event):
        selected = self.source_list.GetSelection()
        if selected == wx.NOT_FOUND:
            wx.MessageBox("Önce kayıt listesinden eşleştirilecek ses kaydını seçin.","Ses kaydı seçilmedi",wx.OK | wx.ICON_INFORMATION,parent=self)
            return
        source = self.sources[selected]
        with wx.TextEntryDialog(self,"Aynı şarkının farklı kayıtlarına aynı eşleştirme adını verin. Farklı şarkılarda bu alanı boş bırakın.","Aynı şarkının kayıtlarını eşleştir",self.source_groups.get(source,"")) as dialog:
            if dialog.ShowModal()!=wx.ID_OK: return
            group=dialog.GetValue().strip()
        if len(group)>100:
            wx.MessageBox("Eşleştirme adı en fazla 100 karakter olabilir.","Eşleştirme adı",wx.OK | wx.ICON_INFORMATION,parent=self)
            return
        if group: self.source_groups[source]=group
        else: self.source_groups.pop(source,None)
        self.RefreshSources()
        self.ClearAnalysis()
        self.source_list.SetFocus()

    def OnProfile(self,event):
        pass  # Sample rate is read directly by Options; no technical filler field.

    def Options(self):
        def decimal(control, label):
            try:
                return float(control.GetValue().strip().replace(',', '.'))
            except ValueError:
                raise ValueError(f'{label} bir sayı olmalı; örneğin 0.3.')
        try:
            learning_rate = float(self.learning_rate.GetValue().strip().replace(",", "."))
        except ValueError:
            raise ValueError("Öğrenme hızı sayısal olmalı; örneğin 0.0001.")
        return TrainingOptions(name=self.model_name.GetValue().strip(), sources=tuple(self.sources),
                               sample_rate=(32000, 40000, 48000)[self.sample_rate.GetSelection()],
                               epochs=self.epochs.GetValue(), batch_size=self.batch.GetValue(),
                               save_every=self.interval.GetValue(), learning_rate=learning_rate,
                               segment_seconds=decimal(self.segment,'Ses parçası süresi'), overlap_seconds=decimal(self.overlap,'Ortak süre'),
                               holdout_fraction=self.holdout.GetValue()/100, cpu_threads=self.threads.GetValue(),
                               f0_method=("rmvpe", "crepe", "crepe-tiny")[self.f0.GetSelection()],
                               checkpointing=self.checkpointing.GetValue(),
                               source_groups=tuple(self.source_groups.get(source,"") for source in self.sources) if self.source_groups else ()).validate()

    def EnableUI(self, enable):
        self.busy = not enable
        for control in (self.source_list, self.btn_add, self.btn_remove, self.model_name, self.sample_rate,
                        self.epochs, self.batch, self.interval, self.advanced_toggle, self.advanced,
                        self.btn_start, self.btn_resume, self.btn_load, self.btn_group):
            control.Enable(enable)
        self.btn_cancel.Enable(not enable)
        self.btn_force_stop.Disable()
        self.candidate.Enable(enable and self.result is not None)
        self.btn_register.Enable(enable and self.result is not None)
        self.test_mode.Enable(enable and self.result is not None)
        self.btn_listen.Enable(enable and self.result is not None)
        self.btn_remove.Enable(enable and bool(self.sources))
        self.btn_group.Enable(enable and bool(self.sources))
        self.RefreshSections()

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
        self.RefreshSections()

    def ClearAnalysis(self):
        self.analysis_report = None
        self.txt_analysis.Clear()
        self.txt_analysis.Hide()
        self.RefreshSections()

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
        self.RefreshSections()
        self.txt_status.SetValue("Analiz tamamlandı. Uyarıları okuyun; kayıtları dinleyerek kontrol edin.")
        if announce:
            self.NotifyResult(self.txt_status.GetValue(),"Kayıt analizi tamamlandı",self.txt_analysis)

    def NotifyResult(self,message,title,focus=None,error=False):
        """A native focused dialog exposes terminal results to screen readers."""
        self.ShowProgress()
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
            control.SetValue(str(value) if isinstance(control,wx.TextCtrl) else value)
        self.learning_rate.SetValue(str(options.learning_rate))
        self.f0.SetSelection(("rmvpe","crepe","crepe-tiny").index(options.f0_method))
        self.checkpointing.SetValue(options.checkpointing)

    def OnLoad(self, event):
        if self.busy:
            return
        with wx.DirDialog(self, "Kayıtlı eğitimin sonuç klasörünü seçin", defaultPath=str(Path(data_directory())/"training_runs")) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            job = Path(dialog.GetPath())
        self.ShowProgress()
        try:
            from training.storage import read_manifest
            for control in (self.txt_resources,self.txt_log,self.txt_pitch,self.txt_analysis):control.Clear()
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
                self.txt_pitch.Clear()
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
        self.ShowProgress()
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
            self.txt_pitch.Clear()
            self.txt_resources.Clear()
            self.txt_log.Clear()
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
        self.ShowProgress()
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
            self.RefreshSections()
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
        self.RefreshSections()

    def OnFinished(self, result, message):
        self.result = result
        self.RefreshSections()
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
