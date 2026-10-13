"""Resource samples without adding a mandatory GUI dependency."""
import os
import time


def memory_status():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Memory(ctypes.Structure):
            _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
                (key, ctypes.c_ulonglong) for key in
                ("total", "available", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]
        class ProcessMemory(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (key, ctypes.c_size_t) for key in
                ("peak_working", "working", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
        mem, process = Memory(), ProcessMemory()
        mem.length, process.cb = ctypes.sizeof(mem), ctypes.sizeof(process)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(mem)) or not psapi.GetProcessMemoryInfo(
                kernel.GetCurrentProcess(), ctypes.byref(process), process.cb):
            raise OSError("RAM kullanım bilgisi okunamadı.")
        return {"rss_mb": process.working/1024**2, "available_ram_mb": mem.available/1024**2}
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {"rss_peak_mb": peak/(1024**2 if __import__('sys').platform=='darwin' else 1024)}
    except ImportError:
        return {}


class ResourceMonitor:
    def __init__(self, device, emit):
        self.device, self.emit = device, emit
        self.wall, self.cpu = time.monotonic(), time.process_time()
        self.last = 0

    def sample(self, force=False):
        now = time.monotonic()
        if not force and now-self.last < 5:
            return
        values = memory_status()
        values["cpu_percent"] = 100*(time.process_time()-self.cpu)/max(now-self.wall, .001)
        self.wall, self.cpu, self.last = now, time.process_time(), now
        from compute_backend import device_stats
        values.update(device_stats(self.device))
        self.emit("resources", **values)
