import unittest
import hashlib
import base64
from hotspot import voucher_credentials

class TestVoucher(unittest.TestCase):
    def test_digest(self):
        u,p,h=voucher_credentials()
        raw=base64.b64decode(h)
        self.assertEqual(len(raw),80)
        self.assertEqual(raw[:64],hashlib.sha512(p.encode()+raw[64:]).digest())
        self.assertRegex(u,r"^hs-[a-f0-9]{20}$")
        self.assertEqual(len(p),32)
        self.assertNotEqual(voucher_credentials()[0],u)
