#!/usr/bin/env python3
"""Run against an isolated development Compose stack. Never run on production."""
import json
import os
import secrets
import subprocess
import time
import urllib.request

BASE = os.getenv("ZRADIUS_URL", "http://127.0.0.1:8080")
TOKEN = os.environ["ADMIN_TOKEN"]
user = "ci-" + secrets.token_hex(8)
password = secrets.token_hex(16)
session = secrets.token_hex(16)

def api(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)

def radius(kind, attrs, expected):
    packet = "\n".join(f"{k} = {v}" for k,v in attrs.items()) + "\n"
    port = 1812 if kind == "auth" else 1813
    result = subprocess.run(["docker", "compose", "exec", "-T", "radius", "sh", "-ec",
        'key=$(mktemp); trap \'rm -f "$key"\' EXIT; chmod 600 "$key"; printf "%s\\n" "$RADIUS_TEST_SECRET" > "$key"; radclient -x -r 1 -t 3 -S "$key" "$1" "$2"',
        "sh", f"127.0.0.1:{port}", kind], input=packet, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15)
    if expected not in result.stdout:
        raise AssertionError(f"Expected {expected}; radclient exit={result.returncode}")
    print("PASS", expected, flush=True)

def auth(secret, expected):
    radius("auth", {"User-Name":user,"User-Password":secret,
        "Message-Authenticator":"0x00"}, expected)

def accounting(status, **extra):
    attrs={"User-Name":user,"Acct-Session-Id":session,
           "NAS-IP-Address":"127.0.0.1","NAS-Port":"1",
           "Acct-Status-Type":status,"Framed-IP-Address":"192.0.2.10"}
    attrs.update(extra)
    radius("acct",attrs,"Received Accounting-Response")

def db_session():
    # Isolated CI only; query by unique generated session identifier.
    out=subprocess.check_output(["docker","compose","exec","-T","postgres",
        "psql","-U","radius","-d","radius","-Atqc",
        "SELECT row_to_json(a) FROM radacct a WHERE acctsessionid='"+session+"'"],text=True)
    return json.loads(out)

for _ in range(60):
    try:
        api("/health/ready")
        break
    except (OSError, ValueError):
        time.sleep(2)
else:
    raise RuntimeError("API readiness timeout")

api("/api/v1/users","POST",{"username":user,"password":password})
try:
    auth(password,"Received Access-Accept")
    auth("wrong-password","Received Access-Reject")
    api(f"/api/v1/users/{user}/state","PUT",{"enabled":False})
    auth(password,"Received Access-Reject")
    api(f"/api/v1/users/{user}/state","PUT",{"enabled":True})
    auth(password,"Received Access-Accept")
    accounting("Start")
    assert db_session()["acctstoptime"] is None
    accounting("Interim-Update", **{"Acct-Session-Time":"30","Acct-Input-Octets":"1234","Acct-Output-Octets":"5678"})
    row=db_session()
    assert row["acctinputoctets"]==1234 and row["acctoutputoctets"]==5678, "Interim counters not persisted"
    accounting("Stop", **{"Acct-Session-Time":"60","Acct-Input-Octets":"2345","Acct-Output-Octets":"6789","Acct-Terminate-Cause":"User-Request"})
    assert db_session()["acctstoptime"] is not None, "Stop not persisted"
    print("PASS SQL Accounting Start / Interim / Stop")
finally:
    api(f"/api/v1/users/{user}","DELETE")
