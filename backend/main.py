import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, SecretStr, IPvAnyAddress
from typing import Literal
from psycopg.errors import UniqueViolation
from coa import send, destination_allowed

ROOT = Path(__file__).parent
bearer = HTTPBearer(auto_error=False)

def db():
    return psycopg.connect(row_factory=dict_row, connect_timeout=5)

@asynccontextmanager
async def lifespan(app):
    token = os.environ.get("ADMIN_TOKEN", "")
    if len(token) < 32 or token.startswith("replace_with"):
        raise RuntimeError("Set a random ADMIN_TOKEN of at least 32 characters")
    with db() as conn:
        conn.execute((ROOT / "schema.sql").read_text())
    yield

app = FastAPI(title="ZRADIUS", version="0.1.0-alpha", lifespan=lifespan)

def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or not secrets.compare_digest(
        credentials.credentials.encode(), os.environ["ADMIN_TOKEN"].encode()
    ):
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate":"Bearer"})

class User(BaseModel):
    username: str = Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: SecretStr = Field(min_length=12,max_length=253)

class Group(BaseModel):
    name: str = Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")

def audit(conn, action, subject):
    conn.execute("INSERT INTO zradius_audit(action,subject) VALUES (%s,%s)", (action,subject))

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "index.html")

@app.get("/health/live")
def live():
    return {"status":"ok"}

@app.get("/health/ready")
def ready():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(503,"Database unavailable")
    return {"status":"ready"}

@app.get("/api/v1/users", dependencies=[Depends(auth)])
def users(limit: int = 100, offset: int = 0):
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("SELECT DISTINCT r.username, NOT EXISTS (SELECT 1 FROM zradius_disabled_users d WHERE d.username=r.username) AS enabled FROM radcheck r ORDER BY r.username LIMIT %s OFFSET %s",(limit,offset)).fetchall()

@app.post("/api/v1/users", status_code=201, dependencies=[Depends(auth)])
def create_user(user: User):
    with db() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(user.username,))
        if conn.execute("SELECT 1 FROM radcheck WHERE username=%s",(user.username,)).fetchone():
            raise HTTPException(409,"User exists")
        password = user.password.get_secret_value()
        if len(password.encode()) > 253:
            raise HTTPException(422,"Password exceeds 253 bytes")
        conn.execute("INSERT INTO radcheck(username,attribute,op,value) VALUES (%s,'Cleartext-Password',':=',%s)",(user.username,password))
        audit(conn,"user.create",user.username)
    return {"username":user.username}

@app.get("/api/v1/groups", dependencies=[Depends(auth)])
def groups():
    with db() as conn:
        return conn.execute("SELECT name FROM zradius_groups ORDER BY name").fetchall()

@app.post("/api/v1/groups", status_code=201, dependencies=[Depends(auth)])
def create_group(group: Group):
    with db() as conn:
        result = conn.execute("INSERT INTO zradius_groups(name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING name",(group.name,)).fetchone()
        if not result:
            raise HTTPException(409,"Group exists")
        audit(conn,"group.create",group.name)
    return result

