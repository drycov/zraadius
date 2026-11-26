import re
import ipaddress

def normalize_mac(value: str) -> str:
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{12}|(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}|(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4})",value):
        raise ValueError("Invalid MAC format")
    raw=re.sub(r"[:.\-]","",value).lower()
    if raw=="000000000000" or int(raw[:2],16)&1:
        raise ValueError("MAC must be nonzero unicast")
    return ":".join(raw[i:i+2] for i in range(0,12,2))

def normalize_ip(value: str | None) -> str | None:
    if value is None:
        return None
    ip=ipaddress.IPv4Address(value)
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local or int(ip)==0xffffffff:
        raise ValueError("Invalid subscriber IPv4")
    return str(ip)
