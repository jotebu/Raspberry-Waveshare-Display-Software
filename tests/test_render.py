import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pi_status_display.config import load_config
from pi_status_display.render import HEIGHT, WIDTH, render_status
from pi_status_display.status import PowerStatus, SystemStatus


class LandscapeTests(unittest.TestCase):
    def test_render_size_is_landscape(self) -> None:
        status = SystemStatus(
            ip_address="192.168.55.79",
            uptime="11d 12h",
            temperature_c=54.2,
            power=PowerStatus("OK", True, 0),
            cpu_percent=23.0,
            ram_percent=31.0,
            services={"MediaMTX": True, "MJPEG-Gateway": True},
            storage_label="NVMe",
            storage_percent=42.0,
        )
        image = render_status("MediaMTX", status)
        self.assertEqual((WIDTH, HEIGHT), (320, 170))
        self.assertEqual(image.size, (320, 170))

    def test_landscape_rotations(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "host.json"
            for rotation in (90, 270):
                path.write_text(json.dumps({
                    "host_label": "Test", "display": {"rotation": rotation}
                }))
                self.assertEqual(load_config(path).display.rotation, rotation)

    def test_portrait_rotation_is_rejected(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "host.json"
            path.write_text(json.dumps({
                "host_label": "Test", "display": {"rotation": 0}
            }))
            with self.assertRaisesRegex(ValueError, "Querformat"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
