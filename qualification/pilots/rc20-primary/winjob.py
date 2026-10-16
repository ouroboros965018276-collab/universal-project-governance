"""Exact generic local Win32 capability; no CLI business entry copied."""
import ctypes,os
from ctypes import wintypes as W
class Job:
    """Owner-created Win32 job; workers join before the parent sends GO."""
    def __init__(self,name,create=False,memory=0):
        if os.name!='nt':raise RuntimeError('this frozen launch protocol requires Windows')
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        k=self.k
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.OpenJobObjectW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];k.OpenJobObjectW.restype=W.HANDLE
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
        k.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
        k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];k.TerminateJobObject.restype=W.BOOL
        k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
        k.GetCurrentProcess.restype=W.HANDLE
        self.handle=k.CreateJobObjectW(None,name) if create else k.OpenJobObjectW(0x1|0x4,False,name)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        if create:
            class Basic(ctypes.Structure):
                _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',W.DWORD),('min_work',ctypes.c_size_t),('max_work',ctypes.c_size_t),('active_limit',W.DWORD),('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
            class IO(ctypes.Structure):
                _fields_=[(n,ctypes.c_ulonglong) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
            class Extended(ctypes.Structure):
                _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
            info=Extended();info.basic.flags=0x2000|0x200|0x8;info.basic.active_limit=16;info.job_memory=memory
            if not k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):raise ctypes.WinError(ctypes.get_last_error())
    def join(self):
        if not self.k.AssignProcessToJobObject(self.handle,self.k.GetCurrentProcess()):raise ctypes.WinError(ctypes.get_last_error())
    def terminate(self):
        if not self.k.TerminateJobObject(self.handle,97):raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:self.k.CloseHandle(self.handle);self.handle=None
