import unittest
from directory_reconcile import plan_identities

GUID="11111111-2222-3333-4444-555555555555"
ROW={"identity_id":1,"object_guid":GUID,"directory_username":"old","directory_enabled":True}
ENTRY={"object_guid":GUID,"username":"new","directory_enabled":False,"compatible":True}

class DirectoryReconcileTests(unittest.TestCase):
    def test_changed(self):
        changes, summary = plan_identities([ROW],{"limited":False,"items":[ENTRY]})
        self.assertEqual(changes,[(1,"new",False)])
        self.assertEqual(summary["directory_disabled"],1)
    def test_missing_does_not_disable(self):
        changes, summary = plan_identities([ROW],{"limited":False,"items":[]})
        self.assertEqual(changes,[])
        self.assertEqual(summary["not_observed"],1)
    def test_truncated(self):
        with self.assertRaises(ValueError):
            plan_identities([ROW],{"limited":True,"items":[]})
    def test_duplicate(self):
        with self.assertRaises(ValueError):
            plan_identities([ROW],{"limited":False,"items":[ENTRY,ENTRY]})
    def test_incompatible_name_preserved(self):
        changes, _ = plan_identities([ROW],{"limited":False,"items":[dict(ENTRY,compatible=False)]})
        self.assertEqual(changes,[(1,"old",False)])

if __name__=="__main__":
    unittest.main()
