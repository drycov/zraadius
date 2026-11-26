import unittest
from routeros_ppp import generate,local_secret_commands

class RouterosConfigTests(unittest.TestCase):
    def test_review_only(self):
        sections=generate("10.216.40.3","10.216.40.1","10.216.40.4",300,True)
        self.assertIn("src-address=10.216.40.1",sections[1]["commands"])
        self.assertIn("REPLACE_WITH_NAS_SHARED_SECRET",sections[1]["commands"])
        for section in sections[1:]:
            self.assertTrue(all(line.startswith("#") for line in section["commands"].splitlines()))
    def test_invalid_input(self):
        for ip in ("127.0.0.1","10.0.0.1; /system reboot","::1"):
            with self.assertRaises(ValueError):
                generate(ip,"10.216.40.1")
        with self.assertRaises(ValueError):
            generate("10.216.40.3","10.216.40.1",disconnect=True)
    def test_user(self):
        commands=local_secret_commands("vpn-test")
        self.assertIn('service=l2tp',commands["cutover"])
        self.assertTrue(commands["rollback"].startswith("#"))
        with self.assertRaises(ValueError):
            local_secret_commands('bad"')
