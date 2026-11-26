import unittest
from ipam import pool_bounds,next_address

class TestIPAM(unittest.TestCase):
    def test_ipv4(self):
        self.assertEqual(pool_bounds("100.64.0.0/30"),("100.64.0.0/30","100.64.0.1","100.64.0.2",2))
    def test_ipv6(self):
        self.assertEqual(pool_bounds("2001:db8::/64")[3],2**64-1)
    def test_invalid(self):
        for args in [("10.0.0.1/24",),("10.0.0.0/24","10.0.1.1"),("10.0.0.0/24","10.0.0.0"),("10.0.0.0/24","10.0.0.9","10.0.0.2")]:
            with self.assertRaises(ValueError):pool_bounds(*args)
    def test_allocate(self):
        self.assertEqual(next_address("10.0.0.1","10.0.0.4",["10.0.0.1","10.0.0.3"]),"10.0.0.2")
        self.assertIsNone(next_address("10.0.0.1","10.0.0.1",["10.0.0.1"]))
        self.assertEqual(next_address("2001:db8::1","2001:db8::ffff",["2001:db8::1"]),"2001:db8::2")
