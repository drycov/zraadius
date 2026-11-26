"""Generate high-entropy vouchers and FreeRADIUS SSHA512-Password values."""
import secrets
import hashlib
import base64

def voucher_credentials():
    username="hs-"+secrets.token_hex(10)
    password=secrets.token_hex(16)
    salt=secrets.token_bytes(16)
    # FreeRADIUS SSHA512-Password: base64 digest followed by salt.
    encoded=base64.b64encode(hashlib.sha512(password.encode()+salt).digest()+salt).decode("ascii")
    return username,password,encoded
