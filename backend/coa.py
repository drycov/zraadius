"""RFC 5176 transport via radclient. No shell interpolation or secrets in argv."""
import ipaddress
import os
import re
import subprocess
import tempfile

def destination_allowed(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local:
        return False
    networks = [ipaddress.ip_network(x.strip(), strict=True)
                for x in os.environ.get("COA_ALLOWED_NETWORKS", "").split(",") if x.strip()]
    return any(ip.version == net.version and ip in net for net in networks)

def quote(value: str) -> str:
    if not value or len(value.encode()) > 253 or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError("Invalid RADIUS attribute")
    return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'

def send(address, secret, username, session_id, rate=None):
    if not destination_allowed(address):
        raise ValueError("NAS address outside configured networks")
    if not re.fullmatch(r"[A-Za-z0-9]{32,128}",secret):
        raise ValueError("Invalid NAS secret")
    kind = "coa" if rate is not None else "disconnect"
    attrs = ["User-Name = "+quote(username), "Acct-Session-Id = "+quote(session_id),
             "Message-Authenticator = 0x00"]
    if rate is not None:
        if not re.fullmatch(r"[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M",rate):
            raise ValueError("Invalid rate")
        attrs.append("Mikrotik-Rate-Limit = "+quote(rate))
    ip = ipaddress.ip_address(address)
    endpoint = f"[{ip}]:3799" if ip.version == 6 else f"{ip}:3799"
    with tempfile.NamedTemporaryFile(mode="w", encoding="ascii") as key:
        key.write(secret+"\n")
        key.flush()
        try:
            result = subprocess.run(["radclient","-x","-r","1","-t","3","-S",key.name,endpoint,kind],
                                    input="\n".join(attrs)+"\n",text=True,
                                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=8)
        except (subprocess.TimeoutExpired,OSError):
            return "unknown"
    expected = "CoA" if rate is not None else "Disconnect"
    if re.search(r"(?m)^Received "+expected+r"-ACK\b",result.stdout) and result.returncode==0:
        return "ack"
    if re.search(r"(?m)^Received "+expected+r"-NAK\b",result.stdout):
        return "nak"
    return "unknown"
