from __future__ import annotations

import socket
import subprocess
import time
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class PowerStatus:
    label: str
    healthy: bool
    raw: Optional[int]


@dataclass(frozen=True)
class SystemStatus:
    ip_address: str
    uptime: str
    temperature_c: Optional[float]
    power: PowerStatus
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    services: Dict[str, Optional[bool]]
    storage_label: str = "DISK"
    storage_percent: Optional[float] = None


def ip_address() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    try:
        sock.connect(("1.1.1.1", 80))
        address = sock.getsockname()[0]
        return address if not address.startswith("127.") else "keine IP"
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "keine IP"
    finally:
        sock.close()


def uptime_text(path: Union[str, Path] = "/proc/uptime") -> str:
    try:
        seconds = int(float(Path(path).read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return "unbekannt"
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return f"{days}d {hours:02d}h" if days else f"{hours}h {minutes:02d}m"


def cpu_temperature(path: Union[str, Path] = "/sys/class/thermal/thermal_zone0/temp") -> Optional[float]:
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"], capture_output=True, text=True,
            timeout=1.5, check=False,
        )
        match = re.search(r"(-?\d+(?:\.\d+)?)", result.stdout)
        if result.returncode == 0 and match:
            return float(match.group(1))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    try:
        value = float(Path(path).read_text().strip())
        return value / 1000.0 if value > 1000 else value
    except (OSError, ValueError):
        return None


def power_status() -> PowerStatus:
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"], capture_output=True, text=True,
            timeout=1.5, check=False,
        )
        raw = int(result.stdout.strip().split("=", 1)[1], 16)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return PowerStatus("UNBEKANNT", False, None)

    current = raw & 0xF
    historic = raw & 0xF0000
    if current & 0x1:
        return PowerStatus("UNTERSPANNUNG", False, raw)
    if current:
        return PowerStatus("GEDROSSELT", False, raw)
    if historic:
        return PowerStatus("VERLAUF!", False, raw)
    return PowerStatus("OK", True, raw)


def cpu_percent(path: Union[str, Path] = "/proc/stat") -> Optional[float]:
    def snapshot() -> tuple:
        fields = [int(v) for v in Path(path).read_text().splitlines()[0].split()[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
        return sum(fields), idle

    try:
        total_1, idle_1 = snapshot()
        time.sleep(0.1)
        total_2, idle_2 = snapshot()
        total_delta = total_2 - total_1
        idle_delta = idle_2 - idle_1
        return max(0.0, min(100.0, (total_delta - idle_delta) * 100.0 / total_delta))
    except (OSError, ValueError, IndexError, ZeroDivisionError):
        return None


def ram_percent(path: Union[str, Path] = "/proc/meminfo") -> Optional[float]:
    try:
        values = {}
        for line in Path(path).read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0])
        return (values["MemTotal"] - values["MemAvailable"]) * 100.0 / values["MemTotal"]
    except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError):
        return None


def storage_usage(
    path: Union[str, Path] = "/",
    mounts_path: Union[str, Path] = "/proc/self/mounts",
) -> tuple[str, Optional[float]]:
    """Return a compact device label and utilization for the system filesystem."""
    source = ""
    try:
        target = str(path)
        for line in Path(mounts_path).read_text().splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[1].replace("\\040", " ") == target:
                source = fields[0].replace("\\040", " ")
                break
    except (OSError, UnicodeError):
        pass

    lowered = source.lower()
    if "nvme" in lowered:
        label = "NVMe"
    elif "mmcblk" in lowered:
        label = "SD"
    else:
        label = "DISK"

    try:
        usage = shutil.disk_usage(path)
        percent = usage.used * 100.0 / usage.total
    except (OSError, ZeroDivisionError):
        percent = None
    return label, percent


def _process_is_running(name: str, proc_root: Union[str, Path] = "/proc") -> Optional[bool]:
    try:
        proc = Path(proc_root)
        for entry in proc.iterdir():
            if entry.name.isdigit():
                try:
                    if (entry / "comm").read_text().strip() == name:
                        return True
                except (OSError, UnicodeError):
                    continue
        return False
    except OSError:
        return None


def _container_is_running(name: str) -> Optional[bool]:
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.State.Running}}", name],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return False
    return result.stdout.strip().lower() == "true"


def service_states(names: list[str]) -> Dict[str, Optional[bool]]:
    states: Dict[str, Optional[bool]] = {}
    for configured_name in names:
        target, separator, configured_label = configured_name.partition("|")
        label = configured_label.strip() if separator and configured_label.strip() else target
        if target.startswith("process:"):
            process_name = target.split(":", 1)[1]
            states[label] = _process_is_running(process_name) if process_name else None
            continue
        if target.startswith("container:"):
            container_name = target.split(":", 1)[1]
            states[label] = _container_is_running(container_name) if container_name else None
            continue
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "--quiet", target], timeout=1.5, check=False
            )
            states[label] = result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            states[label] = None
    return states


def collect(services: list[str], include_cpu_ram: bool) -> SystemStatus:
    storage_label, storage_percent = storage_usage()
    return SystemStatus(
        ip_address=ip_address(), uptime=uptime_text(), temperature_c=cpu_temperature(),
        power=power_status(),
        cpu_percent=cpu_percent() if include_cpu_ram else None,
        ram_percent=ram_percent() if include_cpu_ram else None,
        services=service_states(services),
        storage_label=storage_label,
        storage_percent=storage_percent,
    )
