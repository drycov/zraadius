"""RFC 6238 TOTP and encrypted seed storage."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
import re
from urllib.parse import quote
from secret_crypto import seal, unseal

def new_seed(user_id):
    raw=secrets.token_hex(20)
    return seal(raw,f"mfa:{user_id}"),base64.b32encode(bytes.fromhex(raw)).decode()

def seed_from_envelope(envelope,user_id):
    return bytes.fromhex(unseal(envelope,f"mfa:{user_id}"))

def otp(seed,step):
    digest=hmac.new(seed,struct.pack(">Q",step),hashlib.sha1).digest()
    offset=digest[-1]&15
    return f"{(struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}"

def match_step(seed,code,last_step=-1,now=None):
    if not re.fullmatch(r"[0-9]{6}",code):
        return None
    current=int(time.time() if now is None else now)//30
    for step in (current,current-1,current+1):
        if step>last_step and step>=0 and hmac.compare_digest(otp(seed,step),code):
            return step
    return None

def recovery_codes():
    codes=[secrets.token_hex(16) for _ in range(10)]
    return codes,[hashlib.sha256(c.encode()).hexdigest() for c in codes]

def uri(username,seed):
    return "otpauth://totp/"+quote("ZRADIUS:"+username,safe="")+"?secret="+seed+"&issuer=ZRADIUS&algorithm=SHA1&digits=6&period=30"
