from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass(frozen=True)
class DisplayConfig:
    spi_bus: int = 0
    spi_device: int = 0
    spi_hz: int = 40_000_000
    dc_gpio: int = 25
    reset_gpio: int = 27
    backlight_gpio: int = 18
    rotation: int = 90
    brightness: float = 0.8


@dataclass(frozen=True)
class AppConfig:
    host_label: str
    refresh_seconds: float = 5.0
    show_cpu_ram: bool = True
    services: list[str] = field(default_factory=list)
    display: DisplayConfig = field(default_factory=DisplayConfig)


def load_config(path: Union[str, Path]) -> AppConfig:
    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Konfiguration kann nicht gelesen werden: {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Konfiguration muss ein JSON-Objekt sein")
    label = str(raw.get("host_label", "")).strip()
    if not label:
        raise ValueError("host_label darf nicht leer sein")
    refresh = float(raw.get("refresh_seconds", 5))
    if refresh < 1:
        raise ValueError("refresh_seconds muss mindestens 1 sein")
    services = raw.get("services", [])
    if not isinstance(services, list) or not all(isinstance(s, str) and s for s in services):
        raise ValueError("services muss eine Liste nicht-leerer Namen sein")

    display_raw = raw.get("display", {})
    if not isinstance(display_raw, dict):
        raise ValueError("display muss ein JSON-Objekt sein")
    allowed = set(DisplayConfig.__dataclass_fields__)
    unknown = set(display_raw) - allowed
    if unknown:
        raise ValueError(f"Unbekannte Display-Einstellung(en): {', '.join(sorted(unknown))}")
    display = DisplayConfig(**display_raw)
    if display.rotation not in (90, 270):
        raise ValueError("rotation muss für Querformat 90 oder 270 sein")
    if not 0.0 <= display.brightness <= 1.0:
        raise ValueError("brightness muss zwischen 0 und 1 liegen")
    if not 100_000 <= display.spi_hz <= 62_500_000:
        raise ValueError("spi_hz liegt außerhalb des sicheren Bereichs")

    return AppConfig(
        host_label=label,
        refresh_seconds=refresh,
        show_cpu_ram=bool(raw.get("show_cpu_ram", True)),
        services=services,
        display=display,
    )
