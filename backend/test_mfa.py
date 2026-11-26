import unittest
from unittest.mock import patch
from mfa import otp,match_step,new_seed,seed_from_envelope,recovery_codes
class MfaTests(unittest.TestCase):
    def test_vector_and_replay(self):
        seed=b"12345678901234567890"
        self.assertEqual(otp(seed,1),"287082")
        self.assertEqual(match_step(seed,"287082",now=59),1)
        self.assertIsNone(match_step(seed,"287082",last_step=1,now=59))
    @patch.dict("os.environ",{"ZRADIUS_SECRET_KEY":"ab"*32})
    def test_enrollment(self):
        envelope,seed=new_seed(1)
        self.assertEqual(len(seed),32)
        self.assertEqual(len(seed_from_envelope(envelope,1)),20)
    def test_recovery(self):
        codes,digests=recovery_codes()
        self.assertEqual(len(set(codes)),10)
        self.assertEqual(len(set(digests)),10)
        self.assertNotEqual(codes,digests)
