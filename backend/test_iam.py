import unittest
from iam import hash_password,verify_password,new_token,token_digest,permitted
class IamTests(unittest.TestCase):
    def test_password(self):
        password="test-password-long-enough"
        digest=hash_password(password)
        self.assertTrue(digest.startswith("$argon2id$"))
        self.assertTrue(verify_password(digest,password))
        self.assertFalse(verify_password(digest,"incorrect"))
    def test_session(self):
        token,digest=new_token()
        self.assertEqual(digest,token_digest(token))
        self.assertNotEqual(token,digest)
    def test_permissions(self):
        self.assertTrue(permitted("operator","POST","/api/v1/sessions/1/disconnect"))
        self.assertFalse(permitted("operator","POST","/api/v1/users"))
        self.assertFalse(permitted("auditor","GET","/api/v1/iam/users"))
        self.assertFalse(permitted("auditor","DELETE","/api/v1/nas/1"))

    def test_unknown_resources_denied(self):
        self.assertFalse(permitted("auditor","GET","/api/v1/future-secret-endpoint"))
        self.assertFalse(permitted("operator","POST","/api/v1/sessions/1/unexpected/disconnect"))
        self.assertTrue(permitted("auditor","GET","/api/v1/nas"))


class VpnDisconnectPermissionTests(unittest.TestCase):
    def test_vpn_disconnect(self):
        from iam import permitted
        path="/api/v1/ppp/sessions/42/disconnect"
        self.assertTrue(permitted("admin","POST",path))
        self.assertTrue(permitted("operator","POST",path))
        self.assertFalse(permitted("auditor","POST",path))
        self.assertFalse(permitted("operator","POST","/api/v1/ppp/sessions/42/rate"))
        self.assertFalse(permitted("operator","POST","/api/v1/ppp/sessions/abc/disconnect"))
