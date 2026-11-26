import unittest
import hashlib
import base64
from ppp_vpn import credentials,static_address
class PppTests(unittest.TestCase):
    def test_hash(self):
        password="A-secure-test-password"
        nt,digest=credentials(password)
        from Crypto.Hash import MD4
        self.assertEqual(nt,MD4.new(password.encode("utf-16le")).hexdigest())
        raw=base64.b64decode(digest)
        self.assertEqual(len(raw),80)
        self.assertEqual(raw[:64],hashlib.sha512(password.encode()+raw[64:]).digest())
        self.assertNotEqual(digest,credentials(password)[1])
    def test_validation(self):
        with self.assertRaises(ValueError):credentials("short")
        with self.assertRaises(ValueError):static_address("127.0.0.1")
        with self.assertRaises(ValueError):static_address("2001:db8::1")
        self.assertEqual(static_address("10.216.71.240"),"10.216.71.240")
