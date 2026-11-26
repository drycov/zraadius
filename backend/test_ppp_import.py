import unittest
from ppp_import import parse_export

class ImportTests(unittest.TestCase):
    def test_profiles_and_secrets(self):
        rows=parse_export('/ppp profile\nadd name=offices remote-address=office-pool\n/ppp secret\nadd name=test service=l2tp profile=offices comment="office client" password=hidden')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1]["comment"],"office client")
        self.assertNotIn("hidden",str(rows))
        self.assertFalse(rows[1]["issues"])
    def test_unsafe_or_ambiguous(self):
        rows=parse_export('/ppp secret\nadd name=one service=any\nadd name=two service=l2tp routes=foo\nadd name=three service=l2tp password=$var')
        self.assertTrue(all(r["issues"] for r in rows))
    def test_continuation(self):
        rows=parse_export('/ppp secret\nadd name=one \\\n    service=l2tp profile=offices')
        self.assertEqual(rows[0]["service"],"l2tp")
    def test_no_ppp(self):
        with self.assertRaises(ValueError):
            parse_export('/ip address\nadd address=10.0.0.1/24')
