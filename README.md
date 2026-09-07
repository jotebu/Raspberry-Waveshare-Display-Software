# Raspberry Pi Status Display

Eine kompakte Statusanzeige für Raspberry Pis – unabhängig davon, welche Anwendungen darauf laufen. Unterstützt wird das **Waveshare 1.9inch LCD mit ST7789V2** im Querformat **320 × 170 Pixel**. Andere Displays oder beliebige Computer werden nicht automatisch unterstützt.

Die Anleitung installiert die veröffentlichte **Version 1.0.0 direkt von GitHub**. Die Anzeige wurde unter Trixie auch auf einem Raspberry Pi 5 erfolgreich betrieben.

## Was zeigt das Display?

- Oben: frei wählbarer Gerätename, Uhrzeit und ein farbiger Dienststatus.
- Vier Karten: IP-Adresse, Laufzeit seit dem Start, CPU-Temperatur und Stromversorgungs-/Drosselungsstatus.
- Unten: CPU-Auslastung links, RAM-Belegung mittig und SD-/DISK-/NVMe-Belegung rechts.
- Gut lesbare Beschriftungen und Aktualisierung alle fünf Sekunden.

Der Punkt zeigt den Status des ersten konfigurierten Dienstes: **grün = aktiv**, **rot = inaktiv**, **orange = unbekannt**. Ohne konfigurierten Dienst bleibt er orange. Er zeigt nicht den allgemeinen Gesundheitszustand des Raspberry an.

## 1. Voraussetzungen und Anschluss

Du benötigst:

- Einen Raspberry Pi mit GPIO-Anschluss und aktuellem Raspberry Pi OS; diese Anleitung ist für Trixie vorgesehen.
- Ein Waveshare 1.9inch LCD mit ST7789V2 und Verbindungskabel.
- Internetzugang für die Installation und einen Benutzer mit `sudo`-Rechten.
- Ein Terminal auf dem Raspberry oder eine SSH-Verbindung, beispielsweise mit PuTTY.

**Alle folgenden Befehle werden im Terminal des Raspberry ausgeführt, nicht in der Windows-PowerShell.** Kopiere jeweils nur den Inhalt eines Codeblocks. Eine Passwortabfrage bei `sudo` ist normal; beim Tippen werden keine Zeichen angezeigt.

Schalte den Raspberry aus und trenne die Stromversorgung, bevor du die Kabel anschließt. Die GPIO-Nummer und die physische Pin-Nummer sind unterschiedliche Angaben:

| LCD-Anschluss | Raspberry Pi (BCM) | Physischer Pin |
|---|---|---:|
| VCC | 3,3 V | 1 |
| GND | Masse | 6 |
| DIN | GPIO10 / MOSI | 19 |
| CLK | GPIO11 / SCLK | 23 |
| CS | GPIO8 / CE0 | 24 |
| DC | GPIO25 | 22 |
| RST | GPIO27 | 13 |
| BL | GPIO18 | 12 |

Orientiere dich an den Platinenbeschriftungen; Kabelfarben sind nicht einheitlich. Starte den Raspberry danach wieder.

## 2. SPI aktivieren

SPI ist die Schnittstelle, über die die Software das Display ansteuert.

```bash
sudo raspi-config
```

Wähle **Interface Options → SPI → Yes**, anschließend **Finish**. Starte neu, wenn das Programm dies nicht bereits veranlasst:

```bash
sudo reboot
```

Die SSH-Verbindung wird dabei getrennt. Verbinde dich nach dem Neustart erneut und prüfe:

```bash
ls -l /dev/spidev0.0 /dev/spidev0.1
```

Es sollten beide Geräte angezeigt werden. Falls `/dev/spidev0.0` fehlt, fahre noch nicht mit dem Display-Test fort: Prüfe die SPI-Einstellung und ob tatsächlich neu gestartet wurde. Falls `raspi-config` fehlt, benötigt dein Betriebssystem eine passende SPI-Einrichtung.

Beim Pi 5 kann `dtoverlay=nospi10` in der Boot-Konfiguration stehen. Dieser Eintrag betrifft SPI10 und muss für unser Display an SPI0 nicht entfernt werden.

## 3. Version 1.0.0 von GitHub installieren

Der folgende Block lädt zuerst die Version herunter. Eine vorhandene Installation wird unter `/opt/pi-status-display.backup.DATUM-UHRZEIT` gesichert; eine vorhandene Dienstdatei wird ebenfalls gesichert. Ein laufender Anzeigedienst wird für die Installation gestoppt. Andere Anwendungen werden nicht gestoppt.

Kopiere den **gesamten Block einschließlich `bash` und der abschließenden Zeile `EOF`**. Bei einem Fehler hält er an. Fahre erst fort, wenn **„Installation abgeschlossen.“** erscheint.

