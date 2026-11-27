import unittest
from legacy_radius import assess

class LegacyRadiusTests(unittest.TestCase):
    def setUp(self):
        self.checks=[{"attribute":"Cleartext-Password","op":":=","value":None}]
        self.replies=[{"attribute":k,"op":":=","value":v} for k,v in [("Mikrotik-Rate-Limit","100M/100M"),("Framed-Pool","pppoe"),("Acct-Interim-Interval","300")]]
    def test_compatible_is_not_apply(self):
        r=assess(self.checks,self.replies,[],False)
        self.assertTrue(r["attributes_compatible"])
        self.assertFalse(r["can_apply"])
    def test_group_blocks(self):
        self.assertFalse(assess(self.checks,self.replies,[{"groupname":"test"}],False)["attributes_compatible"])
    def test_unknown_check_blocks(self):
        self.assertFalse(assess(self.checks+[{"attribute":"Simultaneous-Use","op":":=","value":None}],self.replies,[],False)["attributes_compatible"])
    def test_duplicate_reply_blocks(self):
        self.assertFalse(assess(self.checks,self.replies+self.replies[:1],[],False)["attributes_compatible"])
    def test_disabled_reject(self):
        self.assertTrue(assess(self.checks+[{"attribute":"Auth-Type","op":":=","value":"Reject"}],self.replies,[],True)["attributes_compatible"])
    def test_no_interval_blocks(self):
        self.assertFalse(assess(self.checks,self.replies[:2],[],False)["attributes_compatible"])
