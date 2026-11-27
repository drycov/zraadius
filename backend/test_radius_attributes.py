import unittest
from radius_attributes import validate,catalog

class RadiusAttributeTests(unittest.TestCase):
    def test_catalog(self):
        self.assertTrue(all(not r["runtime_enforced"] for r in catalog()))
    def test_integer_normalization(self):
        self.assertEqual(validate("Simultaneous-Use","control",":=","01")["value"],"1")
    def test_integer_range(self):
        with self.assertRaises(ValueError):
            validate("Simultaneous-Use","control",":=","0")
    def test_ip(self):
        self.assertEqual(validate("NAS-IP-Address","check","==","192.0.2.1")["value"],"192.0.2.1")
    def test_invalid_ip(self):
        with self.assertRaises(ValueError):
            validate("Framed-IP-Address","reply",":=","999.1.1.1")
    def test_operator(self):
        with self.assertRaises(ValueError):
            validate("Filter-Id","reply","+=","read")
    def test_list(self):
        with self.assertRaises(ValueError):
            validate("Simultaneous-Use","reply",":=","1")
    def test_secret_rejected(self):
        with self.assertRaises(ValueError):
            validate("Cleartext-Password","control",":=","secret")
    def test_vsa(self):
        self.assertEqual(validate("Mikrotik-Rate-Limit","reply",":=","100M/100M")["vendor"],14988)
