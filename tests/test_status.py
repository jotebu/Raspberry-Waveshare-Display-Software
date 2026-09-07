import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from pi_status_display.status import (
    _container_is_running, _process_is_running, cpu_temperature, ram_percent,
    service_states, storage_usage, uptime_text,
)


class StatusTests(unittest.TestCase):
    def test_uptime(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "uptime"
            path.write_text("90061.12 100.0")
            self.assertEqual(uptime_text(path), "1d 01h")


    @patch("pi_status_display.status.subprocess.run", side_effect=FileNotFoundError)
    def test_temperature(self, _run: Mock) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "temp"
            path.write_text("48750")
            self.assertEqual(cpu_temperature(path), 48.75)


    def test_ram(self) -> None:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "meminfo"
            path.write_text("MemTotal: 1000 kB\nMemAvailable: 250 kB\n")
            self.assertEqual(ram_percent(path), 75.0)

    @patch("pi_status_display.status.shutil.disk_usage")
    def test_nvme_storage(self, disk_usage: Mock) -> None:
        disk_usage.return_value = Mock(total=1000, used=425)
        with TemporaryDirectory() as folder:
            mounts = Path(folder) / "mounts"
            mounts.write_text("/dev/nvme0n1p2 / ext4 rw 0 0\n")
            self.assertEqual(storage_usage("/", mounts), ("NVMe", 42.5))

    @patch("pi_status_display.status.shutil.disk_usage")
    def test_sd_storage(self, disk_usage: Mock) -> None:
        disk_usage.return_value = Mock(total=100, used=37)
        with TemporaryDirectory() as folder:
            mounts = Path(folder) / "mounts"
            mounts.write_text("/dev/mmcblk0p2 / ext4 rw 0 0\n")
            self.assertEqual(storage_usage("/", mounts), ("SD", 37.0))

    def test_process_detection(self) -> None:
        with TemporaryDirectory() as folder:
            proc = Path(folder)
            (proc / "123").mkdir()
            (proc / "123" / "comm").write_text("mediamtx\n")
            self.assertTrue(_process_is_running("mediamtx", proc))
            self.assertFalse(_process_is_running("missing", proc))

    @patch("pi_status_display.status.subprocess.run")
    def test_container_detection(self, run: Mock) -> None:
        run.return_value = Mock(returncode=0, stdout="true\n")
        self.assertTrue(_container_is_running("mediamtx"))
        run.assert_called_once()

    @patch("pi_status_display.status._container_is_running", return_value=True)
    def test_container_display_label(self, _running: Mock) -> None:
        states = service_states(["container:mjpeg-gateway|MJPEG-Gateway"])
        self.assertEqual(states, {"MJPEG-Gateway": True})


if __name__ == "__main__":
    unittest.main()
