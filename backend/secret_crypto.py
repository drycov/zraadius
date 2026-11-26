"""Versioned AES-256-GCM envelopes; bind ciphertext to its record identity."""
import os
import re
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def key():
    raw=os.environ.get("ZRADIUS_SECRET_KEY","")
    if not re.fullmatch(r"[0-9a-fA-F]{64}",raw):
        raise ValueError("ZRADIUS_SECRET_KEY must be 32 random bytes encoded as hex")
    return bytes.fromhex(raw)

def seal(value,identity):
    if not re.fullmatch(r"[A-Za-z0-9]{32,128}",value):
        raise ValueError("Invalid shared secret")
    nonce=os.urandom(12)
    return "v1:"+base64.urlsafe_b64encode(nonce+AESGCM(key()).encrypt(nonce,value.encode("ascii"),identity.encode())).decode("ascii")

def unseal(value,identity):
    if not value.startswith("v1:"):
        raise ValueError("Unencrypted or unsupported secret")
    data=base64.b64decode(value[3:],altchars=b"-_",validate=True)
    result=AESGCM(key()).decrypt(data[:12],data[12:],identity.encode()).decode("ascii")
    if not re.fullmatch(r"[A-Za-z0-9]{32,128}",result):
        raise ValueError("Invalid decrypted secret")
    return result
