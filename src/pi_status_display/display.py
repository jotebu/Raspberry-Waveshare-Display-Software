from __future__ import annotations

import time
from typing import Iterable

from PIL import Image

from .config import DisplayConfig


class ST7789V2Display:
    """Minimal driver for Waveshare's 170x320 ST7789V2 module."""

    orientations = {
        0: (0x00, 170, 320, 35, 0),
        90: (0x60, 320, 170, 0, 35),
        180: (0xC0, 170, 320, 35, 0),
        270: (0xA0, 320, 170, 0, 35),
    }

    def __init__(self, config: DisplayConfig):
        try:
            import spidev
            from gpiozero import DigitalOutputDevice, PWMOutputDevice
        except ImportError as exc:
            raise RuntimeError("SPI/GPIO-Bibliotheken fehlen; bitte Installation ausführen") from exc

        self.config = config
        (self.madctl, self.width, self.height,
         self.x_offset, self.y_offset) = self.orientations[config.rotation]
        self.dc = DigitalOutputDevice(config.dc_gpio, initial_value=False)
        self.reset = DigitalOutputDevice(config.reset_gpio, initial_value=True)
        self.backlight = PWMOutputDevice(config.backlight_gpio, frequency=1000, initial_value=0)
        self.spi = spidev.SpiDev()
        self.spi.open(config.spi_bus, config.spi_device)
        self.spi.max_speed_hz = config.spi_hz
        self.spi.mode = 0
        self.spi.no_cs = False
        self._initialize()
        self.backlight.value = config.brightness

    def _write(self, data: Iterable[int], is_data: bool) -> None:
        self.dc.value = is_data
        payload = list(data)
        for start in range(0, len(payload), 4096):
            self.spi.writebytes2(payload[start:start + 4096])

    def _command(self, command: int, *data: int) -> None:
        self._write([command], False)
        if data:
            self._write(data, True)

    def _initialize(self) -> None:
        self.reset.off(); time.sleep(0.01)
        self.reset.on(); time.sleep(0.12)
        self._command(0x11); time.sleep(0.12)  # sleep out
        self._command(0x36, self.madctl)
        self._command(0x3A, 0x05)              # RGB565
        self._command(0xB2, 0x0C, 0x0C, 0x00, 0x33, 0x33)
        self._command(0xB7, 0x35)
        self._command(0xBB, 0x35)
        self._command(0xC0, 0x2C)
        self._command(0xC2, 0x01)
        self._command(0xC3, 0x13)
        self._command(0xC4, 0x20)
        self._command(0xC6, 0x0F)
        self._command(0xD0, 0xA4, 0xA1)
        self._command(0xE0, 0xD0, 0x00, 0x05, 0x0E, 0x15, 0x0D, 0x37,
                      0x43, 0x47, 0x09, 0x15, 0x12, 0x16, 0x19)
        self._command(0xE1, 0xD0, 0x00, 0x05, 0x0D, 0x0C, 0x06, 0x2D,
                      0x44, 0x40, 0x0E, 0x1C, 0x18, 0x16, 0x19)
        self._command(0x21)                    # display inversion on
        self._command(0x13)                    # normal display mode
        self._command(0x29); time.sleep(0.02)  # display on

    def show(self, image: Image.Image) -> None:
        if image.size != (self.width, self.height):
            raise ValueError(f"Bild muss {self.width}x{self.height} Pixel groß sein")
        x0, y0 = self.x_offset, self.y_offset
        x1, y1 = x0 + self.width - 1, y0 + self.height - 1
        self._command(0x2A, x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)
        self._command(0x2B, y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)
        self._command(0x2C)
        pixels = bytearray(self.width * self.height * 2)
        for index, (red, green, blue) in enumerate(image.convert("RGB").getdata()):
            rgb565 = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
            pixels[index * 2] = rgb565 >> 8
            pixels[index * 2 + 1] = rgb565 & 0xFF
        self._write(pixels, True)

    def close(self) -> None:
        try:
            self.backlight.off()
            self.spi.close()
        finally:
            self.dc.close(); self.reset.close(); self.backlight.close()

    def __enter__(self) -> "ST7789V2Display":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