```bash
bash <<'EOF'
set -e

sudo apt update
sudo apt install -y git python3-venv python3-pil python3-spidev python3-gpiozero python3-lgpio fonts-dejavu-core

download=$(mktemp -d /tmp/pi-status-display-1.0.0.XXXXXX)
git clone --depth 1 --branch v1.0.0 https://github.com/jotebu/Raspberry-Waveshare-Display-Software.git "$download"

stamp=$(date +%Y%m%d-%H%M%S)
if [ -d /opt/pi-status-display ]; then
  sudo cp -a /opt/pi-status-display "/opt/pi-status-display.backup.$stamp"
  echo "Projektsicherung: /opt/pi-status-display.backup.$stamp"
fi
if [ -f /etc/systemd/system/pi-status-display.service ]; then
  sudo cp -a /etc/systemd/system/pi-status-display.service "/etc/systemd/system/pi-status-display.service.bak.$stamp"
fi
if systemctl is-active --quiet pi-status-display.service; then
  sudo systemctl stop pi-status-display.service
fi

sudo mkdir -p /opt/pi-status-display
sudo cp -a "$download/src" "$download/config" "$download/systemd" "$download/tests" /opt/pi-status-display/
sudo cp "$download/pyproject.toml" "$download/README.md" "$download/CHANGELOG.md" /opt/pi-status-display/
sudo python3 -m venv --system-site-packages /opt/pi-status-display/.venv
sudo /opt/pi-status-display/.venv/bin/python -m pip install --no-deps /opt/pi-status-display

echo "Installation abgeschlossen."
EOF
```

Die Git-Meldung „detached HEAD“ ist beim Herunterladen einer festen Version normal. Die mitgelieferten Beispielkonfigurationen werden durch die Release-Dateien ersetzt; eigene Anpassungen daran liegen zusätzlich in der Sicherung. Die im nächsten Schritt verwendete `host.json` wird beim Kopieren nicht überschrieben.

## 4. Eigenen Gerätenamen festlegen

Wir verwenden für alle Geräte denselben Konfigurationspfad: `/opt/pi-status-display/config/host.json`.

Dieser Block erstellt eine allgemeine Konfiguration, **sofern noch keine `host.json` existiert**:

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path

path = Path('/opt/pi-status-display/config/host.json')
config = {
    'host_label': 'Mein Raspberry',
    'refresh_seconds': 5,
    'show_cpu_ram': True,
    'services': [],
    'display': {
        'spi_bus': 0,
        'spi_device': 0,
        'spi_hz': 40000000,
        'dc_gpio': 25,
        'reset_gpio': 27,
        'backlight_gpio': 18,
        'rotation': 90,
        'brightness': 0.8
    }
}
if path.exists():
    print('Vorhandene host.json bleibt erhalten.')
else:
    path.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print('host.json wurde angelegt.')
