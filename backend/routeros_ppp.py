"""Generate review-only RouterOS commands without exporting stored secrets."""
from ipaddress import IPv4Address
import re

def address(value):
    ip=IPv4Address(value)
    if ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip.is_link_local or int(ip)==0xffffffff:
        raise ValueError("Invalid unicast IPv4")
    return str(ip)

def generate(radius_ip,nas_ip,egress_ip=None,interim=300,disconnect=False):
    radius_ip=address(radius_ip)
    nas_ip=address(nas_ip)
    if not 60<=interim<=86400:
        raise ValueError("Invalid interim interval")
    if disconnect and not egress_ip:
        raise ValueError("Disconnect requires API egress IPv4")
    egress_ip=address(egress_ip) if egress_ip else None
    # Deliberately commented: no placeholder secret or global setting is executable.
    sections=[
        {"name":"preflight","commands":"/radius print detail\n/ppp aaa print\n/ppp profile print\n/ip pool print\n/radius incoming print\n/ip firewall filter print"},
        {"name":"radius","commands":f'# /radius add address={radius_ip} src-address={nas_ip} service=ppp realm=l2tp authentication-port=1812 accounting-port=1813 timeout=3s secret="REPLACE_WITH_NAS_SHARED_SECRET" disabled=yes comment="ZRADIUS-L2TP"'},
        {"name":"activation","commands":f'# Enable only the reviewed new RADIUS entry after checking order and competing entries.\n# /radius enable [find where comment="ZRADIUS-L2TP" and address={radius_ip}]\n# /ppp aaa set use-radius=yes accounting=yes interim-update={interim}s'},
    ]
    if disconnect:
        sections.append({"name":"disconnect","commands":f'# Place the following rule before applicable input drops; review existing rules first.\n# /ip firewall filter add chain=input action=accept protocol=udp src-address={egress_ip}/32 dst-port=3799 comment="ZRADIUS Disconnect"\n# /radius incoming set accept=yes port=3799'})
    sections.append({"name":"rollback","commands":f'# Disable the reviewed ZRADIUS entry if rollback is required.\n# /radius disable [find where comment="ZRADIUS-L2TP" and address={radius_ip}]\n# Restore the previous PPP AAA settings and local secrets from your recorded baseline.'})
    return sections

def local_secret_commands(username):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}",username):
        raise ValueError("Unsupported username")
    selector=f'[find where name="{username}" and service=l2tp]'
    return {"inspect":f"/ppp secret print where name=\"{username}\" and service=l2tp",
            "cutover":f"# /ppp secret disable {selector}",
            "rollback":f"# /ppp secret enable {selector}"}
