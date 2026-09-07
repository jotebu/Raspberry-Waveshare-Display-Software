# Raspberry Pi Status Display — 1.0.0

Statusanzeige für das Waveshare 1.9inch LCD mit ST7789V2, im Querformat **320 × 170 Pixel**.
Der Stand wurde auf einem Pi-hole-Raspberry mit Raspberry Pi OS / Raspbian 13 (Trixie) am echten Display getestet. Der systemd-Dienst wurde als laufend und für den Autostart aktiviert bestätigt; ein Neustart-Test wurde noch nicht dokumentiert.

## Anzeige

- Vier Karten: IP-Adresse, Uptime, CPU-Temperatur und Stromversorgungs-/Drosselungsstatus.
- Hostname links, Uhrzeit rechts; davor ein Statuspunkt für den **ersten** konfigurierten Dienst: grün = aktiv, rot = inaktiv, orange = unbekannt.
- CPU linksbündig, RAM mittig und SD/DISK/NVMe rechtsbündig. Die untere Zeile nutzt dieselbe 15-Pixel-Schrift wie die Kartenbeschriftungen und liegt innerhalb der 170 Pixel Höhe.
- Keine zusätzliche Service-Zeile. Weitere konfigurierte Dienste werden abgefragt, aber nicht angezeigt. Anzeigenamen sollten eindeutig sein.
- Automatische Aktualisierung (standardmäßig alle fünf Sekunden).

## Verdrahtung

| LCD | Raspberry Pi (BCM) | Physischer Pin |
|---|---|---:|
| VCC | 3,3 V | 1 |
| GND | GND | 6 |
| DIN | GPIO10 / MOSI | 19 |
| CLK | GPIO11 / SCLK | 23 |
| CS | GPIO8 / CE0 | 24 |
| DC | GPIO25 | 22 |
| RST | GPIO27 | 13 |
| BL | GPIO18 | 12 |

## Neuinstallation auf dem Raspberry

Diese Schritte sind für eine Neuinstallation gedacht. Bei einer vorhandenen Installation zuerst Projekt und eigene Konfiguration sichern.

1. Mit `sudo raspi-config` unter **Interface Options → SPI** SPI aktivieren, anschließend neu starten. `ls -l /dev/spidev0.0` sollte das SPI-Gerät zeigen.
2. Abhängigkeiten und Version 1.0.0 installieren:

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pil python3-spidev python3-gpiozero python3-lgpio fonts-dejavu-core
sudo git clone --branch v1.0.0 https://github.com/jotebu/Raspberry-Waveshare-Display-Software.git /opt/pi-status-display
sudo python3 -m venv --system-site-packages /opt/pi-status-display/.venv
sudo /opt/pi-status-display/.venv/bin/pip install --no-deps /opt/pi-status-display
```

Python >= 3.9 wird vorausgesetzt. Hardwarezugriff erfolgt über SPI und gpiozero; DejaVu Sans wird für das Layout benötigt.

## Vorschau und Display-Test

```bash
cd /opt/pi-status-display
PYTHONPATH="$PWD/src" ./.venv/bin/pi-status-display --config ./config/pihole.json --preview /tmp/pihole-display-test.png
sudo env PYTHONPATH="$PWD/src" ./.venv/bin/pi-status-display --config ./config/pihole.json --log-level DEBUG
```

Der zweite Befehl läuft bis Strg+C. Nicht parallel zum systemd-Dienst starten. `--once` beendet das Programm nach einem Bild und schaltet dabei die Hintergrundbeleuchtung wieder aus.

## Autostart (Pi-hole)

Die mitgelieferte Dienstdatei entspricht der auf dem Pi getesteten Konfiguration. Sie verwendet `config/pihole.json` und lädt ausdrücklich den Quellcode unter `src`, damit Änderungen dort sofort nach einem Dienstneustart wirksam sind.

```bash
sudo cp /opt/pi-status-display/systemd/pi-status-display.service /etc/systemd/system/pi-status-display.service
sudo systemctl daemon-reload
sudo systemctl enable --now pi-status-display.service
sudo systemctl status pi-status-display.service --no-pager
```

`enabled` bestätigt den Autostart, `active (running)` den laufenden Prozess. Die SSH-Verbindung kann geschlossen werden. Der Dienst läuft wie im manuellen Test als root und startet bei einem Programmende nach fünf Sekunden neu; ein ausdrückliches `systemctl stop` bleibt gestoppt.

```bash
sudo systemctl restart pi-status-display.service
sudo systemctl stop pi-status-display.service
sudo journalctl -u pi-status-display.service -n 50 --no-pager
```

Ein optionaler `sudo reboot` prüft den Start nach einem Neustart; Pi-hole ist dabei kurz nicht erreichbar.

## Andere Hosts und Einstellungen

Beispiele stehen in `config/symcon.json`, `config/mediamtx.json` und `config/test-pi.json`.
Für einen anderen Host in der installierten Dienstdatei den `--config`-Pfad ändern; `pihole-FTL.service` aus `After=` entfernen oder durch den passenden Dienst ersetzen. Danach `sudo systemctl daemon-reload` und `sudo systemctl restart pi-status-display.service` ausführen.

- `host_label`: Anzeigename oben links.
- `services`: systemd-Name (z. B. `pihole-FTL.service`), `process:NAME` oder `container:NAME`; optional `|Anzeigename`. Der erste Eintrag bestimmt den Punkt.
- `show_cpu_ram: false`: CPU/RAM werden nicht abgefragt und als `--` angezeigt.
- `rotation`: 90 oder 270; beide im Querformat.
- `brightness`: 0 bis 1; `refresh_seconds`: mindestens 1.
- Bei instabiler Darstellung kann `spi_hz` auf 24000000 reduziert werden.

Fehlende Messwerte erscheinen als `--` oder `UNBEKANNT`. Bei Dienstabfragen werden Zeitüberschreitungen bzw. nicht ausführbare Befehle als unbekannt behandelt; negative systemctl-/Docker-Rückgaben erscheinen als inaktiv.
Der Power-Wert basiert auf `vcgencmd get_throttled`, nicht auf einer Wattmessung. `VERLAUF!` bezeichnet ein seit dem Boot gespeichertes Problem.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Softwaretests benötigen Pillow und eine skalierbare Schrift; SPI/GPIO-Hardware ist dafür nicht erforderlich. Symcon und MediaMTX sind als Konfigurationsbeispiele enthalten und wurden für diesen Release nicht am Gerät getestet.
