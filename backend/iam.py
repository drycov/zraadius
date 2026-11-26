"""Management authentication, independent of RADIUS identities."""
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
def hash_password(password):
    if not 16<=len(password)<=128:
        raise ValueError("Password must contain 16-128 characters")
    return hasher.hash(password)
def verify_password(encoded,password):
    try:
        return hasher.verify(encoded,password)
    except (VerificationError,InvalidHashError):
        return False
def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()
def new_token():
    token=secrets.token_urlsafe(32)
    return token,token_digest(token)
# Explicit resource/action allowlist; unknown endpoints deny non-admin roles.
READ_RESOURCES=frozenset({"identities","dashboard","users","groups","nas","accounting","coa","services","dictionaries","audit","ipoe","ipam","hotspot","device-aaa","ppp","eap","pki","proxy"})
def permission(method,path):
    parts=path.strip("/").split("/")
    if len(parts)<3 or parts[:2]!=["api","v1"]:
        return None
    resource=parts[2]
    if method=="GET" and resource in READ_RESOURCES:
        return resource+":read"
    if method=="POST" and len(parts)==5 and resource=="sessions" and parts[3].isdigit() and parts[4] in ("disconnect","rate"):
        return "sessions:"+parts[4]
    if method=="POST" and len(parts)==6 and resource=="ppp" and parts[3]=="sessions" and parts[4].isdigit() and parts[5]=="disconnect":
        return "sessions:disconnect"
    return None
def permitted(role,method,path):
    if role=="admin":
        return True
    code=permission(method,path)
    if role not in ("operator","auditor") or code is None:
        return False
    return code.endswith(":read") or (role=="operator" and code in ("sessions:disconnect","sessions:rate"))
