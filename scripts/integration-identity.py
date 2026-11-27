#!/usr/bin/env python3
"""Destructive fixture setup ONLY for an isolated CI Compose stack."""
import json
import os
import secrets
import subprocess
import urllib.request
import urllib.error

assert os.environ.get("ZRADIUS_ISOLATED_TEST") == "1", "Isolated test stack required"
base=os.getenv("ZRADIUS_URL","http://127.0.0.1:8080")+"/api/v1/"
token=os.environ["ADMIN_TOKEN"]
user="unified-ci-"+secrets.token_hex(6)
password=secrets.token_hex(24)

def api(path,method="GET",body=None,status=200):
    req=urllib.request.Request(base+path,method=method,headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            assert r.status==status,(path,r.status,status)
            return json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code!=status:
            raise AssertionError((path,exc.code,status)) from None

def sql(query):
    return subprocess.check_output(["docker","compose","exec","-T","postgres","psql","-U","radius","-d","radius","-Atq","-v","ON_ERROR_STOP=1","-c",query],text=True).strip()

def auth(service,secret,expected):
    attrs={"User-Name":user,"User-Password":secret,"Mikrotik-Realm":service,"Message-Authenticator":"0x00"}
    if service in ("pppoe","l2tp"):
        attrs.update({"Service-Type":"Framed-User","Framed-Protocol":"PPP"})
    elif service=="device-aaa":
        attrs["Service-Type"]="Login-User"
    command=["docker","compose","exec","-T","radius","sh","-ec",
        "key=$(mktemp); trap 'rm -f \"$key\"' EXIT; chmod 600 \"$key\"; printf '%s\\n' \"$RADIUS_TEST_SECRET\" > \"$key\"; radclient -r 1 -t 3 -S \"$key\" 127.0.0.1:1812 auth"]
    result=subprocess.run(command,input="\n".join(f"{k} = {v}" for k,v in attrs.items())+"\n",text=True,capture_output=True,timeout=15)
    assert "Received Access-"+expected in result.stdout+result.stderr,(service,expected,result.returncode)
    print("PASS",service,expected,flush=True)
    return result.stdout+result.stderr

# localhost is the existing CI static client; do not enable dynamic NAS loading here.
nas=int(sql("INSERT INTO nas(nasname,shortname,type,secret) VALUES ('127.0.0.1','unified-ci','mikrotik','unused-ci-fixture') RETURNING id"))
for service in ("device-aaa","l2tp","pppoe","hotspot"):
    sql(f"INSERT INTO zradius_nas_services(nas_id,service_code) VALUES ({nas},'{service}')")
profile=api("ppp/profiles","POST",{"name":user,"pool":"ci-pool"},201)["id"]
identity=api("identities","POST",{"username":user,"password":password,
    "device":{"nas_id":nas,"role":"read"},
    "l2tp":{"nas_id":nas,"profile_id":profile},
    "pppoe":{"nas_id":nas,"rate_limit":"100M/100M","pool":"ci-pool"},
    "hotspot":{"nas_id":nas,"rate_limit":"20M/20M"}},201)["id"]
for service in ("device-aaa","l2tp","pppoe","hotspot"):
    auth(service,password,"Accept")
    auth(service,"wrong-password","Reject")
api("users","POST",{"username":user,"password":password},409)
api("identities/"+str(identity)+"/state","PUT",{"enabled":False})
for service in ("device-aaa","l2tp","pppoe","hotspot"):
    auth(service,password,"Reject")
api("identities/"+str(identity)+"/state","PUT",{"enabled":True})
new=secrets.token_hex(24)
api("identities/"+str(identity)+"/password","PUT",{"password":new})
for service in ("device-aaa","l2tp","pppoe","hotspot"):
    auth(service,password,"Reject")
    auth(service,new,"Accept")
api("identities/"+str(identity)+"/hotspot","PUT",{"enabled":False})
auth("hotspot",new,"Reject")
auth("pppoe",new,"Accept")
assert api("identities/"+str(identity)+"/sessions")["network"]==[]
print("PASS unified identity lifecycle")

# Exercise the actual SQL projection and RADIUS reply path, independent of
# personal-admin login setup. Only synthetic identities in isolated CI.
policy=int(sql(f"INSERT INTO zradius_policies(name,enabled) VALUES ('{user}-timeouts',true) RETURNING id"))
sql(f"INSERT INTO zradius_policy_assignments(policy_id,identity_id) VALUES ({policy},{identity})")
sql(f"""INSERT INTO zradius_policy_attributes(policy_id,service,name,attribute_list,operator,value,priority,runtime_apply)
 VALUES ({policy},'pppoe','Idle-Timeout','reply',':=','123',100,true),
 ({policy},'pppoe','Session-Timeout','reply',':=','456',100,true)""")
import re
reply=auth("pppoe",new,"Accept")
assert re.search(r"Idle-Timeout\s*=\s*123\b",reply), "Missing runtime idle timeout"
assert re.search(r"Session-Timeout\s*=\s*456\b",reply), "Missing runtime session timeout"
other=int(sql(f"INSERT INTO zradius_policies(name,enabled) VALUES ('{user}-conflict',true) RETURNING id"))
sql(f"INSERT INTO zradius_policy_assignments(policy_id,identity_id) VALUES ({other},{identity})")
sql(f"""INSERT INTO zradius_policy_attributes(policy_id,service,name,attribute_list,operator,value,priority,runtime_apply)
 VALUES ({other},'pppoe','Idle-Timeout','reply',':=','124',100,true)""")
auth("pppoe",new,"Reject")
sql(f"UPDATE zradius_policy_attributes SET runtime_apply=false WHERE policy_id={other}")
auth("pppoe",new,"Accept")
sql(f"UPDATE zradius_policies SET enabled=false WHERE id={policy}")
reply=auth("pppoe",new,"Accept")
assert not re.search(r"Idle-Timeout\s*=\s*123\b",reply), "Disabled policy still applied"
print("PASS PPPoE runtime attributes and conflict rejection",flush=True)
