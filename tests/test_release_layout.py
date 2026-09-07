import unittest
from PIL import ImageColor, ImageChops, Image
from pi_status_display.render import render_status, BG, GREEN, RED, ORANGE
from pi_status_display.status import SystemStatus, PowerStatus


class ReleaseLayoutTests(unittest.TestCase):
    def status(self, services, label='SD'):
        return SystemStatus('192.168.255.255', '1234d 23h', 48.6,
                            PowerStatus('OK', True, 0), 100, 100, services, label, 100)

    def test_first_service_colors_and_missing_status(self):
        for services, color in [({'first': True, 'second': False}, GREEN),
                                ({'first': False, 'second': True}, RED),
                                ({'first': None, 'second': True}, ORANGE), ({}, ORANGE)]:
            with self.subTest(services=services):
                image = render_status('Pi-hole', self.status(services))
                self.assertEqual(image.getpixel((12, 16)), ImageColor.getrgb(color))

    def test_footer_alignment_and_height_at_full_utilization(self):
        for label in ('SD', 'DISK', 'NVMe'):
            image = render_status('Pi-hole', self.status({'service': True}, label))
            self.assertEqual(image.size, (320, 170))
            difference = ImageChops.difference(image, Image.new('RGB', image.size, BG))
            self.assertIsNone(difference.crop((0, 164, 320, 170)).getbbox())
            cpu = difference.crop((0, 146, 105, 164)).getbbox()
            ram = difference.crop((105, 146, 213, 164)).getbbox()
            disk = difference.crop((213, 146, 320, 164)).getbbox()
            self.assertLessEqual(abs(cpu[0] - 7), 2)
            self.assertLessEqual(abs(105 + (ram[0] + ram[2]) / 2 - 160), 2)
            self.assertLessEqual(abs(213 + disk[2] - 314), 2)
