"""LDAP-specific encrypted credentials, separate from NAS secret format."""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from secret_crypto import key

def seal_bind(password,profile_id,host,bind_dn):
    raw=password.encode("utf-8")
    if not 1<=len(raw)<=1024 or b"\x00" in raw:
        raise ValueError("Invalid bind password")
    nonce=os.urandom(12)
    aad=f"ldap:{profile_id}:{host}:{bind_dn}".encode()
    return "v1:"+base64.urlsafe_b64encode(nonce+AESGCM(key()).encrypt(nonce,raw,aad)).decode("ascii")

def open_bind(value,profile_id,host,bind_dn):
    if not value.startswith("v1:"):
        raise ValueError("Unsupported bind secret")
    raw=base64.b64decode(value[3:],altchars=b"-_",validate=True)
    return AESGCM(key()).decrypt(raw[:12],raw[12:],f"ldap:{profile_id}:{host}:{bind_dn}".encode()).decode("utf-8")
