from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

from .config import load_config
from .display import ST7789V2Display
from .render import render_status
from .status import collect

LOG = logging.getLogger("pi-status-display")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry-Pi-Status auf ST7789V2 anzeigen")
    parser.add_argument("--config", required=True, help="Pfad zur Host-Konfiguration")
    parser.add_argument("--once", action="store_true", help="Nur einmal aktualisieren")
    parser.add_argument("--preview", metavar="PNG", help="PNG schreiben statt LCD anzusteuern")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args(argv)


def run(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = load_config(args.config)
    except ValueError as exc:
        LOG.error("%s", exc)
        return 2

    if args.preview:
        image = render_status(config.host_label, collect(config.services, config.show_cpu_ram))
        target = Path(args.preview)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        LOG.info("Vorschau gespeichert: %s", target)
        return 0

    stopping = False
    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        with ST7789V2Display(config.display) as display:
            while not stopping:
                started = time.monotonic()
                try:
                    display.show(render_status(
                        config.host_label, collect(config.services, config.show_cpu_ram)
                    ))
                except Exception:
                    LOG.exception("Aktualisierung fehlgeschlagen; nächster Versuch folgt")
                if args.once:
                    break
                remaining = config.refresh_seconds - (time.monotonic() - started)
                if remaining > 0:
                    time.sleep(remaining)
    except Exception:
        LOG.exception("Display konnte nicht gestartet werden")
        return 1
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
