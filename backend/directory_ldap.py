"""Read-only AD discovery. No password synchronization or RADIUS bind."""
import os
import re
import ssl
from uuid import UUID
from ldap3 import Server, Connection, Tls, SUBTREE, NONE


def _paged_entries(conn, base, filt, attributes, limit):
    """Bounded RFC 2696 search; reject incomplete or malformed responses."""
    oid = "1.2.840.113556.1.4.319"
    cookie = None
    seen = set()
    entries = []
    for _ in range(101):
        conn.search(base, filt, search_scope=SUBTREE, attributes=attributes,
                    paged_size=min(200, limit + 1), paged_cookie=cookie,
                    paged_criticality=True, time_limit=10)
        result = conn.result or {}
        if result.get("result") != 0:
            raise ValueError("LDAP search incomplete")
        control = result.get("controls", {}).get(oid, {}).get("value", {})
        if "cookie" not in control or not isinstance(control["cookie"], bytes):
            raise ValueError("LDAP pagination control missing or invalid")
        if any(x.get("type") != "searchResEntry" for x in conn.response):
            raise ValueError("LDAP search contains unsupported referrals")
        entries.extend(conn.entries)
        cookie = control["cookie"]
        if len(entries) > limit:
            return entries[:limit], True
        if not cookie:
            return entries, False
        if cookie in seen:
            raise ValueError("LDAP pagination cookie repeated")
        seen.add(cookie)
    raise ValueError("LDAP pagination page limit exceeded")

def discover(profile=None, test_only=False, object_guid=None, groups=False, member_dn=None, *, limit=200):
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10000:
        raise ValueError("Invalid LDAP result limit")
    host=os.environ.get("ZRADIUS_LDAP_HOST","")
    base=os.environ.get("ZRADIUS_LDAP_BASE_DN","")
    bind=os.environ.get("ZRADIUS_LDAP_BIND_DN","")
    password=os.environ.get("ZRADIUS_LDAP_BIND_PASSWORD","")
    if profile is not None:
        host,base,bind,password=(profile[k] for k in ("host","base_dn","bind_dn","password"))
    if os.environ.get("ZRADIUS_LDAP_ENABLED")!="true" or not all((host,base,bind,password)):
        raise ValueError("LDAP discovery not configured")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}",host):
        raise ValueError("Invalid LDAP hostname")
    # Deployment-controlled exact DNS allowlist prevents arbitrary UI-selected destinations.
    allowed={x.strip().lower() for x in os.environ.get("ZRADIUS_LDAP_ALLOWED_HOSTS","").split(",") if x.strip()}
    if host.lower() not in allowed:
        raise ValueError("LDAP host is not allowlisted")
    tls=Tls(validate=ssl.CERT_REQUIRED,version=ssl.PROTOCOL_TLS_CLIENT,ca_certs_file=os.environ.get("ZRADIUS_LDAP_CA_FILE") or None)
    server=Server(host,port=636,use_ssl=True,tls=tls,get_info=NONE,connect_timeout=5)
    with Connection(server,user=bind,password=password,auto_bind=True,receive_timeout=10,raise_exceptions=True,auto_referrals=False,read_only=True) as conn:
        if test_only:
            from ldap3 import BASE
            if not conn.search(base,"(objectClass=*)",search_scope=BASE,attributes=["objectClass"],size_limit=1,time_limit=5) or not conn.entries:
                raise ValueError("LDAP base not readable")
            return {"status":"ok","tls":True,"base_readable":True}
        guid_filter="" if object_guid is None else "(objectGUID="+ "".join("\\%02x"%v for v in UUID(str(object_guid)).bytes_le)+")"
        if groups:
            # AD security-enabled bit, not distribution groups.
            filt="(&(objectClass=group)(groupType:1.2.840.113556.1.4.803:=2147483648)"+guid_filter+")"
            entries, limited = _paged_entries(conn, base, filt, ["objectGUID","cn","distinguishedName"], limit)
            items=[]
            for entry in entries:
                raw=entry.entry_raw_attributes.get("objectGUID",[])
                if len(raw)!=1 or len(raw[0])!=16:
                    raise ValueError("Missing group GUID")
                items.append({"object_guid":str(UUID(bytes_le=raw[0])),"name":str(entry.cn.value)[:256],"distinguished_name":entry.entry_dn})
            return {"items":items,"limited":limited}
        if member_dn is not None:
            from ldap3.utils.conv import escape_filter_chars
            # Explicit direct membership only; no nested or primary-group expansion.
            guid_filter+="(memberOf="+escape_filter_chars(member_dn)+")"
        entries, limited = _paged_entries(conn, base, "(&(objectCategory=person)(objectClass=user)"+guid_filter+")",
                    ["sAMAccountName","displayName","department","userAccountControl","objectGUID"], limit)
        rows=[]
        for entry in entries:
            attrs=entry.entry_attributes_as_dict
            def first(name):
                values=attrs.get(name,[])
                return str(values[0]) if values else ""
            raw=entry.entry_raw_attributes.get("objectGUID",[])
            guid=str(UUID(bytes_le=raw[0])) if len(raw)==1 and len(raw[0])==16 else None
            username=first("sAMAccountName")
            state=first("userAccountControl")
            rows.append({"object_guid":guid,"username":username,"full_name":first("displayName")[:200],"department":first("department")[:200],
                         "directory_enabled":state.isdecimal() and not bool(int(state)&2),
                         "compatible":bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",username)) and not bool(re.fullmatch(r"hs-[a-f0-9]{20}",username))})
        return {"items":rows,"limited":limited}
