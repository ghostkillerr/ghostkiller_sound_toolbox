"""Bounded cleanup for an owned native worker and its child processes.

Windows Job Objects provide lifecycle ownership, not a security sandbox.
POSIX callers launch with start_new_session=True to own a process group.
"""
import os
import subprocess


class NativeProcessGroup:
    def __init__(self):
        self.process = None
        self._handle = None
        self._kernel = None
        self._attached = False

    def spawn(self, command, **kwargs):
        """Own Windows descendants before even a venv redirector can run."""
        if os.name == 'nt':
            kwargs['creationflags'] = kwargs.get('creationflags',0) | 0x00000004  # CREATE_SUSPENDED
        else:
            kwargs['start_new_session'] = True
        process = subprocess.Popen(command,**kwargs)
        try:
            self.attach(process)
            if os.name=='nt' and process.poll() is None:
                self._resume_windows(process.pid)
            return process
        except BaseException:
            try:
                self.terminate(timeout=3.)
            finally:
                self.close()
            raise

    def _resume_windows(self, pid):
        # Popen closes the primary thread handle returned by CreateProcess.
        # The documented Toolhelp API recovers it while the child is suspended.
        import ctypes
        from ctypes import wintypes
        class ThreadEntry(ctypes.Structure):
            _fields_ = [('size',wintypes.DWORD),('usage',wintypes.DWORD),
                        ('thread_id',wintypes.DWORD),('owner_pid',wintypes.DWORD),
                        ('base_priority',wintypes.LONG),('delta_priority',wintypes.LONG),
                        ('flags',wintypes.DWORD)]
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD,wintypes.DWORD]
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for method in ('Thread32First','Thread32Next'):
            function = getattr(kernel,method)
            function.argtypes = [wintypes.HANDLE,ctypes.POINTER(ThreadEntry)]
            function.restype = wintypes.BOOL
        kernel.OpenThread.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenThread.restype = wintypes.HANDLE
        kernel.ResumeThread.argtypes = [wintypes.HANDLE]
        kernel.ResumeThread.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        snapshot = kernel.CreateToolhelp32Snapshot(0x00000004,0)
        if snapshot in (None,ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            present = kernel.Thread32First(snapshot,ctypes.byref(entry))
            while present:
                if entry.owner_pid==pid:
                    thread = kernel.OpenThread(0x0002,False,entry.thread_id)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if kernel.ResumeThread(thread)==0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        kernel.CloseHandle(thread)
                    return
                present = kernel.Thread32Next(snapshot,ctypes.byref(entry))
            raise RuntimeError('Native worker başlangıç thread\'i bulunamadı.')
        finally:
            kernel.CloseHandle(snapshot)

    def attach(self, process):
        if self.process is not None:
            raise RuntimeError("Bir işlem grubu yalnız bir worker'a bağlanabilir.")
        self.process = process
        if process.poll() is not None:
            return self
        try:
            if os.name == "nt":
                self._attach_windows(process)
            elif os.getpgid(process.pid) != process.pid:
                raise RuntimeError("Native worker ayrı bir işlem oturumunda başlatılmalı.")
            self._attached = True
        except BaseException:
            # The worker must not continue without the promised owned lifecycle.
            process.kill()
            try:
                process.wait(timeout=5)
            finally:
                self.close()
            raise
        return self

    def _attach_windows(self, process):
        import ctypes
        from ctypes import wintypes
        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time",ctypes.c_longlong),("job_time",ctypes.c_longlong),
                        ("flags",wintypes.DWORD),("min_working",ctypes.c_size_t),
                        ("max_working",ctypes.c_size_t),("active",wintypes.DWORD),
                        ("affinity",ctypes.c_size_t),("priority",wintypes.DWORD),
                        ("scheduling",wintypes.DWORD)]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name,ctypes.c_ulonglong) for name in
                        ("read_ops","write_ops","other_ops","read_bytes","write_bytes","other_bytes")]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic",BasicLimits),("io",IoCounters),
                        ("process_memory",ctypes.c_size_t),("job_memory",ctypes.c_size_t),
                        ("peak_process_memory",ctypes.c_size_t),("peak_job_memory",ctypes.c_size_t)]
        kernel = ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p,wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE,wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE,wintypes.UINT]
        kernel.TerminateJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self._kernel = kernel
        handle = kernel.CreateJobObjectW(None,None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle,int(process._handle)):
            code = ctypes.get_last_error()
            if process.poll() is None:
                raise RuntimeError(f"Native worker için güvenli işlem ağacı kurulamıyor (Windows hata {code}).")

    def terminate(self, timeout=5.):
        process = self.process
        if process is None:
            return
        if self._handle is not None:
            if not self._kernel.TerminateJobObject(self._handle,1):
                import ctypes
                raise ctypes.WinError(ctypes.get_last_error())
        elif os.name != "nt":
            import signal
            try:
                os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                import signal
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.wait(timeout=timeout)

    def close(self):
        if self._handle is not None:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
        elif os.name != "nt" and self.process is not None and self._attached:
            # Also clean descendants after the worker itself has exited.
            import signal
            try:
                os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process = None
        self._attached = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
