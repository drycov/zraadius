"""Machine identity: explicit endpoint permissions."""
import re
import secrets
from iam import token_digest

PREFIX="zrs_"
ROUTES={
    ("GET","/api/v1/dashboard"):"dashboard:read",
    ("GET","/api/v1/users"):"users:read",
    ("GET","/api/v1/users/{username}"):"users:read",
    ("POST","/api/v1/users"):"users:create",
    ("PUT","/api/v1/users/{username}/state"):"users:state",
    ("PUT","/api/v1/users/{username}/password"):"users:password",
    ("PUT","/api/v1/users/{username}/groups/{group}"):"users:groups",
    ("DELETE","/api/v1/users/{username}/groups/{group}"):"users:groups",
    ("GET","/api/v1/groups"):"groups:read",
    ("GET","/api/v1/groups/{group}/profile"):"groups:read",
    ("GET","/api/v1/nas"):"nas:read",
    ("GET","/api/v1/accounting"):"accounting:read",
    ("GET","/api/v1/coa"):"coa:read",
    ("POST","/api/v1/sessions/{session_id}/disconnect"):"sessions:disconnect",
    ("POST","/api/v1/sessions/{session_id}/rate"):"sessions:rate",
}
SCOPES=frozenset(ROUTES.values())

def issue_token():
    token=PREFIX+secrets.token_urlsafe(32)
    return token,token_digest(token)

def valid_token(token):
    return bool(re.fullmatch(r"zrs_[A-Za-z0-9_-]{43}",token))

def allowed(scopes,method,route):
    required=ROUTES.get((method,route))
    return required is not None and required in scopes
