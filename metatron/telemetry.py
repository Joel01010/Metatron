from __future__ import annotations

import os
import platform
import threading
import time
from collections import defaultdict, deque
from typing import Any

from .db import Database


def process_rss_mib(pid: int | None = None) -> float | None:
    """Best-effort *current* RSS/working set without psutil."""
    pid = os.getpid() if pid is None else int(pid)
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            PROCESS_VM_READ = 0x0010

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
            )
            if not handle:
                return None
            try:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    return counters.WorkingSetSize / 1024 / 1024
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return None
    else:
        try:
            # /proc gives current RSS; ru_maxrss is only a peak and would make
            # the memory governor permanently pessimistic after one spike.
            statm = f"/proc/{pid}/statm"
            if os.path.exists(statm):
                with open(statm, "r", encoding="ascii") as f:
                    pages = int(f.read().split()[1])
                return pages * os.sysconf("SC_PAGE_SIZE") / 1024 / 1024
            if pid == os.getpid():
                import resource
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                return rss / (1024 if platform.system() == "Linux" else 1024 * 1024)
        except Exception:
            return None
    return None



def process_private_commit_mib(pid: int | None = None) -> float | None:
    """Best-effort committed private bytes (Windows PROCESS_MEMORY_COUNTERS_EX.PrivateUsage).

    This is deliberately named *private commit*, not private working set. It is
    useful alongside working-set and system commit deltas; none of these alone
    captures iGPU/shared-driver memory.
    """
    pid = os.getpid() if pid is None else int(pid)
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_VM_READ = 0x0010

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
        )
        if not handle:
            return None
        try:
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(counters)
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.PrivateUsage / 1024 / 1024
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return None
    return None


def process_tree_private_commit_mib(root_pid: int) -> float | None:
    total = 0.0
    found = False
    for pid in process_tree_pids(root_pid):
        value = process_private_commit_mib(pid)
        if value is not None:
            total += value
            found = True
    return total if found else None

def _process_parent_map() -> dict[int, list[int]]:
    """Return parent -> child PID map using native OS primitives only."""
    parents: dict[int, list[int]] = defaultdict(list)
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            TH32CS_SNAPPROCESS = 0x00000002
            MAX_PATH = 260
            INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ("dwSize", wintypes.DWORD),
                    ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * MAX_PATH),
                ]

            k32 = ctypes.windll.kernel32
            snapshot = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if snapshot == INVALID_HANDLE_VALUE:
                return dict(parents)
            try:
                entry = PROCESSENTRY32W()
                entry.dwSize = ctypes.sizeof(entry)
                if not k32.Process32FirstW(snapshot, ctypes.byref(entry)):
                    return dict(parents)
                while True:
                    parents[int(entry.th32ParentProcessID)].append(int(entry.th32ProcessID))
                    if not k32.Process32NextW(snapshot, ctypes.byref(entry)):
                        break
            finally:
                k32.CloseHandle(snapshot)
        except Exception:
            pass
    else:
        proc = "/proc"
        try:
            for name in os.listdir(proc):
                if not name.isdigit():
                    continue
                pid = int(name)
                try:
                    with open(f"{proc}/{name}/status", "r", encoding="ascii", errors="ignore") as f:
                        ppid = None
                        for line in f:
                            if line.startswith("PPid:"):
                                ppid = int(line.split()[1])
                                break
                    if ppid is not None:
                        parents[ppid].append(pid)
                except (OSError, ValueError):
                    continue
        except OSError:
            pass
    return dict(parents)


def process_tree_pids(root_pid: int, max_processes: int = 512) -> list[int]:
    """Root PID + descendants, bounded against pathological process trees."""
    root_pid = int(root_pid)
    parent_map = _process_parent_map()
    out: list[int] = []
    seen: set[int] = set()
    q = deque([root_pid])
    while q and len(out) < max(1, int(max_processes)):
        pid = q.popleft()
        if pid in seen:
            continue
        seen.add(pid)
        out.append(pid)
        q.extend(parent_map.get(pid, ()))
    return out


