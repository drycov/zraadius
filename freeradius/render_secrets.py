"""Render validated RADIUS config from encrypted records, never log plaintext."""
import os
import sys
import json
import ipaddress
import re
import subprocess
from secret_crypto import key,unseal

key()
mode=sys.argv[1]
queries={
"nas":"SELECT coalesce(json_agg(row_to_json(t)),'[]') FROM (SELECT id,nasname,secret FROM nas ORDER BY id)t",
"proxy":"SELECT coalesce(json_agg(row_to_json(t)),'[]') FROM (SELECT id,realm,host(home_ip) AS ip,secret FROM zradius_proxy_realms WHERE enabled ORDER BY id)t"
}
rows=json.loads(subprocess.check_output(["psql","-X","-h","postgres","-U","zradius_runtime","-d","radius","-v","ON_ERROR_STOP=1","-Atqc",queries[mode]],text=True))
for row in rows:
    i=int(row["id"])
    if mode=="nas":
        ip=ipaddress.ip_address(row["nasname"])
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
            raise ValueError("Invalid NAS address")
        secret=unseal(row["secret"],"nas:"+row["nasname"])
        print(f'client managed_{i} {{\n ipaddr = {ip}\n secret = "{secret}"\n require_message_authenticator = yes\n}}')
    else:
        realm=row["realm"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,126}[a-z0-9]",realm):
            raise ValueError("Invalid realm")
        ip=ipaddress.IPv4Address(row["ip"])
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
            raise ValueError("Invalid upstream address")
        secret=unseal(row["secret"],"zradius_proxy_realms:"+realm)
        for kind,port in (("auth",1812),("acct",1813)):
            print(f'home_server proxy_{kind}_{i} {{\n type = {kind}\n ipaddr = {ip}\n port = {port}\n secret = "{secret}"\n status_check = status-server\n}}')
            print(f'home_server_pool proxy_{kind}_pool_{i} {{\n type = fail-over\n home_server = proxy_{kind}_{i}\n}}')
        print(f'realm "{realm}" {{\n auth_pool = proxy_auth_pool_{i}\n acct_pool = proxy_acct_pool_{i}\n nostrip\n}}')
