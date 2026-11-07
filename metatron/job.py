from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class JobAccounting:
    total_processes: int = 0
    active_processes: int = 0
    total_user_time_100ns: int = 0
    total_kernel_time_100ns: int = 0


@dataclass(slots=True)
class JobMemoryAccounting:
    peak_process_mib: float = 0.0
    peak_job_mib: float = 0.0


class WindowsJob:
    """Own a Windows Job Object with kill-on-close semantics.

    No commit/memory hard limit is applied: accelerator runtimes can reserve
    large address spaces and the product uses measured admission control instead.
    """

    def __init__(self, name: str | None = None) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows Job Objects require Windows")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._k32 = k32
        handle = k32.CreateJobObjectW(None, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = handle
        self._configure_kill_on_close()

    def _configure_kill_on_close(self) -> None:
        c = self._ctypes
        wt = self._wintypes

        class IO_COUNTERS(c.Structure):
            _fields_ = [
                ("ReadOperationCount", c.c_ulonglong), ("WriteOperationCount", c.c_ulonglong),
                ("OtherOperationCount", c.c_ulonglong), ("ReadTransferCount", c.c_ulonglong),
                ("WriteTransferCount", c.c_ulonglong), ("OtherTransferCount", c.c_ulonglong),
            ]

        class BASIC_LIMIT(c.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", c.c_longlong), ("PerJobUserTimeLimit", c.c_longlong),
                ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", c.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD),
            ]

        class EXTENDED_LIMIT(c.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9
        info = EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self._k32.SetInformationJobObject(
            self.handle, JobObjectExtendedLimitInformation, c.byref(info), c.sizeof(info)
        ):
            err = c.get_last_error(); self.close(); raise c.WinError(err)

    def assign_pid(self, pid: int) -> None:
        c = self._ctypes
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = self._k32.OpenProcess(
            PROCESS_SET_QUOTA | PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION,
            False, int(pid),
        )
        if not h:
            raise c.WinError(c.get_last_error())
        try:
            if not self._k32.AssignProcessToJobObject(self.handle, h):
                raise c.WinError(c.get_last_error())
        finally:
            self._k32.CloseHandle(h)

    def accounting(self) -> JobAccounting:
        c = self._ctypes
        wt = self._wintypes

        class BASIC_ACCOUNTING(c.Structure):
            _fields_ = [
                ("TotalUserTime", c.c_longlong), ("TotalKernelTime", c.c_longlong),
                ("ThisPeriodTotalUserTime", c.c_longlong), ("ThisPeriodTotalKernelTime", c.c_longlong),
                ("TotalPageFaultCount", wt.DWORD), ("TotalProcesses", wt.DWORD),
                ("ActiveProcesses", wt.DWORD), ("TotalTerminatedProcesses", wt.DWORD),
            ]

        JobObjectBasicAccountingInformation = 1
        info = BASIC_ACCOUNTING()
        if not self._k32.QueryInformationJobObject(
            self.handle, JobObjectBasicAccountingInformation, c.byref(info), c.sizeof(info), None
        ):
            raise c.WinError(c.get_last_error())
        return JobAccounting(
            total_processes=int(info.TotalProcesses), active_processes=int(info.ActiveProcesses),
            total_user_time_100ns=int(info.TotalUserTime), total_kernel_time_100ns=int(info.TotalKernelTime),
        )


    def peak_memory(self) -> JobMemoryAccounting:
        """OS-maintained peak private commit for processes owned by this job.

        Unlike periodic process-tree sampling this survives short allocation
        spikes between samples, so it is useful corroborating evidence for the
        memory governor and qualification reports.
        """
        c = self._ctypes
        wt = self._wintypes

        class IO_COUNTERS(c.Structure):
            _fields_ = [
                ("ReadOperationCount", c.c_ulonglong), ("WriteOperationCount", c.c_ulonglong),
                ("OtherOperationCount", c.c_ulonglong), ("ReadTransferCount", c.c_ulonglong),
                ("WriteTransferCount", c.c_ulonglong), ("OtherTransferCount", c.c_ulonglong),
            ]

        class BASIC_LIMIT(c.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", c.c_longlong), ("PerJobUserTimeLimit", c.c_longlong),
                ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
                ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                ("Affinity", c.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD),
            ]

        class EXTENDED_LIMIT(c.Structure):
            _fields_ = [
                ("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
                ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t),
            ]

        JobObjectExtendedLimitInformation = 9
        info = EXTENDED_LIMIT()
        if not self._k32.QueryInformationJobObject(
            self.handle, JobObjectExtendedLimitInformation, c.byref(info), c.sizeof(info), None
        ):
            raise c.WinError(c.get_last_error())
        mib = 1024.0 * 1024.0
        return JobMemoryAccounting(
            peak_process_mib=float(info.PeakProcessMemoryUsed) / mib,
            peak_job_mib=float(info.PeakJobMemoryUsed) / mib,
        )

    def close(self) -> None:
        if getattr(self, "handle", None):
            self._k32.CloseHandle(self.handle)
            self.handle = None

    def __del__(self) -> None:
        try: self.close()
        except Exception: pass


class NullJob:
    def assign_pid(self, pid: int) -> None: return None
    def accounting(self) -> JobAccounting: return JobAccounting()
    def peak_memory(self) -> JobMemoryAccounting: return JobMemoryAccounting()
    def close(self) -> None: return None


def owned_job(name: str | None = None):
    return WindowsJob(name) if os.name == "nt" else NullJob()
