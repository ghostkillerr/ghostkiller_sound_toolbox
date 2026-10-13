# -*- coding: utf-8 -*-
"""
Ghostkiller Sound Cleaner - Otomatik Güncelleme Modülü (updater.py)

Bu modül, programın açılışında veya kullanıcının menüden çağırmasıyla
GitHub üzerindeki version.json dosyasını kontrol eder.
Yeni bir sürüm varsa NVDA / JAWS erişilebilir diyalog ile kullanıcıya bildirir
ve istenirse güncel kurulum (Setup.exe) dosyasını otomatik indirip başlatır.
"""

import wx
import os
import re
import time
import json
import urllib.request
import tempfile
import sys
import threading
from app_runtime import JOB_LOCK
from release_security import (MAX_INSTALLER_BYTES, RELEASE_PAGE, validate_package,
                              validate_response_url, verify_installer)
from windows_installer import InstallerLaunchCancelled, launch_elevated_installer, hold_installer_file

CURRENT_VERSION = "2.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/ghostkillerr/ghostkiller_sound_toolbox/master/version.json"
CHECK_LOCK = threading.Lock()


def runtime_backend():
    """Keep an installed CPU/CUDA/ROCm/XPU package on the same update channel."""
    root = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    info_path = os.path.join(root, 'build-info.json')
    if os.path.isfile(info_path):
        with open(info_path, encoding='utf-8') as stream:
            backend = json.load(stream).get('backend')
        if backend not in {'cpu', 'cuda', 'rocm', 'xpu'}:
            raise ValueError('Paket çalışma ortamı bilgisi geçersiz.')
        return backend
    import torch
    if getattr(torch.version, 'hip', None):
        return 'rocm'
    if getattr(torch.version, 'cuda', None):
        return 'cuda'
    if '+xpu' in torch.__version__:
        return 'xpu'
    return 'cpu'


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+(?:\.\d+)*', value.strip()):
        raise ValueError("Güncelleme sürüm bilgisi geçersiz.")
    parts = [int(p) for p in value.strip().removeprefix('v').split('.')]
    while len(parts) > 3 and parts[-1] == 0:
        parts.pop()
    return tuple(parts + [0] * max(0, 3 - len(parts)))


def parse_version(v_str):
    """'2.1.0' gibi sürüm dizgilerini karşılaştırma için sayı demetine (tuple) çevirir."""
    try:
        return version_parts(v_str)
    except Exception:
        return (0, 0, 0)


