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
import sys
import json
import urllib.request
import tempfile
import subprocess
import threading

CURRENT_VERSION = "2.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/YasinTalhaGencsoy/ghostkiller_sound_toolbox/main/version.json"


def parse_version(v_str):
    """'2.1.0' gibi sürüm dizgilerini karşılaştırma için sayı demetine (tuple) çevirir."""
    try:
        parts = [int(p) for p in v_str.strip().lstrip("v").split(".")]
        return tuple(parts)
    except Exception:
        return (0, 0, 0)


def check_for_updates(parent_window, silent=False):
    """
    Güncelleme kontrolü yapar.
    silent=True ise sadece yeni sürüm varsa kullanıcıyı uyarır (açılış kontrolü için).
    silent=False ise güncel olma durumunda da bilgi kutusu gösterir (menüden tıklanma için).
    """
    def _do_check():
        try:
            req = urllib.request.Request(
                UPDATE_URL,
                headers={"User-Agent": "Ghostkiller-Sound-Toolbox-Updater"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            remote_ver_str = data.get("version", CURRENT_VERSION)
            remote_ver = parse_version(remote_ver_str)
            curr_ver = parse_version(CURRENT_VERSION)

            if remote_ver > curr_ver:
                wx.CallAfter(_show_update_dialog, parent_window, data)
            else:
                if not silent:
                    wx.CallAfter(
                        wx.MessageBox,
                        f"Programınız güncel (v{CURRENT_VERSION}).\nEn son sürümdesiniz.",
                        "Güncelleme Kontrolü",
                        wx.OK | wx.ICON_INFORMATION
                    )
        except Exception as e:
            if not silent:
                wx.CallAfter(
                    wx.MessageBox,
                    "Güncelleme sunucusuna bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.\n\n"
                    f"Hata detayı: {str(e)}",
                    "Bağlantı Hatası",
                    wx.OK | wx.ICON_WARNING
                )

    threading.Thread(target=_do_check, daemon=True).start()


def _show_update_dialog(parent_window, data):
    """Yeni sürüm bulunduğunda kullanıcıya sorar ve indirmeyi başlatır."""
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
    temp_dir = tempfile.gettempdir()
    setup_path = os.path.join(temp_dir, "Ghostkiller_V2_Setup.exe")

    progress = wx.ProgressDialog(
        "Güncelleme İndiriliyor",
        "Ghostkiller Sound Cleaner V2 güncel kurulum dosyası indiriliyor...\nLütfen bekleyin.",
        maximum=100,
        parent=parent_window,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT
    )

    def _download():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Ghostkiller-Sound-Toolbox-Updater"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(setup_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            wx.CallAfter(progress.Update, min(pct, 99), f"İndiriliyor: %{pct}")

            wx.CallAfter(progress.Destroy)
            wx.CallAfter(_launch_setup_and_exit, setup_path)

        except Exception as e:
            wx.CallAfter(progress.Destroy)
            wx.CallAfter(
                wx.MessageBox,
                f"Güncelleme dosyası indirilemedi:\n{str(e)}",
                "İndirme Hatası",
                wx.OK | wx.ICON_ERROR
            )

    threading.Thread(target=_download, daemon=True).start()


def _launch_setup_and_exit(setup_path):
    """İndirilen kurulum dosyasını çalıştırır ve mevcut uygulamayı kapatır."""
    try:
        subprocess.Popen([setup_path], shell=True)
        wx.MessageBox(
            "Güncelleme indirildi! Şimdi kurulum başlayacak ve program kapanacak.",
            "Güncelleme Hazır",
            wx.OK | wx.ICON_INFORMATION
        )
        wx.GetApp().ExitMainLoop()
    except Exception as e:
        wx.MessageBox(
            f"Kurulum dosyası başlatılamadı:\n{str(e)}",
            "Kurulum Hatası",
            wx.OK | wx.ICON_ERROR
        )