def process_tree_rss_mib(root_pid: int) -> float | None:
    """Sum current RSS for an agent process and all of its descendants."""
    total = 0.0
    found = False
    for pid in process_tree_pids(root_pid):
        rss = process_rss_mib(pid)
        if rss is not None:
            total += rss
            found = True
    return total if found else None


def system_memory() -> dict[str, float | None]:
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(st)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total_commit = st.ullTotalPageFile / 1024 / 1024
                avail_commit = st.ullAvailPageFile / 1024 / 1024
                return {
                    "total_mib": st.ullTotalPhys / 1024 / 1024,
                    "available_mib": st.ullAvailPhys / 1024 / 1024,
                    "used_pct": float(st.dwMemoryLoad),
                    "commit_limit_mib": total_commit,
                    "commit_used_mib": total_commit - avail_commit,
                }
        except Exception:
            pass
    else:
        try:
            data = {}
            with open("/proc/meminfo", "r", encoding="ascii") as f:
                for line in f:
                    k, v = line.split(":", 1)
                    data[k] = float(v.strip().split()[0]) / 1024
            total = data.get("MemTotal")
            avail = data.get("MemAvailable")
            pct = None if not total or avail is None else (total - avail) / total * 100
            return {"total_mib": total, "available_mib": avail, "used_pct": pct}
        except Exception:
            pass
    return {"total_mib": None, "available_mib": None, "used_pct": None}


class Telemetry:
    """Small buffered telemetry writer.

    Samples are batched to avoid waking SQLite/WAL for every metric. The buffer
    is deliberately tiny and bounded; telemetry is observability, not critical
    transactional state.
    """

    def __init__(self, db: Database, retention_h: int = 72, batch_size: int = 32, flush_interval_s: float = 30.0):
        self.db = db
        self.retention_h = max(1, int(retention_h))
        self.batch_size = max(4, int(batch_size))
        self.flush_interval_s = max(5.0, float(flush_interval_s))
        self._buffer: list[tuple] = []
        self._lock = threading.RLock()
        self._last_flush = time.monotonic()

    def record(self, source: str, metric: str, value: float, unit: str = "", labels: dict[str, Any] | None = None) -> None:
        row = (time.time(), source, metric, float(value), unit, self.db.dumps(labels or {}))
        should_flush = False
        with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.batch_size or time.monotonic() - self._last_flush >= self.flush_interval_s
        if should_flush:
            self.flush()

    def flush(self) -> int:
        with self._lock:
            if not self._buffer:
                self._last_flush = time.monotonic()
                return 0
            rows = self._buffer
            self._buffer = []
            self._last_flush = time.monotonic()
        try:
            with self.db.transaction() as conn:
                conn.executemany(
                    "INSERT INTO telemetry(ts,source,metric,value,unit,labels_json) VALUES(?,?,?,?,?,?)",
                    rows,
                )
        except Exception:
            # Put rows back once; keep the buffer bounded to avoid a failure loop
            # becoming a memory leak.
            with self._lock:
                self._buffer = (rows + self._buffer)[-self.batch_size:]
            raise
        return len(rows)

    def sample_core(self, persist: bool = True) -> dict[str, Any]:
        rss = process_rss_mib()
        private_commit = process_private_commit_mib()
        mem = system_memory()
        if persist and rss is not None:
            self.record("metatron", "working_set", rss, "MiB")
        if persist and private_commit is not None:
            self.record("metatron", "private_commit", private_commit, "MiB")
        return {"working_set_mib": rss, "rss_mib": rss, "private_commit_mib": private_commit, "system_memory": mem}

    def latest(self, limit: int = 100) -> list[dict[str, Any]]:
        self.flush()
        limit = min(max(1, int(limit)), 1000)
        rows = self.db.query("SELECT * FROM telemetry ORDER BY seq DESC LIMIT ?", (limit,))
        for row in rows:
            row["labels"] = self.db.loads(row.pop("labels_json"))
        return rows

    def prune(self, now: float | None = None) -> int:
        self.flush()
        cutoff = (time.time() if now is None else float(now)) - self.retention_h * 3600
        cur = self.db.execute("DELETE FROM telemetry WHERE ts<?", (cutoff,))
        return int(cur.rowcount if cur.rowcount is not None else 0)

    def close(self) -> None:
        self.flush()
