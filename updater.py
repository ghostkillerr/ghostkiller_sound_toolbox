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
import subprocess
import threading
from urllib.parse import urlsplit
from app_runtime import JOB_LOCK

CURRENT_VERSION = "2.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/ghostkillerr/ghostkiller_sound_toolbox/master/version.json"
CHECK_LOCK = threading.Lock()


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
                data = json.loads(resp.read().decode("utf-8"))

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
    download_url = data.get("download_url", "")

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

    if res == wx.ID_YES and download_url:
        _download_and_run_installer(parent_window, download_url)


def _download_and_run_installer(parent_window, url):
    """Yeni sürüm Setup dosyasını indirir ve başlatır."""
    import shutil
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        wx.MessageBox("Güncelleme bağlantısı geçersiz. HTTPS indirme bağlantısı gerekli.", "Güncelleme Hatası", wx.OK | wx.ICON_ERROR)
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
        if not _launch_setup_and_exit(setup_path):
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _download():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Ghostkiller-Sound-Toolbox-Updater"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
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
                        f.write(chunk)
                        downloaded += len(chunk)
                        pct = min(int((downloaded / total_size) * 100), 99) if total_size > 0 else None
                        now = time.monotonic()
                        if (pct != last_percent or pct is None) and now - last_report >= .1:
                            wx.CallAfter(report, pct)
                            last_percent = pct
                            last_report = now

            if not cancelled.is_set():
                if downloaded == 0 or (total_size and downloaded != total_size):
                    raise RuntimeError("İndirme boş veya eksik.")
                with open(setup_path, "rb") as downloaded_file:
                    if downloaded_file.read(2) != b"MZ":
                        raise RuntimeError("İndirilen dosya Windows kurulum dosyası değil.")
            wx.CallAfter(finish)

        except Exception as e:
            wx.CallAfter(finish, str(e))

    try:
        threading.Thread(target=_download, daemon=True).start()
    except Exception as error:
        finish(str(error))


def _launch_setup_and_exit(setup_path):
    """İndirilen kurulum dosyasını çalıştırır ve mevcut uygulamayı kapatır."""
    try:
        if JOB_LOCK.locked():
            wx.MessageBox("Ses işlemi çalışıyor. Güncellemeyi işlem bittikten sonra tekrar başlatın.", "İşlem Sürüyor", wx.OK | wx.ICON_WARNING)
            return False
        subprocess.Popen([setup_path], shell=False)
        wx.MessageBox(
            "Güncelleme indirildi! Şimdi kurulum başlayacak ve program kapanacak.",
            "Güncelleme Hazır",
            wx.OK | wx.ICON_INFORMATION
        )
        wx.GetApp().ExitMainLoop()
        return True
    except Exception as e:
        wx.MessageBox(
            f"Kurulum dosyası başlatılamadı:\n{str(e)}",
            "Kurulum Hatası",
            wx.OK | wx.ICON_ERROR
        )
        return False
