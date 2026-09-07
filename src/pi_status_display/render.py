from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 320, 170
BG = '#101820'
CARD = '#1d2a36'
TEXT = '#f3f6fa'
MUTED = '#c3ceda'
GREEN = '#45dc82'
RED = '#ff5555'
ORANGE = '#ffbd45'
LABEL_SIZE = 15


@lru_cache(maxsize=16)
def _font(size, bold=False):
    name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
    candidates = [
        str(Path('/usr/share/fonts/truetype/dejavu') / name),
        name,
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    raise RuntimeError('Keine skalierbare Schrift gefunden; fonts-dejavu-core installieren.')


def _text(draw, box, text, font, color=TEXT, align='left'):
    """Place the actual glyph bounding box inside a reserved rectangle."""
    x0, y0, x1, y1 = box
    text = str(text)
    def bounds(value):
        return draw.textbbox((0, 0), value, font=font)
    left, top, right, bottom = bounds(text)
    if right - left > x1 - x0:
        while text and bounds(text + '…')[2] - bounds(text + '…')[0] > x1 - x0:
            text = text[:-1]
        text += '…'
        left, top, right, bottom = bounds(text)
    width, height = right - left, bottom - top
    if height > y1 - y0 or width > x1 - x0:
        raise ValueError(f'Text passt nicht in den Layoutbereich: {text!r}')
    x = (x1 - width if align == 'right' else
         x0 + (x1 - x0 - width) // 2 if align == 'center' else x0)
    y = y0 + (y1 - y0 - height) // 2
    draw.text((x - left, y - top), text, font=font, fill=color)


def _card(draw, box, label, value, color=TEXT):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=7, fill=CARD)
    _text(draw, (x0 + 8, y0 + 3, x1 - 8, y0 + 21), label, _font(LABEL_SIZE), MUTED)
    # Preserve long IP addresses and power messages by fitting only card values.
    font = _font(20, True)
    for size in range(20, 10, -1):
        font = _font(size, True)
        bounds = draw.textbbox((0, 0), str(value), font=font)
        if bounds[2] - bounds[0] <= x1 - x0 - 16:
            break
    _text(draw, (x0 + 8, y0 + 23, x1 - 8, y1 - 4), value, font, color)


def _percent(value):
    return '--' if value is None else f'{value:.0f}%'


def render_status(host_label, status):
    """Render the existing SystemStatus data as a 320 x 170 RGB image."""
    image = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    # service_states() inserts entries in configuration order. None/empty = unknown.
    first_state = next(iter(status.services.values()), None)
    dot_color = GREEN if first_state is True else RED if first_state is False else ORANGE
    draw.ellipse((7, 11, 17, 21), fill=dot_color)
    _text(draw, (24, 4, 252, 28), host_label, _font(19, True))
    _text(draw, (258, 4, 313, 28), datetime.now().strftime('%H:%M'), _font(17), align='right')

    temperature = status.temperature_c
    temp_text = '--' if temperature is None else f'{temperature:.1f} °C'
    temp_color = (ORANGE if temperature is None else
                  GREEN if temperature < 60 else ORANGE if temperature <= 75 else RED)
    power = status.power
    power_color = GREEN if power.healthy else ORANGE
    if power.raw is not None and power.raw & 0xF:
        power_color = RED

    _card(draw, (6, 33, 157, 83), 'IP-ADRESSE', status.ip_address)
    _card(draw, (163, 33, 314, 83), 'UPTIME', status.uptime)
    _card(draw, (6, 89, 157, 139), 'CPU TEMP', temp_text, temp_color)
    _card(draw, (163, 89, 314, 139), 'POWER', power.label, power_color)

    # One footer only: same font as card labels, no service row.
    font = _font(LABEL_SIZE)
    storage_label = getattr(status, 'storage_label', 'DISK')
    if storage_label not in ('SD', 'DISK', 'NVMe'):
        storage_label = 'DISK'
    footer = (
        ((7, 146, 101, 164), f'CPU {_percent(status.cpu_percent)}', 'left'),
        ((110, 146, 210, 164), f'RAM {_percent(status.ram_percent)}', 'center'),
        ((214, 146, 314, 164), f'{storage_label} {_percent(getattr(status, "storage_percent", None))}', 'right'),
    )
    for box, text, align in footer:
        _text(draw, box, text, font, align=align)
    return image