def check_for_updates(parent_window, silent=False):
    """
    Güncelleme kontrolü yapar.
    silent=True ise sadece yeni sürüm varsa kullanıcıyı uyarır (açılış kontrolü için).
    silent=False ise güncel olma durumunda da bilgi kutusu gösterir (menüden tıklanma için).
    """
    if not CHECK_LOCK.acquire(blocking=False):
        return

    def deliver(data=None, error=None):
        try:
            if not parent_window or parent_window.IsBeingDeleted():
                return
            if error:
                if not silent:
                    wx.MessageBox(f"Güncelleme kontrol edilemedi:\n{error}", "Güncelleme Hatası", wx.OK | wx.ICON_WARNING)
            elif version_parts(data['version']) > version_parts(CURRENT_VERSION):
                _show_update_dialog(parent_window, data, silent=silent)
            elif not silent:
                wx.MessageBox(f"Programınız güncel (v{CURRENT_VERSION}).", "Güncelleme Kontrolü", wx.OK | wx.ICON_INFORMATION)
        finally:
            CHECK_LOCK.release()

    def _do_check():
        try:
            req = urllib.request.Request(
                UPDATE_URL,
                headers={"User-Agent": "Ghostkiller-Sound-Toolbox-Updater"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = resp.read(65537)
                if len(body) > 65536:
                    raise ValueError('Güncelleme kaydı beklenen boyutu aşıyor.')
                data = json.loads(body.decode("utf-8"))

            if not isinstance(data, dict) or 'version' not in data:
                raise ValueError("Güncelleme kaydı eksik veya geçersiz.")
            version_parts(data['version'])
            wx.CallAfter(deliver, data)
        except Exception as e:
            wx.CallAfter(deliver, None, str(e))

    try:
        threading.Thread(target=_do_check, daemon=True).start()
    except Exception:
        CHECK_LOCK.release()
        raise


def _show_update_dialog(parent_window, data, silent=False):
    """Yeni sürüm bulunduğunda kullanıcıya sorar ve indirmeyi başlatır."""
    if not parent_window or parent_window.IsBeingDeleted():
        return
    if JOB_LOCK.locked():
        if not silent:
            wx.MessageBox(f"v{data['version']} güncellemesi mevcut. Çalışan işlem bittikten sonra tekrar kontrol edin.", "Güncelleme Mevcut", wx.OK | wx.ICON_INFORMATION)
        return
    remote_ver = data.get("version", "Bilinmeyen Sürüm")
    changelog = data.get("changelog", "Yeni geliştirmeler ve hata düzeltmeleri eklendi.")
    try:
        package = validate_package(data, runtime_backend())
    except (ValueError, OSError) as error:
        wx.MessageBox(
            f"v{remote_ver} sürümü bildirildi; doğrulanmış kurulum bilgisi alınamadı:\n{error}\n\n"
            f"Yayınları incelemek için: {RELEASE_PAGE}",
            "Güncelleme Doğrulanamadı", wx.OK | wx.ICON_WARNING
        )
        return

    msg = (
        f"Yeni bir güncelleme mevcut!\n\n"
        f"Mevcut Sürüm: v{CURRENT_VERSION}\n"
        f"Yeni Sürüm: v{remote_ver}\n\n"
        f"Yenilikler:\n{changelog}\n\n"
        "Yeni sürüm kurulum dosyasını şimdi indirip kurmak ister misiniz?"
    )

    dlg = wx.MessageDialog(
        parent_window,
        msg,
        f"Güncelleme Mevcut: v{remote_ver}",
        wx.YES_NO | wx.ICON_QUESTION
    )
    dlg.SetYesNoLabels("Evet (İndir ve Kur)", "Hayır (Sonra)")
    res = dlg.ShowModal()
    dlg.Destroy()

    if res == wx.ID_YES:
        _download_and_run_installer(parent_window, data, backend=package.backend)


def _download_and_run_installer(parent_window, manifest, *, backend=None):
    """Yeni sürüm Setup dosyasını indirir ve başlatır."""
    import shutil
    try:
        package = validate_package(manifest, backend or runtime_backend())
    except (ValueError, OSError) as error:
        wx.MessageBox(f"Güncelleme doğrulanamadı:\n{error}", "Güncelleme Hatası", wx.OK | wx.ICON_ERROR)
        return
    if not JOB_LOCK.acquire(blocking=False):
        wx.MessageBox("Başka bir işlem çalışıyor. Bitmesini bekleyin.", "İşlem Sürüyor", wx.OK | wx.ICON_INFORMATION)
        return
    temp_dir = None
    progress = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="ghostkiller_update_")
        progress = wx.ProgressDialog(
            "Güncelleme İndiriliyor", "Kurulum dosyası indiriliyor...", maximum=100,
            parent=parent_window, style=wx.PD_APP_MODAL | wx.PD_CAN_ABORT
        )
    except Exception:
        JOB_LOCK.release()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    setup_path = os.path.join(temp_dir, "Ghostkiller_V2_Setup.exe")
    cancelled = threading.Event()
    finished = False

    def report(percent):
        if finished:
            return
        if not progress or progress.IsBeingDeleted() or not parent_window or parent_window.IsBeingDeleted():
            cancelled.set()
        elif not (progress.Pulse("İndiriliyor...") if percent is None else progress.Update(percent, f"İndiriliyor: %{percent}"))[0]:
            cancelled.set()

    def finish(error=None):
        nonlocal finished
        if finished:
            return
        # Check a pending cancel click even if the last download chunk was small.
        if not parent_window or parent_window.IsBeingDeleted():
            cancelled.set()
        if not cancelled.is_set():
            report(99)
        finished = True
        if progress and not progress.IsBeingDeleted():
            progress.Destroy()
        JOB_LOCK.release()
        if cancelled.is_set() or error:
            shutil.rmtree(temp_dir, ignore_errors=True)
            if error and not cancelled.is_set() and parent_window and not parent_window.IsBeingDeleted():
                wx.MessageBox(f"Güncelleme dosyası indirilemedi:\n{error}", "İndirme Hatası", wx.OK | wx.ICON_ERROR)
            return
        if not _launch_setup_and_exit(setup_path, package, on_failure=lambda: shutil.rmtree(temp_dir, ignore_errors=True)):
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _download():
        try:
            req = urllib.request.Request(package.url, headers={"User-Agent": "Ghostkiller-Sound-Toolbox-Updater"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                validate_response_url(resp.geturl(), package)
                total_size = int(resp.headers.get("Content-Length", 0))
                if total_size < 0 or total_size > MAX_INSTALLER_BYTES:
                    raise ValueError('Kurulum dosyasının bildirilen boyutu geçersiz.')
                if package.size is not None and total_size and total_size != package.size:
                    raise ValueError('İndirilecek kurulumun boyutu yayın kaydıyla uyuşmuyor.')
                downloaded = 0
                last_percent = -1
                last_report = 0
                chunk_size = 8192

                with open(setup_path, "wb") as f:
                    while True:
                        if cancelled.is_set():
                            break
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > MAX_INSTALLER_BYTES or (package.size is not None and downloaded > package.size):
                            raise ValueError('Kurulum indirmesi izin verilen boyutu aşıyor.')
                        f.write(chunk)
                        pct = min(int((downloaded / total_size) * 100), 99) if total_size > 0 else None
                        now = time.monotonic()
                        if (pct != last_percent or pct is None) and now - last_report >= .1:
                            wx.CallAfter(report, pct)
                            last_percent = pct
                            last_report = now

            if not cancelled.is_set():
                if downloaded == 0 or (total_size and downloaded != total_size):
                    raise RuntimeError("İndirme boş veya eksik.")
                verify_installer(setup_path, package)
            wx.CallAfter(finish)

        except Exception as e:
            wx.CallAfter(finish, str(e))

    try:
        threading.Thread(target=_download, daemon=True).start()
    except Exception as error:
        finish(str(error))


def _launch_setup_and_exit(setup_path, package, *, on_failure=None):
    """Verify large installers off the GUI thread, then request Windows UAC."""
    if not JOB_LOCK.acquire(blocking=False):
        wx.MessageBox("Ses işlemi çalışıyor. Güncellemeyi işlem bittikten sonra tekrar başlatın.", "İşlem Sürüyor", wx.OK | wx.ICON_WARNING)
        return False
    accepted = [True]

    def launch(error=None, guard=None):
        try:
            if error:
                raise RuntimeError(error)
            launch_elevated_installer(setup_path)
            wx.GetApp().ExitMainLoop()
        except InstallerLaunchCancelled as error:
            accepted[0] = False
            wx.MessageBox(str(error), "Kurulum İptal Edildi", wx.OK | wx.ICON_INFORMATION)
        except Exception as error:
            accepted[0] = False
            wx.MessageBox(f"Kurulum dosyası başlatılamadı:\n{error}", "Kurulum Hatası", wx.OK | wx.ICON_ERROR)
        finally:
            if guard:
                guard.close()
            JOB_LOCK.release()
            if not accepted[0] and on_failure:
                on_failure()

    def verify():
        guard = None
        try:
            guard = hold_installer_file(setup_path)
            verify_installer(setup_path, package)
            wx.CallAfter(launch, None, guard)
        except Exception as error:
            wx.CallAfter(launch, str(error), guard)

    try:
        threading.Thread(target=verify, daemon=True).start()
    except Exception as error:
        launch(str(error))
    # True means verification/launch was queued. Success alone closes the app;
    # asynchronous cancellation or failure invokes on_failure and releases lock.
    return accepted[0]