@app.put("/api/v1/users/{username}/groups/{group}", dependencies=[Depends(auth)])
def assign_group(username: str, group: str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM radcheck WHERE username=%s",(username,)).fetchone() or not conn.execute("SELECT 1 FROM zradius_groups WHERE name=%s",(group,)).fetchone():
            raise HTTPException(404,"User or group not found")
        conn.execute("INSERT INTO radusergroup(username,groupname) VALUES (%s,%s) ON CONFLICT DO NOTHING",(username,group))
        audit(conn,"group.assign",username + ":" + group)
    return {"status":"assigned"}

@app.get("/api/v1/audit", dependencies=[Depends(auth)])
def audits():
    with db() as conn:
        return conn.execute("SELECT * FROM zradius_audit ORDER BY id DESC LIMIT 100").fetchall()

@app.get("/api/v1/accounting", dependencies=[Depends(auth)])
def accounting(limit: int = 100, offset: int = 0, active: bool = False):
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(422, "Invalid pagination")
    with db() as conn:
        return conn.execute(
            """SELECT radacctid, username, acctsessionid, nasipaddress::text,
               framedipaddress::text, acctstarttime, acctstoptime,
               acctsessiontime, acctinputoctets, acctoutputoctets
               FROM radacct WHERE (NOT %s OR acctstoptime IS NULL)
               ORDER BY radacctid DESC LIMIT %s OFFSET %s""",
            (active,limit,offset)
        ).fetchall()

# Management operations. Never return credential attributes or NAS secrets.
class PasswordUpdate(BaseModel):
    password: SecretStr = Field(min_length=12,max_length=253)

class UserState(BaseModel):
    enabled: bool

class Profile(BaseModel):
    download_mbps: int = Field(ge=1,le=100000)
    upload_mbps: int = Field(ge=1,le=100000)
    interim_seconds: int = Field(default=300,ge=60,le=86400)
    idle_seconds: int = Field(default=3600,ge=0,le=86400)
    pool: str | None = Field(default=None,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")

class NAS(BaseModel):
    address: IPvAnyAddress
    name: str = Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")
    vendor: Literal["mikrotik","cisco","other"] = "other"
    secret: SecretStr = Field(min_length=32,max_length=128)
    description: str = Field(default="",max_length=200)

def lock_user(conn, username):
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(username,))
    if not conn.execute("SELECT 1 FROM radcheck WHERE username=%s",(username,)).fetchone():
        raise HTTPException(404,"User not found")

@app.get("/api/v1/users/{username}", dependencies=[Depends(auth)])
def user_detail(username: str):
    with db() as conn:
        lock_user(conn,username)
        disabled = conn.execute("SELECT 1 FROM zradius_disabled_users WHERE username=%s",(username,)).fetchone()
        groups = conn.execute("SELECT groupname,priority FROM radusergroup WHERE username=%s ORDER BY priority,groupname",(username,)).fetchall()
        return {"username":username,"enabled":not bool(disabled),"groups":groups}

@app.put("/api/v1/users/{username}/password", dependencies=[Depends(auth)])
def update_password(username: str, body: PasswordUpdate):
    password=body.password.get_secret_value()
    if len(password.encode())>253:
        raise HTTPException(422,"Password exceeds 253 bytes")
    with db() as conn:
        lock_user(conn,username)
        conn.execute("DELETE FROM radcheck WHERE username=%s AND attribute='Cleartext-Password'",(username,))
        conn.execute("INSERT INTO radcheck(username,attribute,op,value) VALUES (%s,'Cleartext-Password',':=',%s)",(username,password))
        audit(conn,"user.password",username)
    return {"status":"updated"}

@app.put("/api/v1/users/{username}/state", dependencies=[Depends(auth)])
def user_state(username: str, body: UserState):
    with db() as conn:
        lock_user(conn,username)
        if body.enabled:
            conn.execute("DELETE FROM zradius_disabled_users WHERE username=%s",(username,))
            conn.execute("DELETE FROM radcheck WHERE username=%s AND attribute='Auth-Type' AND op=':=' AND value='Reject'",(username,))
        else:
            conn.execute("INSERT INTO zradius_disabled_users VALUES (%s) ON CONFLICT DO NOTHING",(username,))
            conn.execute("DELETE FROM radcheck WHERE username=%s AND attribute='Auth-Type'",(username,))
            conn.execute("INSERT INTO radcheck(username,attribute,op,value) VALUES (%s,'Auth-Type',':=','Reject')",(username,))
        audit(conn,"user.enable" if body.enabled else "user.disable",username)
    return {"username":username,"enabled":body.enabled,"existing_sessions_terminated":False}

@app.delete("/api/v1/users/{username}", dependencies=[Depends(auth)])
def delete_user(username: str):
    with db() as conn:
        lock_user(conn,username)
        for table in ("radcheck","radreply","radusergroup","zradius_disabled_users"):
            conn.execute("DELETE FROM "+table+" WHERE username=%s",(username,))
        audit(conn,"user.delete",username)
    return {"status":"deleted","accounting_preserved":True}

@app.delete("/api/v1/users/{username}/groups/{group}", dependencies=[Depends(auth)])
def remove_group(username: str, group: str):
    with db() as conn:
        lock_user(conn,username)
        conn.execute("DELETE FROM radusergroup WHERE username=%s AND groupname=%s",(username,group))
        audit(conn,"group.unassign",username+":"+group)
    return {"status":"removed"}

@app.put("/api/v1/groups/{group}/mikrotik-profile", dependencies=[Depends(auth)])
def set_profile(group: str, body: Profile):
    # MikroTik rate-limit is RX/TX from the router perspective.
    attrs={"Mikrotik-Rate-Limit":f"{body.upload_mbps}M/{body.download_mbps}M",
           "Acct-Interim-Interval":str(body.interim_seconds),
           "Idle-Timeout":str(body.idle_seconds)}
    if body.pool:
        attrs["Framed-Pool"]=body.pool
    with db() as conn:
        if not conn.execute("SELECT name FROM zradius_groups WHERE name=%s FOR UPDATE",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        conn.execute("DELETE FROM radgroupreply WHERE groupname=%s AND attribute=ANY(%s)",(group,["Mikrotik-Rate-Limit","Acct-Interim-Interval","Idle-Timeout","Framed-Pool"]))
        for name,value in attrs.items():
            conn.execute("INSERT INTO radgroupreply(groupname,attribute,op,value) VALUES (%s,%s,':=',%s)",(group,name,value))
        audit(conn,"group.profile",group)
    return attrs

@app.get("/api/v1/groups/{group}/profile", dependencies=[Depends(auth)])
def get_profile(group: str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_groups WHERE name=%s",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        return conn.execute("SELECT attribute,op,value FROM radgroupreply WHERE groupname=%s AND attribute IN ('Mikrotik-Rate-Limit','Acct-Interim-Interval','Idle-Timeout','Framed-Pool') ORDER BY attribute",(group,)).fetchall()

@app.get("/api/v1/nas", dependencies=[Depends(auth)])
def list_nas():
    with db() as conn:
        return conn.execute("SELECT id,nasname,shortname,type,description FROM nas ORDER BY id").fetchall()

@app.post("/api/v1/nas", status_code=201, dependencies=[Depends(auth)])
def create_nas(body: NAS):
    address=str(body.address)
    if body.address.is_loopback or body.address.is_unspecified or body.address.is_multicast or body.address.is_link_local:
        raise HTTPException(422,"Invalid NAS address")
    secret=body.secret.get_secret_value()
    if not secret.isascii() or not secret.isalnum():
        raise HTTPException(422,"Use an alphanumeric random shared secret")
    with db() as conn:
        row=conn.execute("INSERT INTO nas(nasname,shortname,type,secret,description) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,nasname,shortname,type,description",(address,body.name,body.vendor,secret,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"NAS address or name already exists")
        audit(conn,"nas.create",address)
    return {**row,"runtime_applied":False}

@app.delete("/api/v1/nas/{nas_id}", dependencies=[Depends(auth)])
def delete_nas(nas_id: int):
    with db() as conn:
        conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,))
        if conn.execute("SELECT 1 FROM zradius_ipoe_bindings WHERE nas_id=%s",(nas_id,)).fetchone():
            raise HTTPException(409,"Remove IPoE bindings first")
        if conn.execute("SELECT 1 FROM zradius_hotspot_vouchers WHERE nas_id=%s",(nas_id,)).fetchone():
            raise HTTPException(409,"NAS has Hotspot voucher history")
        row=conn.execute("DELETE FROM nas WHERE id=%s RETURNING nasname",(nas_id,)).fetchone()
        if not row:
            raise HTTPException(404,"NAS not found")
        audit(conn,"nas.delete",row["nasname"])
    return {"status":"deleted","runtime_applied":False}

@app.get("/api/v1/dictionaries", dependencies=[Depends(auth)])
def dictionaries():
    return [
        {"name":"Mikrotik-Rate-Limit","vendor":14988,"type":"string","list":"reply"},
        {"name":"Framed-Pool","vendor":0,"type":"string","list":"reply"},
        {"name":"Acct-Interim-Interval","vendor":0,"type":"integer","list":"reply"},
        {"name":"Idle-Timeout","vendor":0,"type":"integer","list":"reply"},
        {"name":"Simultaneous-Use","vendor":0,"type":"integer","list":"control"}
    ]

@app.get("/api/v1/dashboard", dependencies=[Depends(auth)])
def dashboard():
    with db() as conn:
        return conn.execute("""SELECT
            (SELECT count(DISTINCT username) FROM radcheck) AS users,
            (SELECT count(*) FROM zradius_disabled_users) AS disabled_users,
            (SELECT count(*) FROM zradius_groups) AS groups,
            (SELECT count(*) FROM nas) AS nas,
            (SELECT count(*) FROM radacct WHERE acctstoptime IS NULL) AS open_sessions,
            (SELECT count(*) FROM radacct) AS accounting_records,
            (SELECT count(*) FROM zradius_audit WHERE created_at >= now()-interval '24 hours') AS audit_24h
        """).fetchone()

class RateChange(BaseModel):
    upload_mbps: int = Field(ge=1,le=100000)
    download_mbps: int = Field(ge=1,le=100000)

def session_action(session_id: int, rate: str | None = None):
    if os.environ.get("COA_ENABLED","false").lower() != "true":
        raise HTTPException(409,"CoA is disabled")
    action = "coa" if rate else "disconnect"
    try:
        with db() as conn:
            row = conn.execute("""SELECT a.username,a.acctsessionid,host(a.nasipaddress) AS address,n.secret,n.type
              FROM radacct a JOIN nas n ON n.nasname=host(a.nasipaddress)
              WHERE a.radacctid=%s AND a.acctstoptime IS NULL""",(session_id,)).fetchone()
            if not row:
                raise HTTPException(404,"Open session with registered NAS not found")
            if rate and row["type"]!="mikrotik":
                raise HTTPException(422,"Rate change supported only for MikroTik")
            try:
                allowed=destination_allowed(row["address"])
            except ValueError:
                allowed=False
            if not allowed:
                raise HTTPException(403,"NAS outside allowed networks")
            request_id=conn.execute("INSERT INTO zradius_coa_requests(radacctid,action,status) VALUES (%s,%s,'pending') RETURNING id",(session_id,action)).fetchone()["id"]
            audit(conn,"session."+action+".requested",str(session_id))
    except UniqueViolation:
        raise HTTPException(409,"Session already has a pending request")
    try:
        status=send(row["address"],row["secret"],row["username"],row["acctsessionid"],rate)
    except (ValueError,TypeError):
        status="unknown"
    with db() as conn:
        conn.execute("UPDATE zradius_coa_requests SET status=%s,completed_at=now() WHERE id=%s",(status,request_id))
        audit(conn,"session."+action+"."+status,str(session_id))
    # Only real Accounting-Stop closes the session record.
    return {"id":request_id,"status":status,"action":action,"accounting_updated":False}

@app.post("/api/v1/sessions/{session_id}/disconnect", dependencies=[Depends(auth)])
def disconnect(session_id: int):
    return session_action(session_id)

@app.post("/api/v1/sessions/{session_id}/rate", dependencies=[Depends(auth)])
def change_rate(session_id: int, body: RateChange):
    return session_action(session_id,f"{body.upload_mbps}M/{body.download_mbps}M")

@app.get("/api/v1/coa", dependencies=[Depends(auth)])
def coa_history():
    with db() as conn:
        return conn.execute("SELECT * FROM zradius_coa_requests ORDER BY id DESC LIMIT 100").fetchall()

@app.get("/api/v1/services", dependencies=[Depends(auth)])
def service_catalog():
    with db() as conn:
        return conn.execute("SELECT code,name,methods,maturity FROM zradius_services ORDER BY code").fetchall()

class ServiceBindings(BaseModel):
    services: list[str] = Field(max_length=8)

def validate_services(conn, codes):
    codes=sorted(set(codes))
    found=conn.execute("SELECT code FROM zradius_services WHERE code=ANY(%s)",(codes,)).fetchall()
    if len(found)!=len(codes):
        raise HTTPException(422,"Unknown service")
    return codes

@app.get("/api/v1/nas/{nas_id}/services", dependencies=[Depends(auth)])
def nas_services(nas_id: int):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM nas WHERE id=%s",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        return {"services":[x["service_code"] for x in conn.execute("SELECT service_code FROM zradius_nas_services WHERE nas_id=%s ORDER BY service_code",(nas_id,)).fetchall()],"runtime_enforced":False}

@app.put("/api/v1/nas/{nas_id}/services", dependencies=[Depends(auth)])
def set_nas_services(nas_id: int, body: ServiceBindings):
    with db() as conn:
        if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        codes=validate_services(conn,body.services)
        conn.execute("DELETE FROM zradius_nas_services WHERE nas_id=%s",(nas_id,))
        for code in codes:
            conn.execute("INSERT INTO zradius_nas_services VALUES (%s,%s)",(nas_id,code))
        audit(conn,"nas.services",str(nas_id))
    return {"services":codes,"runtime_enforced":False}

@app.get("/api/v1/groups/{group}/services", dependencies=[Depends(auth)])
def group_services(group: str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_groups WHERE name=%s",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        return {"services":[x["service_code"] for x in conn.execute("SELECT service_code FROM zradius_group_services WHERE groupname=%s ORDER BY service_code",(group,)).fetchall()],"runtime_enforced":False}

@app.put("/api/v1/groups/{group}/services", dependencies=[Depends(auth)])
def set_group_services(group: str, body: ServiceBindings):
    with db() as conn:
        if not conn.execute("SELECT name FROM zradius_groups WHERE name=%s FOR UPDATE",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        codes=validate_services(conn,body.services)
        conn.execute("DELETE FROM zradius_group_services WHERE groupname=%s",(group,))
        for code in codes:
            conn.execute("INSERT INTO zradius_group_services VALUES (%s,%s)",(group,code))
        audit(conn,"group.services",group)
    return {"services":codes,"runtime_enforced":False}

class NetworkPolicy(BaseModel):
    vlan_id: int | None = Field(default=None,ge=1,le=4094)
    session_timeout: int | None = Field(default=None,ge=1,le=604800)
    simultaneous_use: int | None = Field(default=None,ge=1,le=100)

class DeviceRole(BaseModel):
    mikrotik_group: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$",max_length=64,min_length=1)

@app.put("/api/v1/groups/{group}/network-policy", dependencies=[Depends(auth)])
def network_policy(group: str, body: NetworkPolicy):
    reply = {}
    if body.vlan_id is not None:
        reply.update({"Tunnel-Type":"VLAN","Tunnel-Medium-Type":"IEEE-802","Tunnel-Private-Group-Id":str(body.vlan_id)})
    if body.session_timeout is not None:
        reply["Session-Timeout"]=str(body.session_timeout)
    with db() as conn:
        if not conn.execute("SELECT name FROM zradius_groups WHERE name=%s FOR UPDATE",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        conn.execute("DELETE FROM radgroupreply WHERE groupname=%s AND attribute=ANY(%s)",(group,["Tunnel-Type","Tunnel-Medium-Type","Tunnel-Private-Group-Id","Session-Timeout"]))
        for name,value in reply.items():
            conn.execute("INSERT INTO radgroupreply(groupname,attribute,op,value) VALUES (%s,%s,':=',%s)",(group,name,value))
        conn.execute("DELETE FROM radgroupcheck WHERE groupname=%s AND attribute='Simultaneous-Use'",(group,))
        if body.simultaneous_use is not None:
            conn.execute("INSERT INTO radgroupcheck(groupname,attribute,op,value) VALUES (%s,'Simultaneous-Use',':=',%s)",(group,str(body.simultaneous_use)))
        audit(conn,"group.network_policy",group)
    return {"reply":reply,"simultaneous_use":body.simultaneous_use}

@app.get("/api/v1/groups/{group}/network-policy", dependencies=[Depends(auth)])
def get_network_policy(group: str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_groups WHERE name=%s",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        rows=conn.execute("SELECT attribute,value FROM radgroupreply WHERE groupname=%s AND attribute IN ('Tunnel-Type','Tunnel-Medium-Type','Tunnel-Private-Group-Id','Session-Timeout') ORDER BY id",(group,)).fetchall()
        checks=conn.execute("SELECT attribute,value FROM radgroupcheck WHERE groupname=%s AND attribute='Simultaneous-Use' ORDER BY id",(group,)).fetchall()
        return {"reply":{r["attribute"]:r["value"] for r in rows},"control":{r["attribute"]:r["value"] for r in checks}}

@app.put("/api/v1/groups/{group}/device-role", dependencies=[Depends(auth)])
def set_device_role(group: str, body: DeviceRole):
    with db() as conn:
        if not conn.execute("SELECT name FROM zradius_groups WHERE name=%s FOR UPDATE",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        if not conn.execute("SELECT 1 FROM zradius_group_services WHERE groupname=%s AND service_code='device-aaa'",(group,)).fetchone():
            raise HTTPException(409,"Assign Device AAA service first")
        conn.execute("INSERT INTO zradius_device_roles VALUES (%s,%s) ON CONFLICT(groupname) DO UPDATE SET mikrotik_group=excluded.mikrotik_group",(group,body.mikrotik_group))
        audit(conn,"group.device_role",group)
    return {"group":group,"mikrotik_group":body.mikrotik_group,"runtime_enforced":False}

@app.get("/api/v1/groups/{group}/device-role", dependencies=[Depends(auth)])
def get_device_role(group: str):
    with db() as conn:
        row=conn.execute("SELECT groupname,mikrotik_group FROM zradius_device_roles WHERE groupname=%s",(group,)).fetchone()
        return {"role":row,"runtime_enforced":False}

@app.delete("/api/v1/groups/{group}/device-role", dependencies=[Depends(auth)])
def delete_device_role(group: str):
    with db() as conn:
        conn.execute("DELETE FROM zradius_device_roles WHERE groupname=%s",(group,))
        audit(conn,"group.device_role.delete",group)
    return {"status":"deleted"}

# IPoE inventory and policy preview; never accepts unauthenticated NAS requests.
from ipoe import normalize_mac, normalize_ip

class IpoeBinding(BaseModel):
    nas_id: int = Field(gt=0)
    mac: str = Field(max_length=32)
    static_ip: str | None = Field(default=None,max_length=15)
    circuit_id: str | None = Field(default=None,min_length=1,max_length=253)
    remote_id: str | None = Field(default=None,min_length=1,max_length=253)
    enabled: bool = True
    description: str = Field(default="",max_length=200)

def binding_values(body):
    try:
        mac=normalize_mac(body.mac)
        ip=normalize_ip(body.static_ip)
        for value in (body.circuit_id,body.remote_id):
            if value is not None and (len(value.encode())>253 or any(ord(c)<32 or ord(c)==127 for c in value)):
                raise ValueError("Invalid circuit or remote identifier")
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    return (body.nas_id,mac,ip,body.circuit_id,body.remote_id,body.enabled,body.description)

def require_ipoe_nas(conn,nas_id):
    if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
        raise HTTPException(404,"NAS not found")
    if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='ipoe'",(nas_id,)).fetchone():
        raise HTTPException(409,"Assign IPoE service to NAS first")

IPOE_FIELDS="id,nas_id,mac::text AS mac,host(static_ip) AS static_ip,circuit_id,remote_id,enabled,description,created_at"

@app.get("/api/v1/ipoe/bindings", dependencies=[Depends(auth)])
def ipoe_bindings(limit: int=100, offset: int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("SELECT "+IPOE_FIELDS+" FROM zradius_ipoe_bindings ORDER BY id DESC LIMIT %s OFFSET %s",(limit,offset)).fetchall()

@app.post("/api/v1/ipoe/bindings",status_code=201,dependencies=[Depends(auth)])
def create_ipoe_binding(body:IpoeBinding):
    values=binding_values(body)
    try:
        with db() as conn:
            conn.execute("LOCK TABLE zradius_ipoe_bindings IN ROW EXCLUSIVE MODE")
            require_ipoe_nas(conn,body.nas_id)
            if values[2] is not None and conn.execute("SELECT 1 FROM zradius_radius_pool_addresses WHERE address=%s",(values[2],)).fetchone():
                raise HTTPException(409,"IP belongs to staged RADIUS pool")
            row=conn.execute("INSERT INTO zradius_ipoe_bindings(nas_id,mac,static_ip,circuit_id,remote_id,enabled,description) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING "+IPOE_FIELDS,values).fetchone()
            audit(conn,"ipoe.create",str(row["id"]))
    except UniqueViolation:
        raise HTTPException(409,"Duplicate MAC or IP on NAS")
    return row

@app.put("/api/v1/ipoe/bindings/{binding_id}",dependencies=[Depends(auth)])
def update_ipoe_binding(binding_id:int,body:IpoeBinding):
    values=binding_values(body)
    try:
        with db() as conn:
            conn.execute("LOCK TABLE zradius_ipoe_bindings IN ROW EXCLUSIVE MODE")
            require_ipoe_nas(conn,body.nas_id)
            if values[2] is not None and conn.execute("SELECT 1 FROM zradius_radius_pool_addresses WHERE address=%s",(values[2],)).fetchone():
                raise HTTPException(409,"IP belongs to staged RADIUS pool")
            row=conn.execute("UPDATE zradius_ipoe_bindings SET nas_id=%s,mac=%s,static_ip=%s,circuit_id=%s,remote_id=%s,enabled=%s,description=%s WHERE id=%s RETURNING "+IPOE_FIELDS,(*values,binding_id)).fetchone()
            if not row:
                raise HTTPException(404,"Binding not found")
            audit(conn,"ipoe.update",str(binding_id))
    except UniqueViolation:
        raise HTTPException(409,"Duplicate MAC or IP on NAS")
    return row

@app.delete("/api/v1/ipoe/bindings/{binding_id}",dependencies=[Depends(auth)])
def delete_ipoe_binding(binding_id:int):
    with db() as conn:
        if not conn.execute("DELETE FROM zradius_ipoe_bindings WHERE id=%s RETURNING id",(binding_id,)).fetchone():
            raise HTTPException(404,"Binding not found")
        audit(conn,"ipoe.delete",str(binding_id))
    return {"status":"deleted"}

class IpoePreview(BaseModel):
    nas_id:int=Field(gt=0)
    mac:str=Field(max_length=32)
    circuit_id:str|None=Field(default=None,max_length=253)
    remote_id:str|None=Field(default=None,max_length=253)

@app.post("/api/v1/ipoe/preview",dependencies=[Depends(auth)])
def preview_ipoe(body:IpoePreview):
    try:
        mac=normalize_mac(body.mac)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    with db() as conn:
        row=conn.execute("""SELECT b.enabled,host(b.static_ip) AS static_ip,b.circuit_id,b.remote_id
        FROM zradius_ipoe_bindings b JOIN zradius_nas_services s
        ON s.nas_id=b.nas_id AND s.service_code='ipoe'
        WHERE b.nas_id=%s AND b.mac=%s""",(body.nas_id,mac)).fetchone()
    allowed=bool(row and row["enabled"] and
        (row["circuit_id"] is None or row["circuit_id"]==body.circuit_id) and
        (row["remote_id"] is None or row["remote_id"]==body.remote_id))
    return {"decision":"allow" if allowed else "deny","reply":{"Framed-IP-Address":row["static_ip"]} if allowed and row["static_ip"] else {},"runtime_enforced":False}

# IPAM inventory: separate from NAS-managed DHCP and FreeRADIUS sqlippool.
from ipam import pool_bounds, next_address
from psycopg.errors import ExclusionViolation, ForeignKeyViolation

class IpPool(BaseModel):
    name: str=Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")
    network: str=Field(max_length=64)
    first_ip: str|None=Field(default=None,max_length=45)
    last_ip: str|None=Field(default=None,max_length=45)
    description: str=Field(default="",max_length=200)

class IpAllocation(BaseModel):
    owner: str=Field(min_length=1,max_length=128)
    address: IPvAnyAddress|None=None
    kind: Literal["reserved","allocated"]="reserved"

@app.get("/api/v1/ipam/pools",dependencies=[Depends(auth)])
def ip_pools():
    with db() as conn:
        return conn.execute("""SELECT p.id,p.name,p.network::text AS network,
        host(p.first_ip) AS first_ip,host(p.last_ip) AS last_ip,p.capacity::text AS capacity,
        count(a.id) AS used,(p.capacity-count(a.id))::text AS free,p.description
        FROM zradius_ip_pools p LEFT JOIN zradius_ip_allocations a ON a.pool_id=p.id
        GROUP BY p.id ORDER BY p.name""").fetchall()

@app.post("/api/v1/ipam/pools",status_code=201,dependencies=[Depends(auth)])
def create_ip_pool(body:IpPool):
    try:
        net,first,last,capacity=pool_bounds(body.network,body.first_ip,body.last_ip)
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    try:
        with db() as conn:
            row=conn.execute("""INSERT INTO zradius_ip_pools(name,network,first_ip,last_ip,capacity,description)
            VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,name""",
            (body.name,net,first,last,capacity,body.description)).fetchone()
            audit(conn,"ipam.pool.create",body.name)
    except (UniqueViolation,ExclusionViolation):
        raise HTTPException(409,"Pool name or network overlaps existing pool")
    return row

@app.delete("/api/v1/ipam/pools/{pool_id}",dependencies=[Depends(auth)])
def delete_ip_pool(pool_id:int):
    try:
        with db() as conn:
            if not conn.execute("DELETE FROM zradius_ip_pools WHERE id=%s RETURNING id",(pool_id,)).fetchone():
                raise HTTPException(404,"Pool not found")
            audit(conn,"ipam.pool.delete",str(pool_id))
    except ForeignKeyViolation:
        raise HTTPException(409,"Release allocations first")
    return {"status":"deleted"}

@app.get("/api/v1/ipam/pools/{pool_id}/allocations",dependencies=[Depends(auth)])
def ip_allocations(pool_id:int,limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT id,host(address) AS address,owner,kind,created_at
        FROM zradius_ip_allocations WHERE pool_id=%s ORDER BY address LIMIT %s OFFSET %s""",
        (pool_id,limit,offset)).fetchall()

@app.post("/api/v1/ipam/pools/{pool_id}/allocations",status_code=201,dependencies=[Depends(auth)])
def allocate_ip(pool_id:int,body:IpAllocation):
    try:
        with db() as conn:
            pool=conn.execute("SELECT host(first_ip) AS first,host(last_ip) AS last FROM zradius_ip_pools WHERE id=%s FOR UPDATE",(pool_id,)).fetchone()
            if not pool:
                raise HTTPException(404,"Pool not found")
            if conn.execute("SELECT 1 FROM zradius_radius_pool_exports WHERE pool_id=%s",(pool_id,)).fetchone():
                raise HTTPException(409,"Withdraw staged RADIUS pool before modifying inventory")
            if body.address is not None:
                import ipaddress
                ip=body.address
                lo,hi=ipaddress.ip_address(pool["first"]),ipaddress.ip_address(pool["last"])
                if ip.version!=lo.version or not lo<=ip<=hi:
                    raise HTTPException(422,"Address outside pool range")
                address=str(ip)
            else:
                with conn.cursor(name="ipam_scan") as cur:
                    cur.execute("SELECT host(address) AS address FROM zradius_ip_allocations WHERE pool_id=%s ORDER BY address",(pool_id,))
                    address=next_address(pool["first"],pool["last"],(r["address"] for r in cur))
                if address is None:
                    raise HTTPException(409,"Pool exhausted")
            row=conn.execute("""INSERT INTO zradius_ip_allocations(pool_id,address,owner,kind)
            VALUES (%s,%s,%s,%s) RETURNING id,host(address) AS address,owner,kind""",
            (pool_id,address,body.owner,body.kind)).fetchone()
            audit(conn,"ipam.allocate",str(row["id"]))
    except UniqueViolation:
        raise HTTPException(409,"Address already allocated")
    return row

@app.delete("/api/v1/ipam/pools/{pool_id}/allocations/{allocation_id}",dependencies=[Depends(auth)])
def release_ip(pool_id:int,allocation_id:int):
    with db() as conn:
        conn.execute("SELECT id FROM zradius_ip_pools WHERE id=%s FOR UPDATE",(pool_id,))
        if conn.execute("SELECT 1 FROM zradius_radius_pool_exports WHERE pool_id=%s",(pool_id,)).fetchone():
            raise HTTPException(409,"Withdraw staged RADIUS pool before modifying inventory")
        if not conn.execute("DELETE FROM zradius_ip_allocations WHERE id=%s AND pool_id=%s RETURNING id",(allocation_id,pool_id)).fetchone():
            raise HTTPException(404,"Allocation not found")
        audit(conn,"ipam.release",str(allocation_id))
    return {"status":"released","runtime_enforced":False}

# Staged export for a future version-matched sqlippool runtime adapter.
@app.post("/api/v1/ipam/pools/{pool_id}/radius-export",status_code=201,dependencies=[Depends(auth)])
def stage_radius_pool(pool_id:int):
    with db() as conn:
        # Serialize with IPoE writes to avoid a conflicting static binding during export.
        conn.execute("LOCK TABLE zradius_ipoe_bindings IN SHARE MODE")
        pool=conn.execute("SELECT id,name,family(network) AS family,capacity,host(first_ip) AS first,host(last_ip) AS last FROM zradius_ip_pools WHERE id=%s FOR UPDATE",(pool_id,)).fetchone()
        if not pool:
            raise HTTPException(404,"Pool not found")
        if pool["family"]!=4 or pool["capacity"]>65536:
            raise HTTPException(422,"Staging supports IPv4 pools of at most 65536 addresses")
        if conn.execute("SELECT 1 FROM zradius_radius_pool_exports WHERE pool_id=%s",(pool_id,)).fetchone():
            raise HTTPException(409,"Pool already staged")
        conn.execute("INSERT INTO zradius_radius_pool_exports(pool_id) VALUES (%s)",(pool_id,))
        result=conn.execute("""INSERT INTO zradius_radius_pool_addresses(pool_id,address)
            SELECT %s, ip FROM (SELECT %s::inet + n AS ip
            FROM generate_series(0, %s::bigint-1) AS s(n)) AS candidates
            WHERE NOT EXISTS(SELECT 1 FROM zradius_ip_allocations a WHERE a.address=ip)
            AND NOT EXISTS(SELECT 1 FROM zradius_ipoe_bindings b WHERE b.static_ip=ip)""",
            (pool_id,pool["first"],int(pool["capacity"])))
        if result.rowcount==0:
            raise HTTPException(409,"No available addresses")
        audit(conn,"ipam.radius.stage",str(pool_id))
        return {"pool_id":pool_id,"pool_name":pool["name"],"staged_addresses":result.rowcount,"runtime_applied":False}

@app.get("/api/v1/ipam/radius-exports",dependencies=[Depends(auth)])
def radius_exports():
    with db() as conn:
        return conn.execute("""SELECT e.pool_id,p.name,e.created_at,count(a.address) AS staged_addresses,
            false AS runtime_applied FROM zradius_radius_pool_exports e
            JOIN zradius_ip_pools p ON p.id=e.pool_id
            LEFT JOIN zradius_radius_pool_addresses a ON a.pool_id=e.pool_id
            GROUP BY e.pool_id,p.name,e.created_at ORDER BY p.name""").fetchall()

@app.delete("/api/v1/ipam/pools/{pool_id}/radius-export",dependencies=[Depends(auth)])
def withdraw_radius_pool(pool_id:int):
    try:
        with db() as conn:
            conn.execute("SELECT id FROM zradius_ip_pools WHERE id=%s FOR UPDATE",(pool_id,))
            if not conn.execute("DELETE FROM zradius_radius_pool_exports WHERE pool_id=%s RETURNING pool_id",(pool_id,)).fetchone():
                raise HTTPException(404,"Export not found")
            audit(conn,"ipam.radius.withdraw",str(pool_id))
    except ForeignKeyViolation:
        raise HTTPException(409,"Remove group bindings first")
    return {"status":"withdrawn","runtime_applied":False}

class RadiusPoolBinding(BaseModel):
    pool_id:int=Field(gt=0)

@app.put("/api/v1/groups/{group}/radius-pool",dependencies=[Depends(auth)])
def bind_radius_pool(group:str,body:RadiusPoolBinding):
    try:
        with db() as conn:
            if not conn.execute("SELECT name FROM zradius_groups WHERE name=%s FOR UPDATE",(group,)).fetchone():
                raise HTTPException(404,"Group not found")
            if not conn.execute("SELECT 1 FROM zradius_radius_pool_exports WHERE pool_id=%s",(body.pool_id,)).fetchone():
                raise HTTPException(409,"Stage pool first")
            conn.execute("INSERT INTO zradius_radius_pool_groups VALUES (%s,%s) ON CONFLICT(groupname) DO UPDATE SET pool_id=excluded.pool_id",(group,body.pool_id))
            audit(conn,"group.radius_pool",group)
    except ForeignKeyViolation:
        raise HTTPException(409,"Pool no longer staged")
    return {"group":group,"pool_id":body.pool_id,"runtime_applied":False}

@app.get("/api/v1/groups/{group}/radius-pool",dependencies=[Depends(auth)])
def get_radius_pool_binding(group:str):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_groups WHERE name=%s",(group,)).fetchone():
            raise HTTPException(404,"Group not found")
        row=conn.execute("SELECT pool_id FROM zradius_radius_pool_groups WHERE groupname=%s",(group,)).fetchone()
        return {"pool_id":row["pool_id"] if row else None,"runtime_applied":False}

@app.delete("/api/v1/groups/{group}/radius-pool",dependencies=[Depends(auth)])
def unbind_radius_pool(group:str):
    with db() as conn:
        conn.execute("DELETE FROM zradius_radius_pool_groups WHERE groupname=%s",(group,))
        audit(conn,"group.radius_pool.remove",group)
    return {"status":"removed"}

# Explicit one-way activation for lab use. No live lease deletion or implicit fallback.
@app.post("/api/v1/ipam/pools/{pool_id}/radius-activate",dependencies=[Depends(auth)])
def activate_radius_pool(pool_id:int):
    with db() as conn:
        pool=conn.execute("""SELECT p.name FROM zradius_ip_pools p JOIN zradius_radius_pool_exports e ON e.pool_id=p.id
            WHERE p.id=%s FOR UPDATE OF p""",(pool_id,)).fetchone()
        if not pool:
            raise HTTPException(404,"Staged pool not found")
        if conn.execute("SELECT 1 FROM zradius_radius_pool_active WHERE pool_id=%s",(pool_id,)).fetchone():
            raise HTTPException(409,"Pool already activated")
        if conn.execute("SELECT 1 FROM radippool WHERE pool_name=%s",(pool["name"],)).fetchone():
            raise HTTPException(409,"Runtime pool name already exists")
        count=conn.execute("""INSERT INTO radippool(pool_name,framedipaddress,expiry_time)
            SELECT %s,address,TIMESTAMP '1970-01-01' FROM zradius_radius_pool_addresses WHERE pool_id=%s""",(pool["name"],pool_id)).rowcount
        if not count:
            raise HTTPException(409,"Empty pool")
        conn.execute("INSERT INTO zradius_radius_pool_active(pool_id) VALUES (%s)",(pool_id,))
        audit(conn,"ipam.radius.activate",str(pool_id))
        return {"pool_id":pool_id,"addresses":count,"runtime_enabled":os.getenv("RADIUS_ENABLE_SQLIPPOOL","false")=="true"}

@app.get("/api/v1/ipam/radius-leases",dependencies=[Depends(auth)])
def radius_leases(pool_id:int,limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT r.id,host(r.framedipaddress) AS address,r.username,r.nasipaddress,
          r.expiry_time,r.lease_session,r.lease_started_at,(r.expiry_time>now() AT TIME ZONE 'UTC') AS leased
          FROM radippool r JOIN zradius_ip_pools p ON p.name=r.pool_name
          JOIN zradius_radius_pool_active a ON a.pool_id=p.id WHERE p.id=%s
          ORDER BY r.framedipaddress LIMIT %s OFFSET %s""",(pool_id,limit,offset)).fetchall()

from hotspot import voucher_credentials

class HotspotVoucher(BaseModel):
    nas_id:int=Field(gt=0)
    validity_seconds:int=Field(default=86400,ge=60,le=2592000)
    session_seconds:int=Field(default=3600,ge=60,le=86400)
    idle_seconds:int=Field(default=300,ge=60,le=86400)
    upload_mbps:int|None=Field(default=None,ge=1,le=10000)
    download_mbps:int|None=Field(default=None,ge=1,le=10000)

@app.post("/api/v1/hotspot/vouchers",status_code=201,dependencies=[Depends(auth)])
def create_hotspot_voucher(body:HotspotVoucher):
    if (body.upload_mbps is None)!=(body.download_mbps is None):
        raise HTTPException(422,"Specify both rate limits or neither")
    if body.session_seconds>body.validity_seconds or body.idle_seconds>body.session_seconds:
        raise HTTPException(422,"Invalid time limits")
    username,password,digest=voucher_credentials()
    rate=f"{body.upload_mbps}M/{body.download_mbps}M" if body.upload_mbps else None
    with db() as conn:
        nas=conn.execute("SELECT id,type FROM nas WHERE id=%s FOR UPDATE",(body.nas_id,)).fetchone()
        if not nas:
            raise HTTPException(404,"NAS not found")
        if nas["type"]!="mikrotik":
            raise HTTPException(422,"Only MikroTik Hotspot is supported")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='hotspot'",(body.nas_id,)).fetchone():
            raise HTTPException(409,"Assign Hotspot service to NAS first")
        row=conn.execute("""INSERT INTO zradius_hotspot_vouchers(nas_id,username,password_hash,expires_at,session_seconds,idle_seconds,rate_limit)
            VALUES (%s,%s,%s,now()+make_interval(secs=>%s),%s,%s,%s)
            RETURNING id,nas_id,username,expires_at,session_seconds,idle_seconds,rate_limit,enabled""",
            (body.nas_id,username,digest,body.validity_seconds,body.session_seconds,body.idle_seconds,rate)).fetchone()
        audit(conn,"hotspot.voucher.create",username)
    return {**row,"password":password}

@app.get("/api/v1/hotspot/vouchers",dependencies=[Depends(auth)])
def list_hotspot_vouchers(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT id,nas_id,username,expires_at,session_seconds,idle_seconds,rate_limit,enabled,
            expires_at<=now() AS expired FROM zradius_hotspot_vouchers ORDER BY id DESC LIMIT %s OFFSET %s""",(limit,offset)).fetchall()

@app.delete("/api/v1/hotspot/vouchers/{voucher_id}",dependencies=[Depends(auth)])
def revoke_hotspot_voucher(voucher_id:int):
    with db() as conn:
        row=conn.execute("UPDATE zradius_hotspot_vouchers SET enabled=false WHERE id=%s RETURNING username",(voucher_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Voucher not found")
        audit(conn,"hotspot.voucher.revoke",row["username"])
    return {"status":"revoked","existing_sessions_terminated":False}

from hotspot import voucher_credentials as device_credentials

class DeviceUserCreate(BaseModel):
    username:str=Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")

class DeviceGrant(BaseModel):
    role:Literal["read","write","full"]

@app.get("/api/v1/device-aaa/users",dependencies=[Depends(auth)])
def device_users():
    with db() as conn:
        return conn.execute("SELECT id,username,enabled,created_at FROM zradius_device_users ORDER BY username").fetchall()

@app.post("/api/v1/device-aaa/users",status_code=201,dependencies=[Depends(auth)])
def create_device_user(body:DeviceUserCreate):
    _,password,digest=device_credentials()
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_device_users(username,password_hash) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id,username,enabled",(body.username,digest)).fetchone()
        if not row:
            raise HTTPException(409,"Device user exists")
        audit(conn,"device.user.create",body.username)
    return {**row,"password":password}

@app.put("/api/v1/device-aaa/users/{user_id}/state",dependencies=[Depends(auth)])
def device_user_state(user_id:int,body:UserState):
    with db() as conn:
        row=conn.execute("UPDATE zradius_device_users SET enabled=%s WHERE id=%s RETURNING id,username,enabled",(body.enabled,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"Device user not found")
        audit(conn,"device.user.state",row["username"])
    return row

@app.post("/api/v1/device-aaa/users/{user_id}/rotate-password",dependencies=[Depends(auth)])
def rotate_device_password(user_id:int):
    _,password,digest=device_credentials()
    with db() as conn:
        row=conn.execute("UPDATE zradius_device_users SET password_hash=%s WHERE id=%s RETURNING username",(digest,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"Device user not found")
        audit(conn,"device.user.rotate",row["username"])
    return {"username":row["username"],"password":password}

@app.get("/api/v1/device-aaa/users/{user_id}/grants",dependencies=[Depends(auth)])
def device_grants(user_id:int):
    with db() as conn:
        return conn.execute("SELECT g.nas_id,n.shortname,g.role FROM zradius_device_grants g JOIN nas n ON n.id=g.nas_id WHERE g.user_id=%s ORDER BY n.shortname",(user_id,)).fetchall()

@app.put("/api/v1/device-aaa/users/{user_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def set_device_grant(user_id:int,nas_id:int,body:DeviceGrant):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_device_users WHERE id=%s FOR UPDATE",(user_id,)).fetchone():
            raise HTTPException(404,"Device user not found")
        if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"MikroTik NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign Device AAA service first")
        conn.execute("INSERT INTO zradius_device_grants VALUES (%s,%s,%s) ON CONFLICT(user_id,nas_id) DO UPDATE SET role=excluded.role",(user_id,nas_id,body.role))
        audit(conn,"device.grant.set",f"{user_id}:{nas_id}:{body.role}")
    return {"role":body.role}

@app.delete("/api/v1/device-aaa/users/{user_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def delete_device_grant(user_id:int,nas_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_device_grants WHERE user_id=%s AND nas_id=%s",(user_id,nas_id))
        audit(conn,"device.grant.remove",f"{user_id}:{nas_id}")
    return {"status":"removed","existing_sessions_terminated":False}

@app.get("/api/v1/device-aaa/auth-log",dependencies=[Depends(auth)])
def device_auth_log(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("SELECT id,username,host(source_ip) AS source_ip,result,created_at FROM zradius_device_auth_log ORDER BY id DESC LIMIT %s OFFSET %s",(limit,offset)).fetchall()

# PEAP-MSCHAPv2 credentials are independent from PPP and device administrators.
class EapUser(BaseModel):
    username:str=Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")
    nt_password:SecretStr=Field(min_length=32,max_length=32)
    vlan_id:int|None=Field(default=None,ge=1,le=4094)

@app.get("/api/v1/eap/users",dependencies=[Depends(auth)])
def eap_users():
    with db() as conn:
        return conn.execute("SELECT username,enabled,vlan_id,created_at FROM zradius_eap_users ORDER BY username").fetchall()

@app.put("/api/v1/eap/users/{username}",dependencies=[Depends(auth)])
def upsert_eap_user(username:str,body:EapUser):
    import re
    digest=body.nt_password.get_secret_value().lower()
    if username!=body.username or not re.fullmatch(r"[0-9a-f]{32}",digest):
        raise HTTPException(422,"Invalid identity or NT hash")
    with db() as conn:
        conn.execute("""INSERT INTO zradius_eap_users(username,nt_password,vlan_id) VALUES (%s,%s,%s)
            ON CONFLICT(username) DO UPDATE SET nt_password=excluded.nt_password,vlan_id=excluded.vlan_id""",(username,digest,body.vlan_id))
        audit(conn,"eap.user.upsert",username)
    return {"username":username}

@app.put("/api/v1/eap/users/{username}/state",dependencies=[Depends(auth)])
def eap_user_state(username:str,body:UserState):
    with db() as conn:
        if not conn.execute("UPDATE zradius_eap_users SET enabled=%s WHERE username=%s RETURNING username",(body.enabled,username)).fetchone():
            raise HTTPException(404,"EAP user not found")
        audit(conn,"eap.user.state",username)
    return {"enabled":body.enabled}

@app.put("/api/v1/eap/users/{username}/grants/{nas_id}",dependencies=[Depends(auth)])
def eap_grant(username:str,nas_id:int):
    with db() as conn:
        if not conn.execute("SELECT username FROM zradius_eap_users WHERE username=%s FOR UPDATE",(username,)).fetchone():
            raise HTTPException(404,"EAP user not found")
        if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code IN ('dot1x','wpa-enterprise')",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign EAP service first")
        conn.execute("INSERT INTO zradius_eap_grants VALUES (%s,%s) ON CONFLICT DO NOTHING",(username,nas_id))
        audit(conn,"eap.grant",f"{username}:{nas_id}")
    return {"status":"assigned"}

@app.delete("/api/v1/eap/users/{username}/grants/{nas_id}",dependencies=[Depends(auth)])
def revoke_eap_grant(username:str,nas_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_eap_grants WHERE username=%s AND nas_id=%s",(username,nas_id))
        audit(conn,"eap.grant.remove",f"{username}:{nas_id}")
    return {"status":"removed"}

from pki import certificate_metadata

class CertificateImport(BaseModel):
    pem:str=Field(min_length=100,max_length=32768)
    purpose:Literal["ca","server","client"]

class CertificateGrant(BaseModel):
    vlan_id:int|None=Field(default=None,ge=1,le=4094)

@app.get("/api/v1/pki/certificates",dependencies=[Depends(auth)])
def pki_certificates():
    with db() as conn:
        return conn.execute("""SELECT fingerprint,purpose,subject,issuer,serial,not_before,not_after,revoked_at,
        CASE WHEN revoked_at IS NOT NULL THEN 'revoked' WHEN not_after<=now() THEN 'expired'
        WHEN not_before>now() THEN 'pending' ELSE 'valid' END AS state
        FROM zradius_pki_certificates ORDER BY not_after""").fetchall()

@app.post("/api/v1/pki/certificates",status_code=201,dependencies=[Depends(auth)])
def import_certificate(body:CertificateImport):
    try:
        m=certificate_metadata(body.pem,body.purpose)
    except (ValueError,UnicodeError):
        raise HTTPException(422,"Invalid public certificate or purpose")
    with db() as conn:
        row=conn.execute("""INSERT INTO zradius_pki_certificates(fingerprint,purpose,subject,issuer,serial,not_before,not_after,pem)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING fingerprint""",
        (m["fingerprint"],body.purpose,m["subject"],m["issuer"],m["serial"],m["not_before"],m["not_after"],body.pem)).fetchone()
        if not row:
            raise HTTPException(409,"Certificate already registered")
        audit(conn,"pki.import",m["fingerprint"])
    return m

@app.get("/api/v1/pki/certificates/{fingerprint}/pem",dependencies=[Depends(auth)])
def certificate_pem(fingerprint:str):
    with db() as conn:
        row=conn.execute("SELECT pem FROM zradius_pki_certificates WHERE fingerprint=%s",(fingerprint,)).fetchone()
        if not row:
            raise HTTPException(404,"Certificate not found")
        return row

@app.post("/api/v1/pki/certificates/{fingerprint}/revoke",dependencies=[Depends(auth)])
def revoke_certificate(fingerprint:str):
    with db() as conn:
        row=conn.execute("UPDATE zradius_pki_certificates SET revoked_at=COALESCE(revoked_at,now()) WHERE fingerprint=%s RETURNING fingerprint",(fingerprint,)).fetchone()
        if not row:
            raise HTTPException(404,"Certificate not found")
        audit(conn,"pki.revoke",fingerprint)
    return {"status":"revoked","runtime_enforced":False}

@app.put("/api/v1/pki/certificates/{fingerprint}/grants/{nas_id}",dependencies=[Depends(auth)])
def certificate_grant(fingerprint:str,nas_id:int,body:CertificateGrant):
    with db() as conn:
        if not conn.execute("SELECT fingerprint FROM zradius_pki_certificates WHERE fingerprint=%s AND purpose='client' AND revoked_at IS NULL AND not_before<=now() AND not_after>now() FOR UPDATE",(fingerprint,)).fetchone():
            raise HTTPException(409,"Active client certificate required")
        if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code IN ('dot1x','wpa-enterprise')",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign EAP service first")
        conn.execute("INSERT INTO zradius_pki_grants VALUES (%s,%s,%s) ON CONFLICT(fingerprint,nas_id) DO UPDATE SET vlan_id=excluded.vlan_id",(fingerprint,nas_id,body.vlan_id))
        audit(conn,"pki.grant",fingerprint+":"+str(nas_id))
    return {"status":"assigned","runtime_enforced":False}

@app.get("/api/v1/pki/certificates/{fingerprint}/grants",dependencies=[Depends(auth)])
def certificate_grants(fingerprint:str):
    with db() as conn:
        return conn.execute("SELECT g.nas_id,n.shortname,g.vlan_id FROM zradius_pki_grants g JOIN nas n ON n.id=g.nas_id WHERE fingerprint=%s ORDER BY n.shortname",(fingerprint,)).fetchall()

@app.delete("/api/v1/pki/certificates/{fingerprint}/grants/{nas_id}",dependencies=[Depends(auth)])
def revoke_certificate_grant(fingerprint:str,nas_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_pki_grants WHERE fingerprint=%s AND nas_id=%s",(fingerprint,nas_id))
        audit(conn,"pki.grant.remove",fingerprint+":"+str(nas_id))
    return {"status":"removed","runtime_enforced":False}

# Proxy registry: explicit realms and individual source NAS grants.
class ProxyRealm(BaseModel):
    realm:str=Field(min_length=3,max_length=128,pattern=r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
    home_ip:IPvAnyAddress
    secret:SecretStr=Field(min_length=32,max_length=128)

@app.get("/api/v1/proxy/realms",dependencies=[Depends(auth)])
def proxy_realms():
    with db() as conn:
        return conn.execute("SELECT id,realm,host(home_ip) AS home_ip,enabled,created_at FROM zradius_proxy_realms ORDER BY realm").fetchall()

@app.post("/api/v1/proxy/realms",status_code=201,dependencies=[Depends(auth)])
def create_proxy_realm(body:ProxyRealm):
    import re
    ip=body.home_ip
    if ip.version!=4 or ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_link_local or ip.is_reserved:
        raise HTTPException(422,"Invalid upstream IPv4")
    if not re.fullmatch(r"[a-zA-Z0-9]{32,128}",body.secret.get_secret_value()) or "." not in body.realm or ".." in body.realm:
        raise HTTPException(422,"Invalid realm or shared secret")
    with db() as conn:
        row=conn.execute("""INSERT INTO zradius_proxy_realms(realm,home_ip,secret) VALUES (%s,%s,%s)
            ON CONFLICT DO NOTHING RETURNING id,realm,host(home_ip) AS home_ip,enabled""",(body.realm,str(ip),body.secret.get_secret_value())).fetchone()
        if not row:
            raise HTTPException(409,"Realm exists")
        audit(conn,"proxy.realm.create",body.realm)
    return row

@app.put("/api/v1/proxy/realms/{realm_id}/state",dependencies=[Depends(auth)])
def proxy_realm_state(realm_id:int,body:UserState):
    with db() as conn:
        if not conn.execute("UPDATE zradius_proxy_realms SET enabled=%s WHERE id=%s RETURNING id",(body.enabled,realm_id)).fetchone():
            raise HTTPException(404,"Realm not found")
        audit(conn,"proxy.realm.state",str(realm_id))
    return {"enabled":body.enabled,"restart_required_for_enable":True}

@app.put("/api/v1/proxy/realms/{realm_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def proxy_grant(realm_id:int,nas_id:int):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_proxy_realms WHERE id=%s FOR UPDATE",(realm_id,)).fetchone():
            raise HTTPException(404,"Realm not found")
        if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='proxy'",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign Proxy service first")
        conn.execute("INSERT INTO zradius_proxy_grants VALUES (%s,%s) ON CONFLICT DO NOTHING",(realm_id,nas_id))
        audit(conn,"proxy.grant",f"{realm_id}:{nas_id}")
    return {"status":"assigned"}

@app.get("/api/v1/proxy/realms/{realm_id}/grants",dependencies=[Depends(auth)])
def proxy_grants(realm_id:int):
    with db() as conn:
        return conn.execute("SELECT g.nas_id,n.shortname FROM zradius_proxy_grants g JOIN nas n ON n.id=g.nas_id WHERE g.realm_id=%s ORDER BY n.shortname",(realm_id,)).fetchall()

@app.delete("/api/v1/proxy/realms/{realm_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def revoke_proxy_grant(realm_id:int,nas_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_proxy_grants WHERE realm_id=%s AND nas_id=%s",(realm_id,nas_id))
        audit(conn,"proxy.grant.remove",f"{realm_id}:{nas_id}")
    return {"status":"removed"}
