import unittest
from unittest.mock import patch
from cryptography.exceptions import InvalidTag
from secret_crypto import seal,unseal
class SecretCryptoTests(unittest.TestCase):
    @patch.dict("os.environ",{"ZRADIUS_SECRET_KEY":"ab"*32})
    def test_roundtrip_and_binding(self):
        secret="a"*128
        a=seal(secret,"nas:192.0.2.1")
        self.assertNotEqual(a,seal(secret,"nas:192.0.2.1"))
        self.assertEqual(unseal(a,"nas:192.0.2.1"),secret)
        with self.assertRaises(InvalidTag):
            unseal(a,"nas:192.0.2.2")
        with self.assertRaises(ValueError):
            unseal(secret,"nas:192.0.2.1")
