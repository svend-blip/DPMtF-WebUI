"""Platform Adapter Framework — Phase 2L.

Abstracts platform-specific operations behind a common interface.
Linux is the primary implementation. Windows is a stub for future use.

ADR-6000003: Linux-first implementation with future platform adapters.
"""

import os
import platform
import subprocess
import sys
from abc import ABC, abstractmethod


class PlatformAdapter(ABC):
    """Abstract base for platform-specific operations."""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return platform identifier: 'linux' or 'windows'."""
        ...

    @abstractmethod
    def get_gpu_info(self) -> list[dict]:
        """Return list of GPU dicts with index, name, memory, utilization."""
        ...

    @abstractmethod
    def get_disk_usage(self, path: str) -> dict | None:
        """Return disk usage dict for a path: size, used, free, use_percent."""
        ...

    @abstractmethod
    def check_port(self, port: int) -> bool:
        """Return True if port is in use."""
        ...

    @abstractmethod
    def get_process_list(self, name_filter: str | None = None) -> list[dict]:
        """Return list of running processes with pid, name, cmdline."""
        ...

    @abstractmethod
    def kill_process_on_port(self, port: int) -> bool:
        """Kill process listening on port. Return True if successful."""
        ...

    @abstractmethod
    def get_env_path_separator(self) -> str:
        """Return path separator: ':' on Linux, ';' on Windows."""
        ...

    @abstractmethod
    def get_home_dir(self) -> str:
        """Return user home directory path."""
        ...


class LinuxPlatformAdapter(PlatformAdapter):
    """Linux implementation using standard CLI tools."""

    def get_platform_name(self) -> str:
        return "linux"

    def get_gpu_info(self) -> list[dict]:
        """Query nvidia-smi for GPU information."""
        try:
            proc = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,"
                 "memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            gpus = []
            for line in proc.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_used_mb": int(parts[2]),
                        "memory_total_mb": int(parts[3]),
                        "memory_free_mb": int(parts[4]),
                        "utilization_percent": int(parts[5]),
                    })
            return gpus
        except Exception:
            return []

    def get_disk_usage(self, path: str) -> dict | None:
        """Query df for disk usage."""
        try:
            proc = subprocess.run(
                ["df", "-h", path], capture_output=True, text=True, timeout=5,
            )
            lines = proc.stdout.strip().split("\n")
            if len(lines) < 2:
                return None
            parts = lines[1].split()
            if len(parts) < 5:
                return None
            return {
                "filesystem": parts[0],
                "size": parts[1],
                "used": parts[2],
                "available": parts[3],
                "use_percent": parts[4].rstrip("%"),
            }
        except Exception:
            return None

    def check_port(self, port: int) -> bool:
        """Check if port is in use via ss or socket."""
        try:
            proc = subprocess.run(
                ["ss", "-tlnp"], capture_output=True, text=True, timeout=5,
            )
            return f":{port}" in proc.stdout
        except Exception:
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1)
                result = s.connect_ex(("127.0.0.1", port))
                s.close()
                return result == 0
            except Exception:
                return False

    def get_process_list(self, name_filter: str | None = None) -> list[dict]:
        """List processes via ps aux."""
        try:
            proc = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5,
            )
            processes = []
            for line in proc.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) < 11:
                    continue
                pid = parts[1]
                name = parts[10]
                if name_filter and name_filter not in name:
                    continue
                processes.append({
                    "pid": int(pid),
                    "name": name,
                    "cmdline": " ".join(parts[10:]),
                })
            return processes
        except Exception:
            return []

    def kill_process_on_port(self, port: int) -> bool:
        """Kill process on port using fuser."""
        try:
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    def get_env_path_separator(self) -> str:
        return ":"

    def get_home_dir(self) -> str:
        return os.path.expanduser("~")


class WindowsPlatformAdapter(PlatformAdapter):
    """Windows stub — returns empty/False for all queries.

    Full Windows implementation deferred to future phase.
    """

    def get_platform_name(self) -> str:
        return "windows"

    def get_gpu_info(self) -> list[dict]:
        return []  # nvidia-smi works on Windows but not yet implemented

    def get_disk_usage(self, path: str) -> dict | None:
        return None  # wmic logicaldisk not yet implemented

    def check_port(self, port: int) -> bool:
        return False  # netstat -ano not yet implemented

    def get_process_list(self, name_filter: str | None = None) -> list[dict]:
        return []  # tasklist not yet implemented

    def kill_process_on_port(self, port: int) -> bool:
        return False  # netstat + taskkill not yet implemented

    def get_env_path_separator(self) -> str:
        return ";"

    def get_home_dir(self) -> str:
        return os.path.expanduser("~")


# ── Platform detection ──────────────────────────────────────────────


def detect_platform() -> PlatformAdapter:
    """Auto-detect platform and return appropriate adapter."""
    system = platform.system().lower()
    if system == "linux":
        return LinuxPlatformAdapter()
    elif system == "windows":
        return WindowsPlatformAdapter()
    else:
        # Default to Linux for unknown platforms (BSD, etc.)
        return LinuxPlatformAdapter()


# Module-level singleton
_adapter: PlatformAdapter | None = None


def get_adapter() -> PlatformAdapter:
    """Return the platform adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = detect_platform()
    return _adapter
