import unittest
from ipoe import normalize_mac,normalize_ip

class TestIpoe(unittest.TestCase):
    def test_formats(self):
        for value in ("02AABBCCDDEE","02:aa:bb:cc:dd:ee","02-AA-BB-CC-DD-EE","02aa.bbcc.ddee"):
            self.assertEqual(normalize_mac(value),"02:aa:bb:cc:dd:ee")
    def test_invalid(self):
        for value in ("ff:ff:ff:ff:ff:ff","00:00:00:00:00:00","01:00:00:00:00:01","02-aa:bb-cc-dd-ee","bad"):
            with self.assertRaises(ValueError):
                normalize_mac(value)
    def test_ip(self):
        self.assertEqual(normalize_ip("100.64.0.10"),"100.64.0.10")
        for value in ("127.0.0.1","0.0.0.0","224.0.0.1","::1","255.255.255.255"):
            with self.assertRaises(ValueError):
                normalize_ip(value)

if __name__=="__main__":
    unittest.main()
