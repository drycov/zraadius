"""Read-only AD discovery. No password synchronization or RADIUS bind."""
import os
import re
import ssl
from ldap3 import Server, Connection, Tls, SUBTREE, NONE

def discover():
    host=os.environ.get("ZRADIUS_LDAP_HOST","")
    base=os.environ.get("ZRADIUS_LDAP_BASE_DN","")
    bind=os.environ.get("ZRADIUS_LDAP_BIND_DN","")
    password=os.environ.get("ZRADIUS_LDAP_BIND_PASSWORD","")
    if os.environ.get("ZRADIUS_LDAP_ENABLED")!="true" or not all((host,base,bind,password)):
        raise ValueError("LDAP discovery not configured")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}",host):
        raise ValueError("Invalid LDAP hostname")
    tls=Tls(validate=ssl.CERT_REQUIRED,version=ssl.PROTOCOL_TLS_CLIENT,ca_certs_file=os.environ.get("ZRADIUS_LDAP_CA_FILE") or None)
    server=Server(host,port=636,use_ssl=True,tls=tls,get_info=NONE,connect_timeout=5)
    with Connection(server,user=bind,password=password,auto_bind=True,receive_timeout=10,raise_exceptions=True,auto_referrals=False,read_only=True) as conn:
        conn.search(base,"(&(objectCategory=person)(objectClass=user))",search_scope=SUBTREE,
                    attributes=["sAMAccountName","displayName","department","userAccountControl"],size_limit=201,time_limit=10)
        rows=[]
        for entry in conn.entries[:200]:
            attrs=entry.entry_attributes_as_dict
            def first(name):
                values=attrs.get(name,[])
                return str(values[0]) if values else ""
            username=first("sAMAccountName")
            state=first("userAccountControl")
            rows.append({"username":username,"full_name":first("displayName")[:200],"department":first("department")[:200],
                         "directory_enabled":state.isdecimal() and not bool(int(state)&2),
                         "compatible":bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",username)) and not bool(re.fullmatch(r"hs-[a-f0-9]{20}",username))})
        return {"items":rows,"limited":len(conn.entries)>200}
