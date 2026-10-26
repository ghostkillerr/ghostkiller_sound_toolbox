"""Accessible, explicitly started live RVC monitoring controls."""
from dataclasses import asdict
import math
import threading

import wx

from app_runtime import JOB_LOCK, append_log, finish_job, post_ui
from audio_service import NativeAudioSession
from live_audio import AudioDevice, enumerate_devices
from live_cover import LiveOptions
from live_gate import (CalibrationOptions, HYSTERESIS_DB, ATTACK_MS, HOLD_MS,
                       RELEASE_MS, validate_gate)
from ui_common import add_intro, apply_native_style, checkbox_control, explanation_control, name_control, fold_controls, request_field
from ui_operation import OperationPreparation, operation_error


class LiveCoverPanel(wx.ScrolledWindow):
    def __init__(self, parent, settings, models=None):
        super().__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.SetScrollRate(0, 20)
        self.settings = settings
        self.models = {}
        self.model_names = []
        self.devices = {'inputs': [AudioDevice(-1, 'Windows varsayılan aygıtı')],
                        'outputs': [AudioDevice(-1, 'Windows varsayılan aygıtı')]}
        self.busy = False
        self.calibrating = False
        self._calibrated_input = None
        self.stop_requested = threading.Event()
        self.force_requested = threading.Event()
        self.audio_session = None
        self.audio_session_factory = NativeAudioSession
        self._gate_lock = threading.Lock()
        self._live_gate = (True, -45.)
        self._microphone_announced = False
        layout = wx.BoxSizer(wx.VERTICAL)

        def field(label, control):
            # Native labels immediately precede their controls in tab order.
            layout.Add(wx.StaticText(self, label=label), 0, wx.LEFT | wx.TOP, 8)
            control = control()
            name_control(control, label)
            layout.Add(control, 0, wx.EXPAND | wx.ALL, 8)
            return control

        self.help = explanation_control(self, 'Canlı dinleme açıklaması',
            'Mikrofon sesinizi seçtiğiniz ses modeliyle dönüştürüp kulaklığınızdan dinleyin. '
            'Yankı ve ıslık oluşmaması için kulaklık kullanın. '
            'Bu özellik deneyseldir; duyduğunuz ses donanıma göre gecikir. Ses dosyaya kaydedilmez.')
        layout.Add(self.help, 0, wx.EXPAND | wx.ALL, 8)
        self.model_choice = field('Kullanılacak ses modeli', lambda: wx.Choice(self))
        row = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_models = wx.Button(self, label='Model listesini yenile')
        self.btn_models.Bind(wx.EVT_BUTTON, lambda event: getattr(self.settings, 'refresh_cover', self.RefreshModels)())
        row.Add(self.btn_models, 0, wx.ALL, 4)
        self.btn_add_model = wx.Button(self, label='Ses modeli ekle')
        self.btn_add_model.Bind(wx.EVT_BUTTON, lambda event: getattr(self.settings, 'add_model', getattr(self.settings, 'open_cover', lambda: None))())
        row.Add(self.btn_add_model, 0, wx.ALL, 4)
        layout.Add(row, 0, wx.EXPAND | wx.LEFT, 4)
        self.input_choice = field('Mikrofon', lambda: wx.Choice(self))
        self.input_choice.Bind(wx.EVT_CHOICE, self.OnInputChange)
        self.output_choice = field('Dinleme aygıtı / kulaklık', lambda: wx.Choice(self))
        self.btn_devices = wx.Button(self, label='Ses aygıtlarını yenile')
        self.btn_devices.Bind(wx.EVT_BUTTON, lambda event: self.RefreshDevices())
        layout.Add(self.btn_devices, 0, wx.ALL, 8)
        self.pitch = field('Ses tonu (yarım ses): 0 değişmez; + inceltir, − kalınlaştırır',
                           lambda: wx.SpinCtrl(self, min=-24, max=24, initial=0))
        self.index_rate = field('Index katkısı (0–1); benzerlik puanı değildir',
                                lambda: wx.TextCtrl(self, value='0.75'))
        self.f0_choice = field('Perde belirleme yöntemi', lambda: wx.Choice(self, choices=['rmvpe', 'crepe']))
        self.f0_choice.SetSelection(0)
        self.f0_choice.Bind(wx.EVT_CHOICE, lambda event: self.preparation.RefreshReadiness())
        self.block = field('Ses parçası süresi', lambda: wx.Choice(self, choices=['250 ms', '500 ms', '1000 ms']))
        self.block.SetSelection(1)
        text = explanation_control(self, 'Gecikme açıklaması',
            'Kısa parçalar daha sık dönüştürme gerektirir. Duyulan toplam gecikme parça süresinden uzundur. '
            'İşlemci yetişemiyorsa 1000 ms veya Ayarlar’dan ekran kartını seçin.')
        layout.Add(text, 0, wx.EXPAND | wx.ALL, 8)
        self.gate_enabled = checkbox_control(
            wx.CheckBox(self, label='Ses eşiğini uygula; sessizken dönüştürmeyi beklet'))
        self.gate_enabled.SetValue(True)
        self.gate_enabled.Bind(wx.EVT_CHECKBOX, self.OnGateChange)
        layout.Add(self.gate_enabled, 0, wx.ALL, 8)
        self.gate_db = field('Ses eşiği (dB, en fazla 0; alt sınır yok)', lambda: wx.TextCtrl(self, value='-45'))
        self.gate_db.Bind(wx.EVT_TEXT, self.OnGateChange)
        gate_help = explanation_control(self, 'Ses eşiği açıklaması',
            'Eşik altındaki dip sesi yok sayılır ve sessiz parçalarda ses modeli çalıştırılmaz. '
            '-35 dB daha fazla sesi keser, -60 dB daha hassastır. Dinlerken değiştirebilirsiniz.')
        layout.Add(gate_help, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_calibrate = wx.Button(self, label='Otomatik ayarla (10 saniye sessizlik)')
        self.btn_calibrate.Bind(wx.EVT_BUTTON, self.OnCalibrate)
        layout.Add(self.btn_calibrate, 0, wx.ALL, 8)
        self.txt_calibration = name_control(wx.TextCtrl(self,
            value='Mikrofonu seçin ve otomatik ayara basın. 10 saniye konuşmayın. Ölçüm bitince mikrofon kapanır.',
            style=wx.TE_READONLY), 'Otomatik ses eşiği ayarı durumu')
        layout.Add(self.txt_calibration, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_gate_profile = name_control(wx.TextCtrl(self, style=wx.TE_READONLY), 'Gate açılma ve kapanma ayarları')
        layout.Add(self.txt_gate_profile, 0, wx.EXPAND | wx.ALL, 8)
        self.UpdateGateProfile()
        self.gain = field('Dinleme ses düzeyi (yüzde)', lambda: wx.SpinCtrl(self, min=10, max=100, initial=50))
        self.preparation = OperationPreparation(self, settings, self.RequiredModels, summary=self.Summary)
        layout.Add(self.preparation, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_hardware = wx.Button(self, label='İşlem donanımını Ayarlar’da seç')
        self.btn_hardware.Bind(wx.EVT_BUTTON, lambda event: self.settings.open_settings())
        layout.Add(self.btn_hardware, 0, wx.ALL, 8)
        actions = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_start = wx.Button(self, label='Canlı dinlemeyi başlat')
        self.btn_stop = wx.Button(self, label='Canlı dinlemeyi durdur')
        self.btn_force_stop = wx.Button(self, label='Zorla durdur')
        self.btn_start.Bind(wx.EVT_BUTTON, self.OnStart)
        self.btn_stop.Bind(wx.EVT_BUTTON, self.OnStop)
        self.btn_force_stop.Bind(wx.EVT_BUTTON, self.OnForceStop)
        for button in (self.btn_start, self.btn_stop, self.btn_force_stop):
            actions.Add(button, 0, wx.ALL, 8)
        layout.Add(actions, 0, wx.EXPAND)
        self.txt_status = name_control(wx.TextCtrl(self, value='Modeli, mikrofonu ve kulaklığı seçin.',
                                                  style=wx.TE_READONLY), 'Canlı dinleme durumu ve gecikme')
        layout.Add(self.txt_status, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_route = name_control(wx.TextCtrl(self, value='Mikrofon → RVC ses modeli → seçilen çıkış',
                                                 style=wx.TE_READONLY), 'Doğrulanmış ses yolu')
        layout.Add(self.txt_route, 0, wx.EXPAND | wx.ALL, 8)
        self.txt_log = name_control(wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE),
                                    'Canlı dinleme günlüğü')
        layout.Add(self.txt_log, 1, wx.EXPAND | wx.ALL, 8)
        # Keep preparation, calibration and listening on the basic path.
        advanced_controls = [self.index_rate.GetPrevSibling(), self.index_rate,
            self.f0_choice.GetPrevSibling(), self.f0_choice, self.block.GetPrevSibling(), self.block,
            text, self.gate_enabled, self.gate_db.GetPrevSibling(), self.gate_db, gate_help, self.txt_gate_profile]
        self.advanced = wx.Panel(self, style=wx.TAB_TRAVERSAL)
        advanced_layout = wx.BoxSizer(wx.VERTICAL)
        for control in advanced_controls:
            layout.Detach(control)
            control.Reparent(self.advanced)
            advanced_layout.Add(control, 0, wx.EXPAND | wx.ALL, 6)
        self.advanced.SetSizer(advanced_layout)
        self.advanced.Hide()
        self.advanced_toggle = wx.ToggleButton(self, label='Gelişmiş canlı ses ayarları [KAPALI]')
        self.advanced_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnAdvanced)
        layout.Add(self.advanced_toggle, 0, wx.ALL, 8)
        layout.Add(self.advanced, 0, wx.EXPAND | wx.ALL, 4)
        from ui_help import add_help
        add_help(self, layout, 'Canlı AI Cover')
        self.log_toggle = fold_controls(self, layout, [self.txt_log, self.txt_route], 'Ses yolu ve günlüğü göster')
        self.btn_start._ui_primary = True
        self.SetSizer(layout)
        add_intro(self, layout, 'Canlı AI Cover', 'Kendi sesinizi başka bir ses modeliyle canlı dinleyin.')
        self.RefreshModels(models)
        self.RefreshDevices()
        self.EnableUI(True)
        apply_native_style(self)
        self.FitInside()

    def OnAdvanced(self, event):
        shown = self.advanced_toggle.GetValue()
        self.advanced.Show(shown)
        self.advanced_toggle.SetLabel('Gelişmiş canlı ses ayarları ' + ('[AÇIK]' if shown else '[KAPALI]'))
        self.Layout()
        self.FitInside()

    def Summary(self):
        device = 'Ekran kartı' if getattr(self.settings, 'preference', 'cpu') == 'gpu' else 'İşlemci'
        report = getattr(self.settings, 'report', None)
        if report is not None:
            try:
                device += ': '+report.selected(self.settings.preference).name
            except RuntimeError:
                device += ' kullanılamıyor; Ayarlar’dan donanımı denetleyin'
        return f'Canlı dinleme · {device} · Dosyaya kayıt yapılmaz'

    def RequiredModels(self):
        return ['contentvec'] + (['rmvpe'] if self.f0_choice.GetSelection() == 0 else [])

    def RefreshModels(self, models=None):
        if self.busy:
            return
        from ui_cover import get_app_dir, load_models
        selected = self.model_choice.GetStringSelection()
        self.models = {name: dict(value) for name, value in
                       (load_models(get_app_dir()) if models is None else models).items()}
        self.model_names = list(self.models)
        self.model_choice.Set(self.model_names)
        if selected in self.model_names:
            self.model_choice.SetSelection(self.model_names.index(selected))
        elif self.model_names:
            self.model_choice.SetSelection(0)

    def RefreshDevices(self):
        if self.busy or JOB_LOCK.locked():
            return
        try:
            devices = enumerate_devices()
            missing = False
            for key, control in (('inputs', self.input_choice), ('outputs', self.output_choice)):
                selection = control.GetSelection()
                current = control.GetClientData(selection) if selection != wx.NOT_FOUND else AudioDevice(-1, 'Windows varsayılan aygıtı')
                control.Clear()
                for device in devices[key]:
                    # Native item data moves with the label even if Windows sorts it.
                    control.Append(device.name, device)
                selected = wx.NOT_FOUND
                for index in range(control.GetCount()):
                    device = control.GetClientData(index)
                    if device == current or (device.id == -1 and current.id == -1):
                        selected = index
                        break
                control.SetSelection(selected)
                missing |= selected == wx.NOT_FOUND
            self.devices = devices
            self.OnInputChange(None)
            if missing:
                self.txt_status.SetValue('Seçilen ses aygıtı artık bulunamıyor. Mikrofonu ve çıkışı yeniden seçin; varsayılana geçilmedi.')
        except Exception as error:
            for key, control in (('inputs', self.input_choice), ('outputs', self.output_choice)):
                if control.GetCount() == 0:
                    for device in self.devices[key]:
                        control.Append(device.name, device)
                    control.SetSelection(0)
            self.txt_status.SetValue(operation_error(error))

    def SelectedDevice(self, control):
        selection = control.GetSelection()
        if selection == wx.NOT_FOUND:
            raise ValueError('Mikrofon ve dinleme çıkışını yeniden seçin; seçilen aygıt bulunamıyor.')
        device = control.GetClientData(selection)
        if not isinstance(device, AudioDevice):
            raise ValueError('Ses aygıtı seçimi geçersiz; aygıt listesini yenileyin.')
        return device

    def EnableUI(self, enable):
        self.busy = not enable
        if enable:
            self.calibrating = False
        for control in (self.model_choice, self.btn_models, self.btn_add_model, self.input_choice,
                        self.output_choice, self.btn_devices, self.pitch, self.index_rate,
                        self.f0_choice, self.block, self.gain, self.btn_start, self.btn_hardware, self.btn_calibrate):
            control.Enable(enable)
        self.gate_enabled.Enable(not self.calibrating)
        self.gate_db.Enable(not self.calibrating and self.gate_enabled.GetValue())
        self.btn_stop.SetLabel('Ölçümü iptal et' if self.calibrating else 'Canlı dinlemeyi durdur')
        self.btn_stop.Enable(not enable)
        self.btn_force_stop.Disable()

    def Options(self):
        from ui_cover import get_app_dir, resolve_model_file_path
        index = self.model_choice.GetSelection()
        if index == wx.NOT_FOUND:
            raise ValueError('Önce bir ses modeli seçin. Ses modeli ekle düğmesiyle dosyanızı ekleyebilirsiniz.')
        record = dict(self.models[self.model_names[index]])
        input_device, output_device = self.SelectedDevice(self.input_choice), self.SelectedDevice(self.output_choice)
        if self._calibrated_input and input_device.id == -1:
            # A measured Windows default is pinned to the microphone actually measured.
            input_device = self._calibrated_input
        try:
            ratio = float(self.index_rate.GetValue().strip().replace(',', '.'))
        except ValueError:
            raise ValueError('Index katkısı 0 ile 1 arasında olmalı.')
        return LiveOptions(
            model_path=resolve_model_file_path(get_app_dir(), record['pth']),
            index_path=resolve_model_file_path(get_app_dir(), record.get('index', '')),
            input_device=input_device.id, output_device=output_device.id,
            input_name=input_device.name if input_device.id >= 0 else '',
            output_name=output_device.name if output_device.id >= 0 else '',
            pitch=self.pitch.GetValue(), index_rate=ratio, f0_method=self.f0_choice.GetStringSelection(),
            block_seconds=(.25, .5, 1.)[self.block.GetSelection()], gain=self.gain.GetValue()/100,
            gate_enabled=self.gate_enabled.GetValue(), gate_db=self.GateThreshold(),
            device=self.settings.prepare_job(self.RequiredModels())).validate()

    def OnStart(self, event):
        if not self.busy and self.model_choice.GetSelection() == wx.NOT_FOUND:
            request_field(self, 'Ses modeli ekleyin veya listeden bir model seçin.', self.btn_add_model)
            return
        if self.busy or not JOB_LOCK.acquire(blocking=False):
            self.txt_status.SetValue('Başka bir işlem sürüyor. Bitmesini bekleyin.')
            return
        try:
            self.calibrating = False
            options = self.Options()  # Freeze every control value before starting a worker.
            self.stop_requested.clear()
            self.force_requested.clear()
            self._live_gate = (options.gate_enabled, options.gate_db)
            self._microphone_announced = False
            self.txt_log.Clear()
            self.txt_route.SetValue(f'Giriş: {options.input_name or "Windows varsayılanı"} → RVC → çıkış: '
                                    f'{options.output_name or "Windows varsayılanı"} (açılışta doğrulanacak)')
            self.EnableUI(False)
            self.txt_status.SetValue('Ses modeli hazırlanıyor...')
            if self._calibrated_input is not None:
                self.txt_calibration.SetValue('Ölçülen gate ayarı bu mikrofon için kullanılıyor.')
            threading.Thread(target=self.Run, args=(options,), name='live-cover-controller', daemon=True).start()
        except Exception as error:
            self.EnableUI(True)
            JOB_LOCK.release()
            self.txt_status.SetValue(operation_error(error))
            wx.MessageBox(operation_error(error), 'Canlı dinleme başlatılamadı', wx.OK | wx.ICON_WARNING, parent=self)

    def OnCalibrate(self, event):
        if self.busy or not JOB_LOCK.acquire(blocking=False):
            self.txt_status.SetValue('Ölçüm için canlı dinlemeyi veya diğer işlemi durdurun.')
            return
        try:
            device = self.SelectedDevice(self.input_choice)
            options = CalibrationOptions(device.id, device.name if device.id >= 0 else '').validate()
            self.stop_requested.clear()
            self.force_requested.clear()
            self._microphone_announced = False
            self.txt_log.Clear()
            self.calibrating = True
            self.EnableUI(False)
            self.txt_status.SetValue('Mikrofon ölçüm için açılıyor...')
            self.txt_calibration.SetValue('Konuşmayın. Mikrofon açıldıktan sonra 10 saniye ölçülecek.')
            self.txt_route.SetValue('Gürültü ölçümü: yalnız seçilen mikrofon; dinleme çıkışı kapalı.')
            threading.Thread(target=self.RunCalibration, args=(options,), name='gate-calibration-controller', daemon=True).start()
        except Exception as error:
            self.EnableUI(True)
            JOB_LOCK.release()
            self.txt_status.SetValue(operation_error(error))
            self.txt_calibration.SetValue(operation_error(error))

    def RunCalibration(self, options):
        result, failed = None, False
        message = 'Otomatik eşik ayarı iptal edildi; önceki eşik korundu.'
        try:
            if self.stop_requested.is_set():
                raise InterruptedError(message)
            with self.audio_session_factory() as session:
                with self._gate_lock:
                    self.audio_session = session
                try:
                    if self.force_requested.is_set():
                        session.request_force_stop()
                    result = session.execute('calibrate_gate', asdict(options),
                        cancelled=self.stop_requested.is_set, progress=self.ReportCalibration)
                finally:
                    with self._gate_lock:
                        self.audio_session = None
        except InterruptedError:
            result = None
        except Exception as error:
            result, message, failed = None, operation_error(error), True
        finally:
            # The session and native microphone are closed before announcing success.
            post_ui(self, self.OnCalibrationFinished, options, result, message, failed)
            finish_job(self)

    def ReportCalibration(self, text):
        self.Report(text)
        if not text.startswith('Mikrofon açıldı.'):
            post_ui(self, self.txt_calibration.SetValue, text)

    def OnCalibrationFinished(self, options, result, message, failed):
        applied = False
        if not failed and result is not None and not self.stop_requested.is_set():
            try:
                threshold = result['threshold_db']
                validate_gate(True, threshold)
                device = AudioDevice(result['input_device'], result['input_name'])
                CalibrationOptions(device.id, device.name).validate()
                noise = result['noise_db']
                if type(noise) not in (int, float) or not math.isfinite(noise):
                    raise ValueError('Geçersiz mikrofon ölçümü; önceki eşik korundu.')
                self.gate_enabled.SetValue(True)
                self.gate_db.SetValue(f'{threshold:g}')
                self._live_gate = (True, threshold)
                self._calibrated_input = device
                for index in range(self.input_choice.GetCount()):
                    if self.input_choice.GetClientData(index) == device:
                        self.input_choice.SetSelection(index)
                        break
                self.UpdateGateProfile()
                message = (f'Ayarlandı. Mikrofon kapatıldı. Ortam {noise:.1f} dB; '
                           f'açılma {threshold:g} dB, kapanma {threshold-HYSTERESIS_DB:g} dB. '
                           'Canlı dinlemeyi ayrıca başlatabilirsiniz.')
                applied = True
            except (KeyError, TypeError, ValueError) as error:
                message, failed = operation_error(error), True
        self.txt_calibration.SetValue(message)
        self.txt_status.SetValue(message)
        self.txt_route.SetValue('Mikrofon kapalı; dinleme çıkışı kapalı.')
        if failed:
            wx.MessageBox(message, 'Otomatik eşik ayarlanamadı', wx.OK | wx.ICON_WARNING, parent=self)
        elif applied:
            wx.MessageBox('10 saniyelik ortam dinlemesi tamamlandı.\n\n'+message,
                          'Dinleme tamamlandı', wx.OK | wx.ICON_INFORMATION, parent=self)

    def GateThreshold(self):
        try:
            threshold = float(self.gate_db.GetValue().strip().replace(',', '.'))
        except ValueError:
            raise ValueError('Ses eşiğini dB olarak yazın; örneğin -45 veya -100. Alt sınır yoktur.')
        validate_gate(True, threshold)
        return threshold

    def UpdateGateProfile(self):
        try:
            threshold = self.GateThreshold()
        except ValueError as error:
            self.txt_gate_profile.SetValue(str(error))
            return
        self.txt_gate_profile.SetValue(
            f'Açılma {threshold:g} dB; kapanma {threshold-HYSTERESIS_DB:g} dB; '
            f'açılma süresi {ATTACK_MS} ms; bekleme {HOLD_MS} ms; kapanma {RELEASE_MS} ms.')

    def OnInputChange(self, event):
        if self._calibrated_input is None:
            return
        selected = self.input_choice.GetSelection()
        device = self.input_choice.GetClientData(selected) if selected != wx.NOT_FOUND else None
        if device != self._calibrated_input:
            self._calibrated_input = None
            self.gate_db.SetValue('-45')
            self.OnGateChange(None)
            self.txt_calibration.SetValue('Mikrofon değişti. Otomatik ayarı bu mikrofonla yeniden yapın; varsayılan eşik -45 dB.')

    def Run(self, options):
        message, failed = 'Canlı dinleme durduruldu.', False
        try:
            if self.stop_requested.is_set():
                raise InterruptedError(message)
            with self.audio_session_factory() as session:
                with self._gate_lock:
                    session.set_live_gate(*self._live_gate)
                    self.audio_session = session
                try:
                    if self.force_requested.is_set():
                        session.request_force_stop()
                    session.execute('live_cover', {'device': options.device, 'options': asdict(options)},
                                    cancelled=self.stop_requested.is_set, progress=self.Report)
                finally:
                    with self._gate_lock:
                        self.audio_session = None
        except InterruptedError:
            pass
        except Exception as error:
            message, failed = operation_error(error), True
        finally:
            self.audio_session = None
            post_ui(self, self.OnFinished, message, failed)
            finish_job(self)

    def Report(self, text):
        if text.startswith('Mikrofon açıldı.'):
            post_ui(self, self.OnMicrophoneOpened, text)
        else:
            post_ui(self, self.txt_status.SetValue, text)

    def OnMicrophoneOpened(self, text):
        self.txt_status.SetValue('Mikrofon açıldı.')
        self.txt_route.SetValue(text.removeprefix('Mikrofon açıldı.').strip())
        if not self._microphone_announced:
            append_log(self, 'Mikrofon açıldı.')
            self._microphone_announced = True

    def OnGateChange(self, event):
        if self.calibrating or (self.busy and self.stop_requested.is_set()):
            return
        enabled = self.gate_enabled.GetValue()
        self.gate_db.Enable(enabled)
        self.UpdateGateProfile()
        try:
            threshold = self.GateThreshold()
        except ValueError:
            return  # Partially typed values keep the last valid live setting.
        with self._gate_lock:
            self._live_gate = (enabled, threshold)
            if self.audio_session is not None:
                try:
                    self.audio_session.set_live_gate(enabled, threshold)
                except Exception as error:
                    self.txt_status.SetValue(operation_error(error))

    def OnFinished(self, message, failed):
        self.txt_status.SetValue(message)
        if failed:
            wx.MessageBox(message, 'Canlı dinleme durdu', wx.OK | wx.ICON_WARNING, parent=self)

    def OnStop(self, event):
        self.stop_requested.set()
        self.btn_stop.Disable()
        self.btn_force_stop.Enable()
        self.gate_enabled.Disable()
        self.gate_db.Disable()
        self.txt_status.SetValue('Ölçüm iptal ediliyor; mikrofon kapatılıyor...' if self.calibrating else 'Canlı dinleme durduruluyor...')

    def OnForceStop(self, event):
        self.stop_requested.set()
        self.force_requested.set()
        if self.audio_session is not None:
            self.audio_session.request_force_stop()
        self.btn_force_stop.Disable()
