import unittest
from service_tokens import issue_token,valid_token,allowed,SCOPES
from iam import token_digest
class ServiceTokenTests(unittest.TestCase):
    def test_token(self):
        t,h=issue_token()
        self.assertTrue(valid_token(t))
        self.assertEqual(token_digest(t),h)
        self.assertNotEqual(t,h)
        self.assertNotEqual(t,issue_token()[0])
    def test_scope(self):
        self.assertTrue(allowed(["users:state"],"PUT","/api/v1/users/{username}/state"))
        self.assertFalse(allowed(["users:read"],"PUT","/api/v1/users/{username}/state"))
        self.assertFalse(allowed(SCOPES,"GET","/api/v1/iam/me"))
        self.assertFalse(allowed(SCOPES,"DELETE","/api/v1/users/{username}"))
        self.assertFalse(allowed(SCOPES,"GET","/api/v1/users/new-endpoint"))
