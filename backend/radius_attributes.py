"""Explicit, typed RADIUS attribute planning catalog. No runtime enforcement."""
import re
from ipaddress import IPv4Address

def entry(name,vendor,kind,lists,minimum=None,maximum=None,pattern=None):
    return dict(name=name,vendor=vendor,type=kind,lists=lists,min=minimum,max=maximum,pattern=pattern)

CATALOG={r["name"]:r for r in [
    entry("Mikrotik-Rate-Limit",14988,"string",["reply"],pattern=r"[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M"),
    entry("Mikrotik-Group",14988,"string",["reply"],pattern=r"[A-Za-z0-9_.-]{1,64}"),
    entry("Framed-Pool",0,"string",["reply"],pattern=r"[A-Za-z0-9_.-]{1,64}"),
    entry("Filter-Id",0,"string",["reply"],pattern=r"[A-Za-z0-9_.-]{1,64}"),
    entry("Framed-IP-Address",0,"ipv4",["reply"]),
    entry("Acct-Interim-Interval",0,"integer",["reply"],60,86400),
    entry("Idle-Timeout",0,"integer",["reply"],1,604800),
    entry("Session-Timeout",0,"integer",["reply"],1,604800),
    entry("Simultaneous-Use",0,"integer",["control"],1,100),
    entry("Tunnel-Private-Group-Id",0,"integer",["reply"],1,4094),
    entry("NAS-IP-Address",0,"ipv4",["check"]),
    entry("Calling-Station-Id",0,"string",["check"],pattern=r"[A-Za-z0-9_.:@-]{1,253}"),
]}
OPERATORS={"reply":(":=",),"control":(":=",),"check":("==","!=")}

def catalog():
    return [{**row,"list":row["lists"][0],"operators":{k:list(OPERATORS[k]) for k in row["lists"]},"runtime_enforced":False} for row in CATALOG.values()]

def validate(name,attribute_list,operator,value):
    row=CATALOG.get(name)
    if row is None:
        raise ValueError("Attribute is not in the supported planning catalog")
    if attribute_list not in row["lists"] or operator not in OPERATORS[attribute_list]:
        raise ValueError("Unsupported attribute list or operator")
    if not isinstance(value,str) or not 1<=len(value)<=253 or any(ord(c)<32 or 127<=ord(c)<=159 for c in value):
        raise ValueError("Invalid attribute value")
    if row["type"]=="integer":
        if not re.fullmatch(r"[0-9]{1,10}",value):
            raise ValueError("Expected decimal integer")
        number=int(value)
        if not row["min"]<=number<=row["max"]:
            raise ValueError("Integer outside supported range")
        value=str(number)
    elif row["type"]=="ipv4":
        try:
            value=str(IPv4Address(value))
        except ValueError:
            raise ValueError("Expected IPv4 address") from None
    elif row["pattern"] and not re.fullmatch(row["pattern"],value):
        raise ValueError("Value does not match supported format")
    return {"name":name,"list":attribute_list,"operator":operator,"value":value,"vendor":row["vendor"],"runtime_enforced":False}
