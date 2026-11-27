import unittest
from attribute_resolution import resolve

def row(value,source="group",priority=100,nas_id=None,policy_id=1):
    return dict(name="Idle-Timeout",attribute_list="reply",operator=":=",value=value,source=source,priority=priority,nas_id=nas_id,policy_id=policy_id,enabled=True)

class ResolutionTests(unittest.TestCase):
    def test_direct(self):
        self.assertEqual(resolve([row("30"),row("60","identity")])["effective"][0]["value"],"60")
    def test_conflict(self):
        self.assertEqual(len(resolve([row("30"),row("60",policy_id=2)])["conflicts"]),1)
    def test_specific(self):
        self.assertEqual(resolve([row("30"),row("60",nas_id=1)])["effective"][0]["value"],"60")
    def test_priority(self):
        self.assertEqual(resolve([row("30"),row("60",priority=101)])["effective"][0]["value"],"60")
    def test_disabled(self):
        self.assertEqual(resolve([{**row("30"),"enabled":False}])["effective"],[])
    def test_no_runtime(self):
        self.assertFalse(resolve([])["can_apply"])
