"""UAC-aware native Windows installer launch with a bounded handle lifetime."""
import ctypes
from ctypes import wintypes
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


class InstallerLaunchCancelled(Exception):
    """The user declined Windows' elevation prompt; the application stays open."""


def wait_for_update_launch(process, status_path, *, timeout=1800):
    """Wait off the GUI thread until UAC succeeds; a launch failure keeps wx open."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = json.loads(Path(status_path).read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            status = {}
        if status.get('state') == 'started':
            return True
        if status.get('state') == 'cancelled':
            raise InstallerLaunchCancelled('Windows yönetici izni kullanıcı tarafından iptal edildi.')
        if status.get('state') == 'failed':
            raise RuntimeError(status.get('message') or 'Güncelleme başlatılamadı.')
        if process.poll() is not None:
            raise RuntimeError('Güncelleme yardımcısı başlatılamadı veya beklenmedik biçimde kapandı.')
        time.sleep(.1)
    process.terminate()
    raise TimeoutError('Güncelleme için yönetici onayı bekleme süresi doldu.')


def run_in_place_update(path, package):
    """Hand off to a hidden, non-elevated process before replacing our own EXE."""
    from app_runtime import resource_directory, data_directory
    from app_settings import write_json_atomic
    if os.name != 'nt' or not getattr(sys, 'frozen', False):
        raise RuntimeError('Yerinde güncelleme yalnız kurulu Windows uygulamasında kullanılabilir.')
    executable = Path(sys.executable).resolve()
    if executable.name != 'Ghostkiller_Sound_Cleaner_V2.exe':
        raise RuntimeError('Bu paket yerinde güncelleme için uygun değil.')
    root = Path(path).resolve().parent
    if not root.name.startswith('ghostkiller_update_'):
        raise ValueError('Güncelleme dosyası özel geçici dizinde bulunmalı.')
    script = root/'update_helper.ps1'
    shutil.copyfile(Path(resource_directory())/'update_helper.ps1', script)
    data = Path(data_directory())
    logs = data/'update-logs'
    logs.mkdir(exist_ok=True)
    status = root/'status.json'
    config = root/'job.json'
    arguments = subprocess.list2cmdline([
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/SP-', '/NORESTART', '/RESTARTEXITCODE=3010',
        '/NOCLOSEAPPLICATIONS', '/NORESTARTAPPLICATIONS', '/NOFORCECLOSEAPPLICATIONS',
        f'/DIR={executable.parent}', f'/LOG={logs/(root.name+".log")}', f'/GKUPDATEPID={os.getpid()}',
    ])
    write_json_atomic(str(config), {
        'installer': str(Path(path).resolve()), 'sha256': package.sha256, 'size': package.size,
        'version': package.version, 'backend': package.backend,
        'executable': str(executable), 'parent_pid': os.getpid(), 'arguments': arguments,
        'status': str(status), 'result': str(data/'update-result.json'),
    })
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = [
        str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', str(script), '-JobPath', str(config),
    ]
    environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
    internal = Path(resource_directory()).resolve()
    environment['PATH'] = os.pathsep.join(entry for entry in environment.get('PATH', '').split(os.pathsep)
                                        if entry and not Path(entry).resolve().is_relative_to(internal))
    # System PowerShell must not inherit PyInstaller's private DLL search path.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = [wintypes.DWORD, wintypes.LPWSTR]
    kernel.GetDllDirectoryW.restype = wintypes.DWORD
    kernel.SetDllDirectoryW.argtypes = [wintypes.LPCWSTR]
    kernel.SetDllDirectoryW.restype = wintypes.BOOL
    buffer = ctypes.create_unicode_buffer(kernel.GetDllDirectoryW(0, None) + 1)
    kernel.GetDllDirectoryW(len(buffer), buffer)
    if not kernel.SetDllDirectoryW(None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        process = subprocess.Popen(command, cwd=root, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        kernel.SetDllDirectoryW(buffer.value or None)
    return wait_for_update_launch(process, status)


def hold_installer_file(path):
    """Deny modification/deletion between the final hash and ShellExecuteEx."""
    if os.name != 'nt':
        raise OSError('Kurulum dosyası koruması yalnız Windows üzerinde kullanılabilir.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(os.path.abspath(os.fspath(path)), 0x80000000,
                                0x1, None, 3, 0x80, None)  # READ; share READ only; OPEN_EXISTING
    if handle in (None, ctypes.c_void_p(-1).value):
        raise ctypes.WinError(ctypes.get_last_error())
    class Guard:
        def close(self):
            nonlocal handle
            if handle is not None:
                kernel.CloseHandle(handle)
                handle = None
    return Guard()


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def launch_elevated_installer(path, *, _api=None):
    """ShellExecuteEx's runas verb invokes UAC, unlike CreateProcess/Popen."""
    if _api is None:
        if os.name != "nt":
            raise OSError("Kurulum başlatma yalnız Windows üzerinde kullanılabilir.")
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        ole = ctypes.WinDLL("ole32", use_last_error=True)
        shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
        shell.ShellExecuteExW.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        ole.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        ole.CoInitializeEx.restype = ctypes.c_long
        # Existing wx COM apartment is retained on RPC_E_CHANGED_MODE.
        initialized = ole.CoInitializeEx(None, 2) in (0, 1)
        try:
            return launch_elevated_installer(path, _api=(shell.ShellExecuteExW,
                                                        ctypes.get_last_error,
                                                        kernel.CloseHandle))
        finally:
            if initialized:
                ole.CoUninitialize()
    execute, last_error, close_handle = _api
    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040 | 0x00000100 | 0x00000400  # NOCLOSEPROCESS, NOASYNC, NO_UI
    info.lpVerb = "runas"
    info.lpFile = os.path.abspath(os.fspath(path))
    info.lpDirectory = os.path.dirname(info.lpFile)
    info.nShow = 1
    if not execute(ctypes.byref(info)):
        error = last_error()
        if error == 1223:  # ERROR_CANCELLED
            raise InstallerLaunchCancelled("Windows yönetici izni kullanıcı tarafından iptal edildi.")
        raise OSError(error, f"Windows kurulum sürecini başlatamadı (hata {error}).")
    if info.hProcess:
        close_handle(info.hProcess)
    return True