PY
```

Öffne die Datei:

```bash
sudo nano /opt/pi-status-display/config/host.json
```

Ersetze `Mein Raspberry` durch den gewünschten Anzeigenamen. Speichere mit **Strg+O**, bestätige mit **Enter** und schließe mit **Strg+X**. Behalte Anführungszeichen und Kommas bei.

Optional kannst du bei `services` einen Dienst überwachen. Zum Beispiel überwacht `"services": ["ssh.service"]` den SSH-Dienst. Dessen tatsächlichen Namen kannst du mit `systemctl status ssh.service --no-pager` prüfen. Mit `"services": []` wird kein Dienst überwacht; der Punkt ist dann orange.

Weitere Einstellungen:

| Einstellung | Bedeutung |
|---|---|
| `refresh_seconds` | Aktualisierung in Sekunden; mindestens 1 |
| `brightness` | Helligkeit von 0 bis 1 |
| `rotation` | 90 oder 270; bei kopfstehendem Bild wechseln |
| `show_cpu_ram` | Bei `false` werden CPU/RAM nicht abgefragt und als `--` angezeigt |
| `services` | Dienstnamen; alternativ `process:NAME` oder `container:NAME` |

Nach einem Dienstnamen kann `|Anzeigename` stehen. Nur der erste Eintrag bestimmt den Statuspunkt. Verwende eindeutige Anzeigenamen. Container-Abfragen setzen Docker voraus.

## 5. Vorschau und Display testen

Zuerst ein Vorschaubild erzeugen:

```bash
cd /opt/pi-status-display
PYTHONPATH="$PWD/src" ./.venv/bin/pi-status-display --config ./config/host.json --preview /tmp/display-preview.png
```

Die Erfolgsmeldung nennt `/tmp/display-preview.png`. Du kannst das Bild beispielsweise mit WinSCP vom Raspberry herunterladen und öffnen. Dieser Befehl zeigt noch nichts auf dem LCD an.

Starte danach die echte Anzeige:

```bash
cd /opt/pi-status-display
sudo env PYTHONPATH="$PWD/src" GPIOZERO_PIN_FACTORY=lgpio ./.venv/bin/pi-status-display --config ./config/host.json --log-level DEBUG
```

Das Display sollte aufleuchten und die Werte regelmäßig aktualisieren. Die GPIO-Einstellung verwendet ausdrücklich `lgpio`, wie im Test auf dem Raspberry Pi 5.

Wenn alles gut aussieht, beende den Test mit **Strg+C**. Die Hintergrundbeleuchtung geht dabei aus. Das ist normal. Bei einem Fehler zuerst die Meldung prüfen, bevor du den Autostart aktivierst.

## 6. Automatisch beim Start einschalten

Kopiere diesen Block vollständig; die letzte Zeile `EOF` muss allein stehen. Er erstellt den Anzeigedienst für deine `host.json`:

```bash
sudo tee /etc/systemd/system/pi-status-display.service >/dev/null <<'EOF'
[Unit]
Description=Raspberry Pi LCD Statusanzeige
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pi-status-display
Environment=PYTHONPATH=/opt/pi-status-display/src
Environment=GPIOZERO_PIN_FACTORY=lgpio
ExecStart=/opt/pi-status-display/.venv/bin/pi-status-display --config /opt/pi-status-display/config/host.json --log-level INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Aktiviere und starte ihn:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-status-display.service
sudo systemctl restart pi-status-display.service
sudo systemctl status pi-status-display.service --no-pager
```

Prüfe nach etwa 30 Sekunden nochmals:

```bash
systemctl status pi-status-display.service --no-pager
```

- **`enabled`**: Der Autostart ist aktiviert.
- **`active (running)`**: Das Programm läuft. Prüfe zusätzlich, ob das Display die Werte zeigt.
- Die angezeigte Laufzeit sollte wachsen, statt ständig wieder bei wenigen Sekunden zu beginnen.

Du kannst nun die SSH-Verbindung schließen. Der Dienst läuft als root für den Hardwarezugriff und startet nach einem Programmende automatisch nach fünf Sekunden neu. Ein ausdrückliches Stoppen mit `systemctl stop` bleibt dagegen wirksam.

Optional lässt sich der Autostart mit `sudo reboot` testen. Dabei sind alle Anwendungen auf dem Raspberry vorübergehend nicht erreichbar. Ein überwachter Dienst kann beim Booten zunächst noch inaktiv sein; sein Status wird bei der nächsten Aktualisierung erneut abgefragt.

## Bedienung und Hilfe

Nach Änderungen an `host.json` die Anzeige neu starten:

```bash
sudo systemctl restart pi-status-display.service
```

Anzeige stoppen:

```bash
sudo systemctl stop pi-status-display.service
```

Autostart ausschalten und Anzeige stoppen:

```bash
sudo systemctl disable --now pi-status-display.service
```

Letzte Fehlermeldungen ansehen:

```bash
sudo journalctl -u pi-status-display.service -n 50 --no-pager
```

| Problem | Was prüfen? |
|---|---|
| Kein `/dev/spidev0.0` | SPI aktivieren und neu starten |
| Display bleibt dunkel | Verkabelung bei ausgeschaltetem Gerät prüfen, danach Fehlermeldungen ansehen |
| Bild steht auf dem Kopf | `rotation` zwischen 90 und 270 wechseln und Dienst neu starten |
| Instabiles Bild | `spi_hz` versuchsweise auf 24000000 reduzieren |
| Punkt orange | Kein Dienst konfiguriert, Abfrage nicht ausführbar oder Zeitüberschreitung |
| Punkt rot | Dienstname und Dienststatus prüfen; negative systemctl-/Docker-Rückgaben gelten als inaktiv |
| Werte fehlen | Fehlende Messwerte erscheinen als `--` oder `UNBEKANNT` |

Starte den manuellen Display-Test nie gleichzeitig mit dem Anzeigedienst. `--once` schreibt nur ein Bild und schaltet beim Beenden die Hintergrundbeleuchtung aus.

Der Power-Wert zeigt Unterspannungs-/Drosselungsinformationen aus `vcgencmd get_throttled`, keine Leistung in Watt. `VERLAUF!` bedeutet, dass seit dem letzten Boot ein entsprechendes Problem gespeichert wurde.

## Hinweise für Entwickler

Python >= 3.9, Pillow und eine skalierbare Schrift werden benötigt. Auf dem Raspberry wird DejaVu Sans verwendet. Softwaretests benötigen keine SPI-/GPIO-Hardware:

```bash
cd /opt/pi-status-display
PYTHONPATH=src ./.venv/bin/python -m unittest discover -s tests -v
```

Der Release enthält 13 Softwaretests. Quellcode steht unter `src/pi_status_display`, Tests unter `tests`. Diese Anleitung erstellt bewusst eine eigene allgemeine Konfiguration und Dienstdatei. Die unveränderten Release-Archive enthalten daneben ältere anwendungsspezifische Beispiele.
