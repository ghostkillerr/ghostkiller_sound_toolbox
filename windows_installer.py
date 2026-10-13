"""UAC-aware native Windows installer launch with a bounded handle lifetime."""
import ctypes
from ctypes import wintypes
import os


class InstallerLaunchCancelled(Exception):
    """The user declined Windows' elevation prompt; the application stays open."""


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
