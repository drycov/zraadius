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
def permitted(role,method,path):
    if role=="admin":
        return True
    if role not in ("operator","auditor"):
        return False
    if path.startswith("/api/v1/iam/"):
        return False
    if method=="GET":
        return True
    return role=="operator" and method=="POST" and path.startswith("/api/v1/sessions/") and path.endswith(("/disconnect","/rate"))
