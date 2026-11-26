"""Credential helpers for PPP PAP and MS-CHAPv2."""
import base64
import hashlib
import secrets
import ipaddress

def credentials(password):
    # NT hash is required by MS-CHAPv2; use OpenSSL legacy MD4 via a portable library.
    from Crypto.Hash import MD4
    raw=password.encode("utf-8")
    if not 16<=len(password)<=128 or len(raw)>128 or "\x00" in password:
        raise ValueError("Password must contain 16–128 characters and at most 128 UTF-8 bytes")
    salt=secrets.token_bytes(16)
    nt=MD4.new(password.encode("utf-16le")).hexdigest()
    return nt,base64.b64encode(hashlib.sha512(raw+salt).digest()+salt).decode("ascii")

def static_address(value):
    if value is None:
        return None
    ip=ipaddress.IPv4Address(value)
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local or int(ip)==0xffffffff:
        raise ValueError("Invalid static IPv4")
    return str(ip)
