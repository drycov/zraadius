import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, SecretStr, IPvAnyAddress
from typing import Literal
from psycopg.errors import UniqueViolation
from coa import send, destination_allowed
from schema_version import require_schema
from secret_crypto import key as secret_key, seal, unseal
from cryptography.exceptions import InvalidTag
from contextvars import ContextVar
from starlette.concurrency import run_in_threadpool
from iam import hash_password, verify_password, token_digest, new_token, permitted
from uuid import UUID
from service_tokens import PREFIX as SERVICE_PREFIX, SCOPES as SERVICE_SCOPES, issue_token, valid_token, allowed as service_allowed
from mfa import new_seed, seed_from_envelope, match_step, recovery_codes, uri as mfa_uri
actor_context=ContextVar('actor',default=None)

ROOT = Path(__file__).parent
bearer = HTTPBearer(auto_error=False)

def db():
    return psycopg.connect(row_factory=dict_row, connect_timeout=5)

@asynccontextmanager
async def lifespan(app):
    token = os.environ.get("ADMIN_TOKEN", "")
    if os.getenv("ZRADIUS_LEGACY_TOKEN_ENABLED","false")=="true" and (len(token)<32 or token.startswith("replace_with")):
        raise RuntimeError("Set a random ADMIN_TOKEN for explicit legacy mode")
    secret_key()
    with db() as conn:
        require_schema(conn)
    yield

app = FastAPI(title="ZRADIUS", version="0.1.0-alpha", lifespan=lifespan)

async def auth(request:Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or len(credentials.credentials)>512:
        raise HTTPException(401,"Unauthorized")
    token=credentials.credentials
    if token.startswith(SERVICE_PREFIX):
        if not valid_token(token):
            raise HTTPException(401,"Unauthorized")
        def lookup_service():
            with db() as conn:
                return conn.execute("""SELECT a.name,t.id,t.scopes FROM zradius_service_tokens t
                    JOIN zradius_service_accounts a ON a.id=t.account_id
                    WHERE t.token_hash=%s AND t.revoked_at IS NULL AND t.expires_at>now() AND a.enabled""",
                    (token_digest(token),)).fetchone()
        service=await run_in_threadpool(lookup_service)
        if not service:
            raise HTTPException(401,"Unauthorized")
        route=getattr(request.scope.get("route"),"path",None)
        if not service_allowed(service["scopes"],request.method,route):
            raise HTTPException(403,"Forbidden")
        actor="service:"+str(service["id"])
        actor_context.set(actor)
        return {"username":actor,"role":"service"}
    legacy=os.getenv("ADMIN_TOKEN","")
    if os.getenv("ZRADIUS_LEGACY_TOKEN_ENABLED","false")=="true" and legacy and secrets.compare_digest(token.encode(),legacy.encode()):
        principal={"username":"legacy-token","role":"admin"}
    else:
        def lookup():
            with db() as conn:
                return conn.execute("""SELECT u.id,u.username,u.role FROM zradius_admin_sessions s JOIN zradius_admin_users u ON u.id=s.user_id
                    WHERE s.token_hash=%s AND s.expires_at>now() AND u.enabled""",(token_digest(token),)).fetchone()
        principal=await run_in_threadpool(lookup)
        if not principal:
            raise HTTPException(401,"Unauthorized")
    if request.url.path not in ("/api/v1/iam/me","/api/v1/iam/logout","/api/v1/iam/password","/api/v1/iam/my-sessions","/api/v1/iam/mfa/status","/api/v1/iam/mfa/setup","/api/v1/iam/mfa/confirm","/api/v1/iam/mfa/disable") and not permitted(principal["role"],request.method,request.url.path):
        raise HTTPException(403,"Forbidden")
    actor_context.set(principal["username"])
    return principal

class User(BaseModel):
    username: str = Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: SecretStr = Field(min_length=12,max_length=253)

class Group(BaseModel):
    name: str = Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")

def audit(conn, action, subject):
    conn.execute("INSERT INTO zradius_audit(action,subject,actor) VALUES (%s,%s,%s)", (action,subject,actor_context.get()))

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
            require_schema(conn)
    except (psycopg.Error, RuntimeError):
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
def accounting(limit: int = 100, offset: int = 0, active: bool = False, username: str | None = None, nas: IPvAnyAddress | None = None, before: int | None = None, order: Literal["desc","asc"] = "desc"):
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(422, "Invalid pagination")
    if username is not None and (not username or len(username)>253):
        raise HTTPException(422,"Invalid username")
    if before is not None and (before<1 or offset or order!="desc"):
        raise HTTPException(422,"Cursor requires descending order and zero offset")
    clauses=[]
    params=[]
    if active:
        clauses.append("acctstoptime IS NULL")
    if username is not None:
        clauses.append("username=%s")
        params.append(username)
    if nas is not None:
        clauses.append("nasipaddress=%s::inet")
        params.append(str(nas))
    if before is not None:
        clauses.append("radacctid<%s")
        params.append(before)
    where=" AND ".join(clauses) or "TRUE"
    direction="ASC" if order=="asc" else "DESC"
    with db() as conn:
        return conn.execute(
            f"""SELECT radacctid, username, acctsessionid, host(nasipaddress) AS nasipaddress,
               host(framedipaddress) AS framedipaddress, acctstarttime, acctstoptime,
               acctsessiontime, acctinputoctets, acctoutputoctets
               FROM radacct WHERE {where}
               ORDER BY radacctid {direction} LIMIT %s OFFSET %s""",
            (*params,limit,offset)
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
        return conn.execute("SELECT n.id,n.nasname,n.shortname,n.type,n.description,             ARRAY(SELECT s.service_code FROM zradius_nas_services s WHERE s.nas_id=n.id ORDER BY s.service_code) AS services             FROM nas n ORDER BY n.id").fetchall()

@app.post("/api/v1/nas", status_code=201, dependencies=[Depends(auth)])
def create_nas(body: NAS):
    address=str(body.address)
    if body.address.is_loopback or body.address.is_unspecified or body.address.is_multicast or body.address.is_link_local:
        raise HTTPException(422,"Invalid NAS address")
    secret=body.secret.get_secret_value()
    if not secret.isascii() or not secret.isalnum():
        raise HTTPException(422,"Use an alphanumeric random shared secret")
    with db() as conn:
        row=conn.execute("INSERT INTO nas(nasname,shortname,type,secret,description) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,nasname,shortname,type,description",(address,body.name,body.vendor,seal(secret,'nas:'+address),body.description)).fetchone()
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

def session_action(session_id: int, rate: str | None = None, vpn_only: bool = False):
    if os.environ.get("COA_ENABLED","false").lower() != "true":
        raise HTTPException(409,"CoA is disabled")
    action = "coa" if rate else "disconnect"
    try:
        with db() as conn:
            row = conn.execute("""SELECT a.username,a.acctsessionid,host(a.nasipaddress) AS address,n.secret,n.type
              FROM radacct a JOIN nas n ON n.nasname=host(a.nasipaddress)
              WHERE a.radacctid=%s AND a.acctstoptime IS NULL
                AND (NOT %s OR (a.zradius_service='l2tp' AND n.type='mikrotik'
                  AND EXISTS(SELECT 1 FROM zradius_nas_services s WHERE s.nas_id=n.id AND s.service_code='l2tp')))""",(session_id,vpn_only)).fetchone()
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
        status=send(row["address"],unseal(row["secret"],"nas:"+row["address"]),row["username"],row["acctsessionid"],rate)
    except (ValueError,TypeError,InvalidTag):
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
    profile_id:int|None=Field(default=None,gt=0)
    role:str|None=Field(default=None,min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    filter_id:str|None=Field(default=None,min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")

def resolve_device_grant(conn,body):
    if body.profile_id is not None:
        if body.role is not None or body.filter_id is not None:
            raise HTTPException(422,"Choose a reply profile or manual attributes, not both")
        profile=conn.execute("SELECT role,filter_id FROM zradius_device_reply_profiles WHERE id=%s",(body.profile_id,)).fetchone()
        if not profile:
            raise HTTPException(404,"Reply profile not found")
        return profile["role"],profile["filter_id"],body.profile_id
    if body.role is None or not conn.execute("SELECT 1 FROM zradius_device_role_catalog WHERE name=%s",(body.role,)).fetchone():
        raise HTTPException(422,"Unknown RouterOS role")
    return body.role,body.filter_id,None

class DeviceRoleCreate(BaseModel):
    name:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    description:str=Field(default="",max_length=200)

@app.get("/api/v1/device-aaa/roles",dependencies=[Depends(auth)])
def device_role_catalog():
    with db() as conn:
        return conn.execute("SELECT name,description FROM zradius_device_role_catalog ORDER BY name").fetchall()

@app.post("/api/v1/device-aaa/roles",status_code=201,dependencies=[Depends(auth)])
def create_device_role(body:DeviceRoleCreate):
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_device_role_catalog(name,description) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING name,description",(body.name,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"Device role already exists")
        audit(conn,"device.role.create",body.name)
        return row


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
        if conn.execute("SELECT 1 FROM zradius_device_users WHERE id=%s AND identity_id IS NOT NULL FOR UPDATE",(user_id,)).fetchone():
            raise HTTPException(409,"Use unified identity password reset")
        row=conn.execute("UPDATE zradius_device_users SET password_hash=%s WHERE id=%s RETURNING username",(digest,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"Device user not found")
        audit(conn,"device.user.rotate",row["username"])
    return {"username":row["username"],"password":password}

@app.get("/api/v1/device-aaa/users/{user_id}/grants",dependencies=[Depends(auth)])
def device_grants(user_id:int):
    with db() as conn:
        return conn.execute("SELECT g.nas_id,n.shortname,g.role,g.filter_id,g.profile_id FROM zradius_device_grants g JOIN nas n ON n.id=g.nas_id WHERE g.user_id=%s ORDER BY n.shortname",(user_id,)).fetchall()

@app.put("/api/v1/device-aaa/users/{user_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def set_device_grant(user_id:int,nas_id:int,body:DeviceGrant):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_device_users WHERE id=%s FOR UPDATE",(user_id,)).fetchone():
            raise HTTPException(404,"Device user not found")
        if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"MikroTik NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign Device AAA service first")
        role,filter_id,profile_id=resolve_device_grant(conn,body)
        conn.execute("""INSERT INTO zradius_device_grants(user_id,nas_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(user_id,nas_id) DO UPDATE SET role=excluded.role,filter_id=excluded.filter_id,profile_id=excluded.profile_id""",(user_id,nas_id,role,filter_id,profile_id))
        audit(conn,"device.grant.set",f"{user_id}:{nas_id}:{role}")
    return {"role":role,"filter_id":filter_id,"profile_id":profile_id}

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
            ON CONFLICT DO NOTHING RETURNING id,realm,host(home_ip) AS home_ip,enabled""",(body.realm,str(ip),seal(body.secret.get_secret_value(),'zradius_proxy_realms:'+body.realm))).fetchone()
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

class ManagementLogin(BaseModel):
    username:str=Field(min_length=1,max_length=64,pattern=r"^[a-zA-Z0-9_.-]+$")
    password:SecretStr=Field(min_length=1,max_length=128)

class ManagementSignIn(ManagementLogin):
    otp:SecretStr|None=Field(default=None,max_length=64)

class ManagementUser(ManagementLogin):
    role:Literal["admin","operator","auditor"]="auditor"

@app.post("/api/v1/iam/login")
def management_login(body:ManagementSignIn,request:Request,response:Response):
    # Shared database limiter: global and per identity, independent of forwarded headers.
    buckets=sorted([token_digest("global-login"),token_digest("login:"+body.username.lower())])
    with db() as conn:
        for bucket in buckets:
            row=conn.execute("""INSERT INTO zradius_login_limits(bucket,attempts) VALUES (%s,1)
                ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN zradius_login_limits.window_start<now()-interval '5 minutes' THEN 1 ELSE zradius_login_limits.attempts+1 END,
                window_start=CASE WHEN zradius_login_limits.window_start<now()-interval '5 minutes' THEN now() ELSE zradius_login_limits.window_start END
                RETURNING attempts""",(bucket,)).fetchone()
            if row["attempts"]>(100 if bucket==token_digest("global-login") else 10):
                conn.commit()
                raise HTTPException(429,"Too many login attempts")
        user=conn.execute("SELECT id,username,password_hash,role,enabled,mfa_secret,mfa_last_step,mfa_recovery FROM zradius_admin_users WHERE username=%s FOR UPDATE",(body.username,)).fetchone()
        if not user or not user["enabled"] or not verify_password(user["password_hash"],body.password.get_secret_value()):
            conn.commit()
            raise HTTPException(401,"Invalid credentials")
        if user["mfa_secret"]:
            if body.otp is None:
                conn.commit()
                response.headers["Cache-Control"]="no-store"
                return {"mfa_required":True}
            if not consume_mfa(conn,user,body.otp.get_secret_value()):
                conn.commit()
                raise HTTPException(401,"Invalid credentials or second factor")
        token,digest=new_token()
        conn.execute("DELETE FROM zradius_admin_sessions WHERE expires_at<=now()")
        conn.execute("INSERT INTO zradius_admin_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval '8 hours')",(digest,user["id"]))
        conn.execute("INSERT INTO zradius_audit(action,subject,actor) VALUES ('iam.login',%s,%s)",(user["username"],user["username"]))
    response.headers["Cache-Control"]="no-store"
    return {"access_token":token,"token_type":"bearer","expires_in":28800,"username":user["username"],"role":user["role"]}

@app.get("/api/v1/iam/me")
def management_me(principal=Depends(auth)):
    return principal

@app.post("/api/v1/iam/logout")
def management_logout(credentials:HTTPAuthorizationCredentials=Depends(bearer),principal=Depends(auth)):
    with db() as conn:
        conn.execute("DELETE FROM zradius_admin_sessions WHERE token_hash=%s",(token_digest(credentials.credentials),))
        audit(conn,"iam.logout",principal["username"])
    return {"status":"logged_out"}

@app.get("/api/v1/iam/users",dependencies=[Depends(auth)])
def management_users():
    with db() as conn:
        return conn.execute("SELECT id,username,role,enabled,created_at,mfa_secret IS NOT NULL AS mfa_enabled FROM zradius_admin_users ORDER BY username").fetchall()

@app.post("/api/v1/iam/users",status_code=201,dependencies=[Depends(auth)])
def management_create(body:ManagementUser):
    try:
        digest=hash_password(body.password.get_secret_value())
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_admin_users(username,password_hash,role) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,username,role,enabled",(body.username,digest,body.role)).fetchone()
        if not row:
            raise HTTPException(409,"Management user exists")
        audit(conn,"iam.user.create",body.username)
    return row

@app.put("/api/v1/iam/users/{user_id}/state",dependencies=[Depends(auth)])
def management_state(user_id:int,body:UserState):
    with db() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7281192202)")
        row=conn.execute("SELECT username,role FROM zradius_admin_users WHERE id=%s FOR UPDATE",(user_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Management user not found")
        if not body.enabled and row["role"]=="admin" and not conn.execute("SELECT 1 FROM zradius_admin_users WHERE role='admin' AND enabled AND id<>%s",(user_id,)).fetchone():
            raise HTTPException(409,"Cannot disable last active administrator")
        conn.execute("UPDATE zradius_admin_users SET enabled=%s WHERE id=%s",(body.enabled,user_id))
        if not body.enabled:
            conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(user_id,))
        audit(conn,"iam.user.state",row["username"])
    return {"enabled":body.enabled}

class ManagementPassword(BaseModel):
    password:SecretStr=Field(min_length=16,max_length=128)

class OwnPassword(ManagementPassword):
    current_password:SecretStr=Field(min_length=1,max_length=128)

class ManagementRole(BaseModel):
    role:Literal["admin","operator","auditor"]

@app.put("/api/v1/iam/password")
def own_password(body:OwnPassword,principal=Depends(auth)):
    if not principal.get("id"):
        raise HTTPException(403,"Personal session required")
    with db() as conn:
        row=conn.execute("SELECT password_hash FROM zradius_admin_users WHERE id=%s AND enabled FOR UPDATE",(principal["id"],)).fetchone()
        if not row or not verify_password(row["password_hash"],body.current_password.get_secret_value()):
            raise HTTPException(401,"Invalid current password")
        digest=hash_password(body.password.get_secret_value())
        conn.execute("UPDATE zradius_admin_users SET password_hash=%s,mfa_pending=NULL,mfa_pending_until=NULL WHERE id=%s",(digest,principal["id"]))
        conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(principal["id"],))
        audit(conn,"iam.password.change",principal["username"])
    return {"status":"changed","reauthentication_required":True}

@app.put("/api/v1/iam/users/{user_id}/password",dependencies=[Depends(auth)])
def reset_management_password(user_id:int,body:ManagementPassword):
    digest=hash_password(body.password.get_secret_value())
    with db() as conn:
        row=conn.execute("UPDATE zradius_admin_users SET password_hash=%s,mfa_pending=NULL,mfa_pending_until=NULL WHERE id=%s RETURNING username",(digest,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"Management user not found")
        conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(user_id,))
        audit(conn,"iam.password.reset",row["username"])
    return {"status":"changed","sessions_revoked":True}

@app.put("/api/v1/iam/users/{user_id}/role",dependencies=[Depends(auth)])
def management_role(user_id:int,body:ManagementRole):
    with db() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7281192202)")
        row=conn.execute("SELECT username,role,enabled FROM zradius_admin_users WHERE id=%s FOR UPDATE",(user_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Management user not found")
        if row["role"]=="admin" and row["enabled"] and body.role!="admin" and not conn.execute("SELECT 1 FROM zradius_admin_users WHERE role='admin' AND enabled AND id<>%s",(user_id,)).fetchone():
            raise HTTPException(409,"Cannot demote last active administrator")
        conn.execute("UPDATE zradius_admin_users SET role=%s WHERE id=%s",(body.role,user_id))
        conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(user_id,))
        audit(conn,"iam.role.change",row["username"]+":"+body.role)
    return {"role":body.role,"sessions_revoked":True}

@app.get("/api/v1/iam/sessions",dependencies=[Depends(auth)])
def management_sessions():
    with db() as conn:
        return conn.execute("""SELECT s.session_id,u.username,s.created_at,s.expires_at
            FROM zradius_admin_sessions s JOIN zradius_admin_users u ON u.id=s.user_id
            WHERE s.expires_at>now() ORDER BY s.created_at DESC LIMIT 500""").fetchall()

@app.get("/api/v1/iam/my-sessions")
def my_sessions(principal=Depends(auth),credentials:HTTPAuthorizationCredentials=Depends(bearer)):
    if not principal.get("id"):
        raise HTTPException(403,"Personal session required")
    with db() as conn:
        return conn.execute("""SELECT session_id,created_at,expires_at,token_hash=%s AS current
            FROM zradius_admin_sessions WHERE user_id=%s AND expires_at>now() ORDER BY created_at DESC""",
            (token_digest(credentials.credentials),principal["id"])).fetchall()

@app.delete("/api/v1/iam/sessions/{session_id}",dependencies=[Depends(auth)])
def revoke_management_session(session_id:UUID):
    with db() as conn:
        row=conn.execute("DELETE FROM zradius_admin_sessions WHERE session_id=%s RETURNING user_id",(session_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Session not found")
        audit(conn,"iam.session.revoke",str(session_id))
    return {"status":"revoked"}

def consume_mfa(conn,row,code):
    if not row["mfa_secret"]:
        return False
    step=match_step(seed_from_envelope(row["mfa_secret"],row["id"]),code,row["mfa_last_step"])
    if step is not None:
        conn.execute("UPDATE zradius_admin_users SET mfa_last_step=%s WHERE id=%s",(step,row["id"]))
        return True
    digest=token_digest(code)
    if any(secrets.compare_digest(digest,item) for item in row["mfa_recovery"]):
        conn.execute("UPDATE zradius_admin_users SET mfa_recovery=array_remove(mfa_recovery,%s) WHERE id=%s",(digest,row["id"]))
        conn.execute("INSERT INTO zradius_audit(action,subject,actor) VALUES (\'iam.mfa.recovery.used\',%s,%s)",(row["username"],row["username"]))
        return True
    return False

class MfaPassword(BaseModel):
    password:SecretStr=Field(min_length=1,max_length=128)

class MfaProof(MfaPassword):
    otp:SecretStr=Field(min_length=6,max_length=64)

def mfa_user(conn,principal,password):
    if not principal.get("id"):
        raise HTTPException(403,"Personal session required")
    bucket=token_digest("mfa-proof:"+str(principal["id"]))
    limit=conn.execute("""INSERT INTO zradius_login_limits(bucket,attempts) VALUES (%s,1)
        ON CONFLICT(bucket) DO UPDATE SET attempts=CASE WHEN zradius_login_limits.window_start<now()-interval '5 minutes' THEN 1 ELSE zradius_login_limits.attempts+1 END,
        window_start=CASE WHEN zradius_login_limits.window_start<now()-interval '5 minutes' THEN now() ELSE zradius_login_limits.window_start END RETURNING attempts""",(bucket,)).fetchone()
    conn.commit()
    if limit["attempts"]>10:
        raise HTTPException(429,"Too many MFA attempts")
    row=conn.execute("SELECT * FROM zradius_admin_users WHERE id=%s AND enabled FOR UPDATE",(principal["id"],)).fetchone()
    if not row or not verify_password(row["password_hash"],password):
        raise HTTPException(401,"Invalid credentials")
    return row

@app.get("/api/v1/iam/mfa/status")
def mfa_status(principal=Depends(auth)):
    if not principal.get("id"):
        raise HTTPException(403,"Personal session required")
    with db() as conn:
        return conn.execute("SELECT mfa_secret IS NOT NULL AS enabled, cardinality(mfa_recovery) AS recovery_remaining FROM zradius_admin_users WHERE id=%s",(principal["id"],)).fetchone()

@app.post("/api/v1/iam/mfa/setup")
def mfa_setup(body:MfaPassword,response:Response,principal=Depends(auth)):
    with db() as conn:
        row=mfa_user(conn,principal,body.password.get_secret_value())
        if row["mfa_secret"]:
            raise HTTPException(409,"MFA already enabled")
        envelope,seed=new_seed(row["id"])
        conn.execute("UPDATE zradius_admin_users SET mfa_pending=%s,mfa_pending_until=now()+interval '10 minutes' WHERE id=%s",(envelope,row["id"]))
        audit(conn,"iam.mfa.setup",row["username"])
    response.headers["Cache-Control"]="no-store"
    return {"secret":seed,"otpauth_uri":mfa_uri(row["username"],seed),"expires_in":600}

@app.post("/api/v1/iam/mfa/confirm")
def mfa_confirm(body:MfaProof,response:Response,principal=Depends(auth)):
    with db() as conn:
        row=mfa_user(conn,principal,body.password.get_secret_value())
        if row["mfa_secret"] or not row["mfa_pending"] or not conn.execute("SELECT 1 FROM zradius_admin_users WHERE id=%s AND mfa_pending_until>now()",(row["id"],)).fetchone():
            raise HTTPException(409,"No active enrollment")
        step=match_step(seed_from_envelope(row["mfa_pending"],row["id"]),body.otp.get_secret_value())
        if step is None:
            raise HTTPException(401,"Invalid OTP")
        codes,digests=recovery_codes()
        conn.execute("UPDATE zradius_admin_users SET mfa_secret=mfa_pending,mfa_pending=NULL,mfa_pending_until=NULL,mfa_last_step=%s,mfa_recovery=%s WHERE id=%s",(step,digests,row["id"]))
        conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(row["id"],))
        audit(conn,"iam.mfa.enabled",row["username"])
    response.headers["Cache-Control"]="no-store"
    return {"recovery_codes":codes,"reauthentication_required":True}

@app.post("/api/v1/iam/mfa/disable")
def mfa_disable(body:MfaProof,principal=Depends(auth)):
    with db() as conn:
        row=mfa_user(conn,principal,body.password.get_secret_value())
        if not consume_mfa(conn,row,body.otp.get_secret_value()):
            raise HTTPException(401,"Invalid second factor")
        conn.execute("UPDATE zradius_admin_users SET mfa_secret=NULL,mfa_pending=NULL,mfa_pending_until=NULL,mfa_last_step=-1,mfa_recovery='{}' WHERE id=%s",(row["id"],))
        conn.execute("DELETE FROM zradius_admin_sessions WHERE user_id=%s",(row["id"],))
        audit(conn,"iam.mfa.disabled",row["username"])
    return {"status":"disabled","reauthentication_required":True}


# Machine credentials may only be issued by personal administrators.
class ServiceAccountCreate(BaseModel):
    name: str = Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")

class ServiceTokenCreate(BaseModel):
    label: str = Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    scopes: list[str] = Field(min_length=1,max_length=32)
    lifetime_days: int = Field(default=30,ge=1,le=365)

def personal_admin(principal):
    if principal.get("role")!="admin" or not principal.get("id"):
        raise HTTPException(403,"Personal administrator required")

@app.get("/api/v1/iam/service-scopes")
def service_scopes(principal=Depends(auth)):
    personal_admin(principal)
    return sorted(SERVICE_SCOPES)

@app.get("/api/v1/iam/service-accounts")
def service_accounts(principal=Depends(auth)):
    personal_admin(principal)
    with db() as conn:
        return conn.execute("SELECT id,name,enabled,created_at FROM zradius_service_accounts ORDER BY id DESC LIMIT 500").fetchall()

@app.post("/api/v1/iam/service-accounts",status_code=201)
def create_service_account(body:ServiceAccountCreate,principal=Depends(auth)):
    personal_admin(principal)
    try:
        with db() as conn:
            row=conn.execute("INSERT INTO zradius_service_accounts(name) VALUES (%s) RETURNING id,name,enabled,created_at",(body.name,)).fetchone()
            audit(conn,"iam.service.create",str(row["id"]))
            return row
    except UniqueViolation:
        raise HTTPException(409,"Service account already exists")

@app.put("/api/v1/iam/service-accounts/{account_id}/disable")
def disable_service_account(account_id:int,principal=Depends(auth)):
    personal_admin(principal)
    with db() as conn:
        if not conn.execute("UPDATE zradius_service_accounts SET enabled=false WHERE id=%s RETURNING id",(account_id,)).fetchone():
            raise HTTPException(404,"Service account not found")
        conn.execute("UPDATE zradius_service_tokens SET revoked_at=now() WHERE account_id=%s AND revoked_at IS NULL",(account_id,))
        audit(conn,"iam.service.disable",str(account_id))
        return {"enabled":False}

@app.get("/api/v1/iam/service-accounts/{account_id}/tokens")
def list_service_tokens(account_id:int,principal=Depends(auth)):
    personal_admin(principal)
    with db() as conn:
        return conn.execute("SELECT id,label,scopes,created_at,expires_at,revoked_at FROM zradius_service_tokens WHERE account_id=%s ORDER BY created_at DESC LIMIT 500",(account_id,)).fetchall()

@app.post("/api/v1/iam/service-accounts/{account_id}/tokens",status_code=201)
def create_service_token(account_id:int,body:ServiceTokenCreate,response:Response,principal=Depends(auth)):
    personal_admin(principal)
    scopes=sorted(set(body.scopes))
    if not set(scopes)<=SERVICE_SCOPES:
        raise HTTPException(422,"Unknown service scope")
    token,digest=issue_token()
    with db() as conn:
        account=conn.execute("SELECT enabled FROM zradius_service_accounts WHERE id=%s FOR UPDATE",(account_id,)).fetchone()
        if not account or not account["enabled"]:
            raise HTTPException(409,"Service account unavailable")
        row=conn.execute("""INSERT INTO zradius_service_tokens(account_id,label,token_hash,scopes,expires_at)
            VALUES (%s,%s,%s,%s,now()+%s*interval '1 day') RETURNING id,label,scopes,expires_at""",
            (account_id,body.label,digest,scopes,body.lifetime_days)).fetchone()
        audit(conn,"iam.service.token.issue",str(row["id"]))
    response.headers["Cache-Control"]="no-store"
    return {**row,"token":token}

@app.delete("/api/v1/iam/service-accounts/{account_id}/tokens/{token_id}")
def revoke_service_token(account_id:int,token_id:UUID,principal=Depends(auth)):
    personal_admin(principal)
    with db() as conn:
        if not conn.execute("UPDATE zradius_service_tokens SET revoked_at=COALESCE(revoked_at,now()) WHERE account_id=%s AND id=%s RETURNING id",(account_id,token_id)).fetchone():
            raise HTTPException(404,"Token not found")
        audit(conn,"iam.service.token.revoke",str(token_id))
        return {"revoked":True}


# Device user groups are separate from subscriber RADIUS groups and IAM roles.
@app.get("/api/v1/device-aaa/groups",dependencies=[Depends(auth)])
def device_user_groups():
    with db() as conn:
        return conn.execute("SELECT id,name,description FROM zradius_device_user_groups ORDER BY name").fetchall()

@app.post("/api/v1/device-aaa/groups",status_code=201,dependencies=[Depends(auth)])
def create_device_user_group(body:DeviceRoleCreate):
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_device_user_groups(name,description) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,description",(body.name,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"Device group exists")
        audit(conn,"device.group.create",str(row["id"]))
        return row

@app.get("/api/v1/device-aaa/groups/{group_id}/members",dependencies=[Depends(auth)])
def device_group_members(group_id:int):
    with db() as conn:
        return conn.execute("""SELECT u.id,u.username,u.enabled FROM zradius_device_user_members m
            JOIN zradius_device_users u ON u.id=m.user_id WHERE m.group_id=%s ORDER BY u.username""",(group_id,)).fetchall()

@app.put("/api/v1/device-aaa/groups/{group_id}/members/{user_id}",dependencies=[Depends(auth)])
def add_device_group_member(group_id:int,user_id:int):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_device_user_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
            raise HTTPException(404,"Device group not found")
        if not conn.execute("SELECT id FROM zradius_device_users WHERE id=%s FOR UPDATE",(user_id,)).fetchone():
            raise HTTPException(404,"Device user not found")
        conn.execute("INSERT INTO zradius_device_user_members(group_id,user_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",(group_id,user_id))
        audit(conn,"device.group.member.add",f"{group_id}:{user_id}")
    return {"status":"assigned"}

@app.delete("/api/v1/device-aaa/groups/{group_id}/members/{user_id}",dependencies=[Depends(auth)])
def remove_device_group_member(group_id:int,user_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_device_user_members WHERE group_id=%s AND user_id=%s",(group_id,user_id))
        audit(conn,"device.group.member.remove",f"{group_id}:{user_id}")
    return {"status":"removed"}

@app.get("/api/v1/device-aaa/groups/{group_id}/grants",dependencies=[Depends(auth)])
def device_group_grants(group_id:int):
    with db() as conn:
        return conn.execute("SELECT g.nas_id,n.shortname,g.role,g.filter_id,g.profile_id FROM zradius_device_group_grants g JOIN nas n ON n.id=g.nas_id WHERE group_id=%s ORDER BY n.shortname",(group_id,)).fetchall()

@app.put("/api/v1/device-aaa/groups/{group_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def set_device_group_grant(group_id:int,nas_id:int,body:DeviceGrant):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_device_user_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
            raise HTTPException(404,"Device group not found")
        if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"MikroTik NAS not found")
        if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(nas_id,)).fetchone():
            raise HTTPException(409,"Assign Device AAA service first")
        role,filter_id,profile_id=resolve_device_grant(conn,body)
        conn.execute("""INSERT INTO zradius_device_group_grants(group_id,nas_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(group_id,nas_id) DO UPDATE SET role=excluded.role,filter_id=excluded.filter_id,profile_id=excluded.profile_id""",(group_id,nas_id,role,filter_id,profile_id))
        audit(conn,"device.group.grant.set",f"{group_id}:{nas_id}:{role}")
    return {"role":role,"filter_id":filter_id,"profile_id":profile_id}

@app.delete("/api/v1/device-aaa/groups/{group_id}/grants/{nas_id}",dependencies=[Depends(auth)])
def remove_device_group_grant(group_id:int,nas_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_device_group_grants WHERE group_id=%s AND nas_id=%s",(group_id,nas_id))
        audit(conn,"device.group.grant.remove",f"{group_id}:{nas_id}")
    return {"status":"removed"}

@app.get("/api/v1/device-aaa/users/{user_id}/effective-grants",dependencies=[Depends(auth)])
def effective_device_grants(user_id:int):
    with db() as conn:
        return conn.execute("""SELECT g.nas_id,n.shortname,g.role,g.filter_id,g.source
            FROM zradius_device_effective_grants g JOIN nas n ON n.id=g.nas_id
            WHERE g.user_id=%s ORDER BY n.shortname""",(user_id,)).fetchall()


# NAS selectors never register clients or change shared secrets.
class NasNetwork(BaseModel):
    network:str=Field(min_length=3,max_length=64)

def canonical_network(value):
    import ipaddress
    try:
        network=ipaddress.ip_network(value,strict=True)
        if network.prefixlen==0:
            raise ValueError()
        return str(network)
    except ValueError:
        raise HTTPException(422,"Use canonical IPv4/IPv6 CIDR with nonzero prefix")

@app.get("/api/v1/nas/groups",dependencies=[Depends(auth)])
def nas_groups():
    with db() as conn:
        return conn.execute("SELECT id,name,description FROM zradius_nas_groups ORDER BY name").fetchall()

@app.post("/api/v1/nas/groups",status_code=201,dependencies=[Depends(auth)])
def create_nas_group(body:DeviceRoleCreate):
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_nas_groups(name,description) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,description",(body.name,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"NAS group exists")
        audit(conn,"nas.group.create",str(row["id"]))
        return row

def lock_nas_group(conn,group_id):
    if not conn.execute("SELECT id FROM zradius_nas_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
        raise HTTPException(404,"NAS group not found")

@app.get("/api/v1/nas/groups/{group_id}/members",dependencies=[Depends(auth)])
def nas_group_members(group_id:int):
    with db() as conn:
        return conn.execute("""SELECT n.id,n.shortname,n.nasname,n.type,
            EXISTS(SELECT 1 FROM zradius_nas_group_members m WHERE m.group_id=%s AND m.nas_id=n.id) AS explicit
            FROM zradius_nas_group_effective_members e JOIN nas n ON n.id=e.nas_id
            WHERE e.group_id=%s ORDER BY n.shortname""",(group_id,group_id)).fetchall()

@app.put("/api/v1/nas/groups/{group_id}/members/{nas_id}",dependencies=[Depends(auth)])
def add_nas_group_member(group_id:int,nas_id:int):
    with db() as conn:
        lock_nas_group(conn,group_id)
        if not conn.execute("SELECT id FROM nas WHERE id=%s FOR UPDATE",(nas_id,)).fetchone():
            raise HTTPException(404,"NAS not found")
        conn.execute("INSERT INTO zradius_nas_group_members VALUES (%s,%s) ON CONFLICT DO NOTHING",(group_id,nas_id))
        audit(conn,"nas.group.member.add",f"{group_id}:{nas_id}")
    return {"status":"assigned"}

@app.delete("/api/v1/nas/groups/{group_id}/members/{nas_id}",dependencies=[Depends(auth)])
def remove_nas_group_member(group_id:int,nas_id:int):
    with db() as conn:
        lock_nas_group(conn,group_id)
        conn.execute("DELETE FROM zradius_nas_group_members WHERE group_id=%s AND nas_id=%s",(group_id,nas_id))
        audit(conn,"nas.group.member.remove",f"{group_id}:{nas_id}")
    return {"status":"removed"}

@app.get("/api/v1/nas/groups/{group_id}/networks",dependencies=[Depends(auth)])
def nas_group_networks(group_id:int):
    with db() as conn:
        return conn.execute("SELECT network::text AS network FROM zradius_nas_group_networks WHERE group_id=%s ORDER BY network",(group_id,)).fetchall()

@app.post("/api/v1/nas/groups/{group_id}/networks",status_code=201,dependencies=[Depends(auth)])
def add_nas_group_network(group_id:int,body:NasNetwork):
    network=canonical_network(body.network)
    with db() as conn:
        lock_nas_group(conn,group_id)
        conn.execute("INSERT INTO zradius_nas_group_networks VALUES (%s,%s::cidr) ON CONFLICT DO NOTHING",(group_id,network))
        audit(conn,"nas.group.network.add",f"{group_id}:{network}")
    return {"network":network}

@app.delete("/api/v1/nas/groups/{group_id}/networks/{network:path}",dependencies=[Depends(auth)])
def remove_nas_group_network(group_id:int,network:str):
    network=canonical_network(network)
    with db() as conn:
        lock_nas_group(conn,group_id)
        conn.execute("DELETE FROM zradius_nas_group_networks WHERE group_id=%s AND network=%s::cidr",(group_id,network))
        audit(conn,"nas.group.network.remove",f"{group_id}:{network}")
    return {"status":"removed"}

@app.get("/api/v1/device-aaa/groups/{group_id}/nas-group-grants",dependencies=[Depends(auth)])
def nas_group_grants(group_id:int):
    with db() as conn:
        return conn.execute("""SELECT g.nas_group_id,n.name,g.role,g.filter_id,g.profile_id FROM zradius_device_nas_group_grants g
            JOIN zradius_nas_groups n ON n.id=g.nas_group_id WHERE g.group_id=%s ORDER BY n.name""",(group_id,)).fetchall()

@app.put("/api/v1/device-aaa/groups/{group_id}/nas-group-grants/{nas_group_id}",dependencies=[Depends(auth)])
def set_nas_group_grant(group_id:int,nas_group_id:int,body:DeviceGrant):
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_device_user_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
            raise HTTPException(404,"Device group not found")
        lock_nas_group(conn,nas_group_id)
        role,filter_id,profile_id=resolve_device_grant(conn,body)
        conn.execute("""INSERT INTO zradius_device_nas_group_grants(group_id,nas_group_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT(group_id,nas_group_id) DO UPDATE SET role=excluded.role,filter_id=excluded.filter_id,profile_id=excluded.profile_id""",(group_id,nas_group_id,role,filter_id,profile_id))
        audit(conn,"device.nas.group.grant.set",f"{group_id}:{nas_group_id}:{role}")
    return {"role":role,"filter_id":filter_id,"profile_id":profile_id}

@app.delete("/api/v1/device-aaa/groups/{group_id}/nas-group-grants/{nas_group_id}",dependencies=[Depends(auth)])
def remove_nas_group_grant(group_id:int,nas_group_id:int):
    with db() as conn:
        conn.execute("DELETE FROM zradius_device_nas_group_grants WHERE group_id=%s AND nas_group_id=%s",(group_id,nas_group_id))
        audit(conn,"device.nas.group.grant.remove",f"{group_id}:{nas_group_id}")
    return {"status":"removed"}


class DeviceReplyProfileCreate(DeviceRoleCreate):
    role:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    filter_id:str|None=Field(default=None,min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")

@app.get("/api/v1/device-aaa/reply-profiles",dependencies=[Depends(auth)])
def device_reply_profiles():
    with db() as conn:
        return conn.execute("SELECT id,name,description,role,filter_id FROM zradius_device_reply_profiles ORDER BY name").fetchall()

@app.post("/api/v1/device-aaa/reply-profiles",status_code=201,dependencies=[Depends(auth)])
def create_device_reply_profile(body:DeviceReplyProfileCreate):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_device_role_catalog WHERE name=%s",(body.role,)).fetchone():
            raise HTTPException(422,"Unknown RouterOS role")
        row=conn.execute("""INSERT INTO zradius_device_reply_profiles(name,description,role,filter_id)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,description,role,filter_id""",
            (body.name,body.description,body.role,body.filter_id)).fetchone()
        if not row:
            raise HTTPException(409,"Reply profile already exists")
        audit(conn,"device.reply.profile.create",str(row["id"]))
        return row


# Dedicated L2TP identities; no fallback to subscriber radcheck.
from ppp_vpn import credentials as ppp_credentials, static_address

class PppProfileCreate(BaseModel):
    name:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    pool:str|None=Field(default=None,min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    interim_seconds:int=Field(default=300,ge=60,le=86400)
    description:str=Field(default="",max_length=200)

class L2tpAssignment(BaseModel):
    address_space_id:int|None=Field(default=None,gt=0)
    nas_id:int=Field(gt=0)
    profile_id:int|None=Field(default=None,gt=0)
    group_id:int|None=Field(default=None,gt=0)
    static_ip:str|None=Field(default=None,max_length=15)
    description:str=Field(default="",max_length=200)

class L2tpUserCreate(L2tpAssignment):
    username:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.@-]+$")
    password:SecretStr=Field(min_length=16,max_length=128)

def lock_ppp_policy(conn):
    conn.execute("SELECT pg_advisory_xact_lock(7281192214)")

def validate_l2tp_assignment(conn,body,address):
    if body.address_space_id is not None and not conn.execute('SELECT id FROM zradius_vpn_address_spaces WHERE id=%s',(body.address_space_id,)).fetchone():
        raise HTTPException(404,'VPN address space not found')
    if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(body.nas_id,)).fetchone():
        raise HTTPException(404,"MikroTik NAS not found")
    if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='l2tp'",(body.nas_id,)).fetchone():
        raise HTTPException(409,"Assign L2TP service first")
    group=None
    if body.group_id is not None:
        group=conn.execute("SELECT profile_id FROM zradius_vpn_groups WHERE id=%s",(body.group_id,)).fetchone()
        if not group:
            raise HTTPException(404,"VPN group not found")
    profile_id=body.profile_id or (group["profile_id"] if group else None)
    if profile_id is None:
        raise HTTPException(422,"Choose a profile or VPN group")
    profile=conn.execute("SELECT pool FROM zradius_ppp_profiles WHERE id=%s",(profile_id,)).fetchone()
    if not profile:
        raise HTTPException(404,"PPP profile not found")
    if address is None and not profile["pool"]:
        raise HTTPException(422,"Static IPv4 or named NAS pool required")
    if address is not None:
        if conn.execute("""SELECT 1 FROM zradius_vpn_pools WHERE (nas_id=%s OR address_space_id=%s)
            AND %s::inet BETWEEN first_ip AND last_ip LIMIT 1""",(body.nas_id,body.address_space_id,address)).fetchone():
            raise HTTPException(409,"Static IP overlaps a registered VPN pool")
    else:
        pool=conn.execute("SELECT address_space_id FROM zradius_vpn_pools WHERE nas_id=%s AND name=%s",(body.nas_id,profile["pool"])).fetchone()
        if pool and pool["address_space_id"]!=body.address_space_id:
            raise HTTPException(409,"Registered pool belongs to another address space")

@app.get("/api/v1/ppp/profiles",dependencies=[Depends(auth)])
def ppp_profiles():
    with db() as conn:
        return conn.execute("SELECT id,name,pool,interim_seconds,description FROM zradius_ppp_profiles ORDER BY name").fetchall()

@app.post("/api/v1/ppp/profiles",status_code=201,dependencies=[Depends(auth)])
def create_ppp_profile(body:PppProfileCreate):
    with db() as conn:
        row=conn.execute("""INSERT INTO zradius_ppp_profiles(name,pool,interim_seconds,description)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,pool,interim_seconds,description""",
            (body.name,body.pool,body.interim_seconds,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"PPP profile exists")
        audit(conn,"ppp.profile.create",body.name)
        return row

@app.get("/api/v1/ppp/l2tp/users",dependencies=[Depends(auth)])
def l2tp_users(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT u.id,u.username,u.enabled,u.nas_id,n.shortname AS nas,u.profile_id,u.group_id,u.address_space_id,asp.name AS address_space,g.name AS vpn_group,p.name AS profile,
            CASE WHEN u.profile_id IS NULL THEN 'group' ELSE 'direct' END AS profile_source,
            host(u.static_ip) AS static_ip,p.pool,u.description FROM zradius_l2tp_users u
            JOIN nas n ON n.id=u.nas_id JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            LEFT JOIN zradius_vpn_groups g ON g.id=u.group_id
            LEFT JOIN zradius_vpn_address_spaces asp ON asp.id=u.address_space_id
            ORDER BY u.username LIMIT %s OFFSET %s""",(limit,offset)).fetchall()

@app.post("/api/v1/ppp/l2tp/users",status_code=201,dependencies=[Depends(auth)])
def create_l2tp_user(body:L2tpUserCreate):
    try:
        nt,digest=ppp_credentials(body.password.get_secret_value())
        address=static_address(body.static_ip)
    except ValueError:
        raise HTTPException(422,"Invalid password encoding/length or static IPv4")
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            validate_l2tp_assignment(conn,body,address)
            row=conn.execute("""INSERT INTO zradius_l2tp_users(username,nt_password,password_hash,nas_id,profile_id,group_id,address_space_id,static_ip,description)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::inet,%s) RETURNING id,username,enabled""",
                (body.username,nt,digest,body.nas_id,body.profile_id,body.group_id,body.address_space_id,address,body.description)).fetchone()
            audit(conn,"ppp.l2tp.create",body.username)
            return row
    except UniqueViolation:
        raise HTTPException(409,"L2TP username or static IP in NAS/address space already assigned")

@app.put("/api/v1/ppp/l2tp/users/{user_id}/state",dependencies=[Depends(auth)])
def l2tp_user_state(user_id:int,body:UserState):
    with db() as conn:
        row=conn.execute("UPDATE zradius_l2tp_users SET enabled=%s WHERE id=%s RETURNING id,username,enabled",(body.enabled,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"L2TP user not found")
        audit(conn,"ppp.l2tp.state",row["username"])
        return row

class PppPassword(BaseModel):
    password:SecretStr=Field(min_length=16,max_length=128)

@app.put("/api/v1/ppp/l2tp/users/{user_id}/password",dependencies=[Depends(auth)])
def l2tp_password(user_id:int,body:PppPassword):
    try:
        nt,digest=ppp_credentials(body.password.get_secret_value())
    except ValueError:
        raise HTTPException(422,"Invalid password encoding/length")
    with db() as conn:
        if conn.execute("SELECT 1 FROM zradius_l2tp_users WHERE id=%s AND identity_id IS NOT NULL FOR UPDATE",(user_id,)).fetchone():
            raise HTTPException(409,"Use unified identity password reset")
        row=conn.execute("UPDATE zradius_l2tp_users SET nt_password=%s,password_hash=%s WHERE id=%s RETURNING username",(nt,digest,user_id)).fetchone()
        if not row:
            raise HTTPException(404,"L2TP user not found")
        audit(conn,"ppp.l2tp.password",row["username"])
    return {"status":"updated"}


class VpnGroupCreate(BaseModel):
    name:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    description:str=Field(default="",max_length=200)
    profile_id:int=Field(gt=0)

@app.get("/api/v1/ppp/groups",dependencies=[Depends(auth)])
def vpn_groups():
    with db() as conn:
        return conn.execute("""SELECT g.id,g.name,g.description,g.profile_id,p.name AS profile,
            (SELECT count(*) FROM zradius_l2tp_users u WHERE u.group_id=g.id) AS members
            FROM zradius_vpn_groups g JOIN zradius_ppp_profiles p ON p.id=g.profile_id ORDER BY g.name""").fetchall()

@app.post("/api/v1/ppp/groups",status_code=201,dependencies=[Depends(auth)])
def create_vpn_group(body:VpnGroupCreate):
    with db() as conn:
        lock_ppp_policy(conn)
        if not conn.execute("SELECT id FROM zradius_ppp_profiles WHERE id=%s",(body.profile_id,)).fetchone():
            raise HTTPException(404,"PPP profile not found")
        row=conn.execute("INSERT INTO zradius_vpn_groups(name,description,profile_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id,name",(body.name,body.description,body.profile_id)).fetchone()
        if not row:
            raise HTTPException(409,"VPN group exists")
        audit(conn,"ppp.group.create",body.name)
        return row

@app.put("/api/v1/ppp/groups/{group_id}",dependencies=[Depends(auth)])
def update_vpn_group(group_id:int,body:VpnGroupCreate):
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            profile=conn.execute("SELECT pool FROM zradius_ppp_profiles WHERE id=%s",(body.profile_id,)).fetchone()
            if not profile:
                raise HTTPException(404,"PPP profile not found")
            if not profile["pool"] and conn.execute("SELECT 1 FROM zradius_l2tp_users WHERE group_id=%s AND profile_id IS NULL AND static_ip IS NULL LIMIT 1",(group_id,)).fetchone():
                raise HTTPException(409,"Inherited users require a dynamic pool")
            row=conn.execute("UPDATE zradius_vpn_groups SET name=%s,description=%s,profile_id=%s WHERE id=%s RETURNING id",(body.name,body.description,body.profile_id,group_id)).fetchone()
            if not row:
                raise HTTPException(404,"VPN group not found")
            validate_registered_vpn_pools(conn)
            audit(conn,"ppp.group.update",str(group_id))
            return row
    except UniqueViolation:
        raise HTTPException(409,"VPN group name exists")

@app.get("/api/v1/ppp/groups/{group_id}/members",dependencies=[Depends(auth)])
def vpn_group_members(group_id:int,limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT u.id,u.username,u.enabled,n.shortname AS nas,p.name AS profile,host(u.static_ip) AS static_ip
            FROM zradius_l2tp_users u JOIN nas n ON n.id=u.nas_id
            JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id WHERE u.group_id=%s
            ORDER BY u.username LIMIT %s OFFSET %s""",(group_id,limit,offset)).fetchall()

@app.put("/api/v1/ppp/profiles/{profile_id}",dependencies=[Depends(auth)])
def update_ppp_profile(profile_id:int,body:PppProfileCreate):
    with db() as conn:
        lock_ppp_policy(conn)
        current=conn.execute("SELECT name FROM zradius_ppp_profiles WHERE id=%s",(profile_id,)).fetchone()
        if not current:
            raise HTTPException(404,"PPP profile not found")
        if body.name!=current["name"]:
            raise HTTPException(422,"RouterOS profile name is immutable; create a new profile")
        if not body.pool and conn.execute("""SELECT 1 FROM zradius_l2tp_users u JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            WHERE p.profile_id=%s AND u.static_ip IS NULL LIMIT 1""",(profile_id,)).fetchone():
            raise HTTPException(409,"Assigned users require a dynamic pool")
        conn.execute("UPDATE zradius_ppp_profiles SET pool=%s,interim_seconds=%s,description=%s WHERE id=%s",(body.pool,body.interim_seconds,body.description,profile_id))
        validate_registered_vpn_pools(conn)
        audit(conn,"ppp.profile.update",str(profile_id))
        return {"id":profile_id}

@app.put("/api/v1/ppp/l2tp/users/{user_id}/assignment",dependencies=[Depends(auth)])
def update_l2tp_assignment(user_id:int,body:L2tpAssignment):
    try:
        address=static_address(body.static_ip)
    except ValueError:
        raise HTTPException(422,"Invalid static IPv4")
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            validate_l2tp_assignment(conn,body,address)
            row=conn.execute("""UPDATE zradius_l2tp_users SET nas_id=%s,profile_id=%s,group_id=%s,address_space_id=%s,static_ip=%s::inet,description=%s
                WHERE id=%s RETURNING id,username""",(body.nas_id,body.profile_id,body.group_id,body.address_space_id,address,body.description,user_id)).fetchone()
            if not row:
                raise HTTPException(404,"L2TP user not found")
            audit(conn,"ppp.l2tp.assignment",row["username"])
            return row
    except UniqueViolation:
        raise HTTPException(409,"Static IP in NAS/address space already assigned")


@app.get("/api/v1/ppp/address-spaces",dependencies=[Depends(auth)])
def vpn_address_spaces():
    with db() as conn:
        return conn.execute("""SELECT s.id,s.name,s.description,
            (SELECT count(*) FROM zradius_l2tp_users u WHERE u.address_space_id=s.id) AS members
            FROM zradius_vpn_address_spaces s ORDER BY s.name""").fetchall()

@app.post("/api/v1/ppp/address-spaces",status_code=201,dependencies=[Depends(auth)])
def create_vpn_address_space(body:DeviceRoleCreate):
    with db() as conn:
        lock_ppp_policy(conn)
        row=conn.execute("INSERT INTO zradius_vpn_address_spaces(name,description) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,description",(body.name,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"VPN address space exists")
        audit(conn,"ppp.address_space.create",body.name)
        return row

@app.get("/api/v1/ppp/address-spaces/conflicts",dependencies=[Depends(auth)])
def vpn_address_conflicts():
    # Equal addresses across NAS are candidates for review, not proof of a routing conflict.
    with db() as conn:
        return conn.execute("""SELECT host(static_ip) AS static_ip,count(*) AS assignments,
            array_agg(username ORDER BY username) AS usernames
            FROM zradius_l2tp_users WHERE static_ip IS NOT NULL
            GROUP BY static_ip HAVING count(*)>1 AND bool_or(address_space_id IS NULL)
            ORDER BY static_ip LIMIT 500""").fetchall()


class VpnPoolCreate(BaseModel):
    name:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    nas_id:int=Field(gt=0)
    address_space_id:int=Field(gt=0)
    network:str=Field(max_length=18)
    first_ip:str=Field(max_length=15)
    last_ip:str=Field(max_length=15)

@app.get("/api/v1/ppp/pools",dependencies=[Depends(auth)])
def vpn_pools():
    with db() as conn:
        return conn.execute("""SELECT p.id,p.name,p.nas_id,n.shortname AS nas,s.name AS address_space,p.address_space_id,
            p.network::text AS network,host(p.first_ip) AS first_ip,host(p.last_ip) AS last_ip,
            p.last_ip-p.first_ip+1 AS capacity
            FROM zradius_vpn_pools p JOIN nas n ON n.id=p.nas_id
            JOIN zradius_vpn_address_spaces s ON s.id=p.address_space_id ORDER BY n.shortname,p.name""").fetchall()

@app.post("/api/v1/ppp/pools",status_code=201,dependencies=[Depends(auth)])
def create_vpn_pool(body:VpnPoolCreate):
    from ipam import pool_bounds
    try:
        network,first,last,_=pool_bounds(body.network,body.first_ip,body.last_ip)
        static_address(first)
        static_address(last)
    except ValueError:
        raise HTTPException(422,"Invalid IPv4 pool range")
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            if not conn.execute("SELECT 1 FROM nas n JOIN zradius_nas_services s ON s.nas_id=n.id WHERE n.id=%s AND n.type='mikrotik' AND s.service_code='l2tp'",(body.nas_id,)).fetchone():
                raise HTTPException(409,"Assign L2TP service to MikroTik NAS first")
            if not conn.execute("SELECT 1 FROM zradius_vpn_address_spaces WHERE id=%s",(body.address_space_id,)).fetchone():
                raise HTTPException(404,"VPN address space not found")
            if conn.execute("""SELECT 1 FROM zradius_vpn_pools WHERE (nas_id=%s OR address_space_id=%s)
                AND first_ip<=%s::inet AND last_ip>=%s::inet LIMIT 1""",(body.nas_id,body.address_space_id,last,first)).fetchone():
                raise HTTPException(409,"Overlapping VPN pool range")
            if conn.execute("""SELECT 1 FROM zradius_l2tp_users WHERE (nas_id=%s OR address_space_id=%s)
                AND static_ip BETWEEN %s::inet AND %s::inet LIMIT 1""",(body.nas_id,body.address_space_id,first,last)).fetchone():
                raise HTTPException(409,"Pool overlaps a static VPN assignment")
            if conn.execute("""SELECT 1 FROM zradius_l2tp_users u JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
                WHERE u.nas_id=%s AND p.pool=%s AND u.static_ip IS NULL AND u.address_space_id IS DISTINCT FROM %s LIMIT 1""",
                (body.nas_id,body.name,body.address_space_id)).fetchone():
                raise HTTPException(409,"Existing dynamic users must first be assigned to this address space")
            row=conn.execute("""INSERT INTO zradius_vpn_pools(name,nas_id,address_space_id,network,first_ip,last_ip)
                VALUES (%s,%s,%s,%s::cidr,%s::inet,%s::inet) RETURNING id""",
                (body.name,body.nas_id,body.address_space_id,network,first,last)).fetchone()
            audit(conn,"ppp.pool.create",str(row["id"]))
            return row
    except UniqueViolation:
        raise HTTPException(409,"Pool name already registered on NAS")

@app.delete("/api/v1/ppp/pools/{pool_id}",dependencies=[Depends(auth)])
def delete_vpn_pool(pool_id:int):
    with db() as conn:
        lock_ppp_policy(conn)
        pool=conn.execute("SELECT nas_id,name FROM zradius_vpn_pools WHERE id=%s",(pool_id,)).fetchone()
        if not pool:
            raise HTTPException(404,"VPN pool not found")
        if conn.execute("""SELECT 1 FROM zradius_l2tp_users u JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            WHERE u.nas_id=%s AND p.pool=%s AND u.static_ip IS NULL LIMIT 1""",(pool["nas_id"],pool["name"])).fetchone():
            raise HTTPException(409,"Pool is assigned to VPN users")
        conn.execute("DELETE FROM zradius_vpn_pools WHERE id=%s",(pool_id,))
        audit(conn,"ppp.pool.delete",str(pool_id))
    return {"status":"removed"}

def validate_registered_vpn_pools(conn):
    if conn.execute("""SELECT 1 FROM zradius_l2tp_users u JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
        JOIN zradius_vpn_pools r ON r.nas_id=u.nas_id AND r.name=p.pool
        WHERE u.static_ip IS NULL AND u.address_space_id IS DISTINCT FROM r.address_space_id LIMIT 1""").fetchone():
        raise HTTPException(409,"Registered pool belongs to another address space")


@app.get("/api/v1/ppp/sessions",dependencies=[Depends(auth)])
def vpn_sessions(active:bool=True,username:str|None=None,nas:IPvAnyAddress|None=None,before:int|None=None,limit:int=100):
    if not 1<=limit<=500 or (before is not None and before<1) or (username is not None and not 1<=len(username)<=253):
        raise HTTPException(422,"Invalid session filters")
    clauses=["a.zradius_service='l2tp'"]
    params=[]
    if active:
        clauses.append("a.acctstoptime IS NULL")
    if username is not None:
        clauses.append("a.username=%s")
        params.append(username)
    if nas is not None:
        clauses.append("a.nasipaddress=%s::inet")
        params.append(str(nas))
    if before is not None:
        clauses.append("a.radacctid<%s")
        params.append(before)
    where=" AND ".join(clauses)
    with db() as conn:
        return conn.execute(f"""SELECT a.radacctid,a.username,a.acctsessionid,host(a.nasipaddress) AS nasipaddress,
            host(a.framedipaddress) AS framedipaddress,a.acctstarttime,a.acctupdatetime,a.acctstoptime,
            a.acctsessiontime,a.acctinputoctets,a.acctoutputoctets,a.acctterminatecause,
            CASE WHEN a.acctstoptime IS NOT NULL THEN 'closed'
                 WHEN a.acctupdatetime IS NULL THEN 'unknown'
                 WHEN a.acctupdatetime<now()-make_interval(secs=>GREATEST(900,COALESCE(p.interim_seconds,300)*3)) THEN 'stale'
                 ELSE 'reported_open' END AS state
            FROM radacct a LEFT JOIN nas n ON n.nasname=host(a.nasipaddress)
            LEFT JOIN zradius_l2tp_users u ON u.username=a.username AND u.nas_id=n.id
            LEFT JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            WHERE {where} ORDER BY a.radacctid DESC LIMIT %s""",(*params,limit)).fetchall()

@app.get("/api/v1/ppp/session-summary",dependencies=[Depends(auth)])
def vpn_session_summary():
    with db() as conn:
        return conn.execute("""SELECT count(*) AS recorded,
            count(*) FILTER (WHERE acctstoptime IS NULL) AS reported_open,
            count(*) FILTER (WHERE acctstoptime IS NULL AND (acctupdatetime IS NULL OR acctupdatetime<now()-interval '15 minutes')) AS no_update_15m
            FROM radacct WHERE zradius_service='l2tp'""").fetchone()


@app.post("/api/v1/ppp/sessions/{session_id}/disconnect",dependencies=[Depends(auth)])
def disconnect_vpn_session(session_id:int):
    return session_action(session_id,vpn_only=True)

@app.get("/api/v1/ppp/disconnect-history",dependencies=[Depends(auth)])
def vpn_disconnect_history():
    with db() as conn:
        return conn.execute("""SELECT c.id,c.radacctid,c.status,c.created_at,c.completed_at,
            a.username,host(a.nasipaddress) AS nasipaddress,a.acctsessionid,a.acctstoptime
            FROM zradius_coa_requests c JOIN radacct a ON a.radacctid=c.radacctid
            WHERE a.zradius_service='l2tp' AND c.action='disconnect'
            ORDER BY c.id DESC LIMIT 100""").fetchall()

@app.get("/api/v1/ppp/disconnect-capabilities",dependencies=[Depends(auth)])
def vpn_disconnect_capabilities(principal=Depends(auth)):
    return {"enabled":os.environ.get("COA_ENABLED","false").lower()=="true",
            "permitted":principal["role"] in ("admin","operator")}


# RouterOS PPP import: read-only preview; explicit atomic commit creates disabled users.
from ppp_import import parse_export as parse_ppp_export
from pydantic import ValidationError

class PppImportRequest(BaseModel):
    export:SecretStr=Field(min_length=1,max_length=262144)
    nas_id:int=Field(gt=0)
    address_space_id:int|None=Field(default=None,gt=0)

def plan_ppp_import(conn,body):
    try:
        rows=parse_ppp_export(body.export.get_secret_value())
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    if not conn.execute("SELECT 1 FROM nas n JOIN zradius_nas_services s ON s.nas_id=n.id WHERE n.id=%s AND n.type='mikrotik' AND s.service_code='l2tp'",(body.nas_id,)).fetchone():
        raise HTTPException(409,"Assign L2TP service first")
    if body.address_space_id is not None and not conn.execute("SELECT 1 FROM zradius_vpn_address_spaces WHERE id=%s",(body.address_space_id,)).fetchone():
        raise HTTPException(404,"Address space not found")
    profiles={r["name"]:r for r in conn.execute("SELECT id,name,pool FROM zradius_ppp_profiles").fetchall()}
    seen_profiles=set()
    seen_users=set()
    seen_ips=set()
    for r in rows:
        if r["kind"]!="profile" or r["issues"]:
            continue
        name=r["name"]
        if name in seen_profiles:
            r["issues"].append("Duplicate profile in export")
            continue
        seen_profiles.add(name)
        pool=r["remote_address"]
        # Profile remote-address may be an IP, not a pool; do not guess.
        if pool:
            try:
                import ipaddress
                ipaddress.ip_address(pool)
                r["issues"].append("Fixed remote-address in profile requires manual mapping")
            except ValueError:
                pass
        try:
            PppProfileCreate(name=name,pool=pool,description=r["comment"])
        except ValidationError:
            r["issues"].append("Invalid profile name or pool")
        if name in profiles:
            if profiles[name]["pool"]!=pool:
                r["issues"].append("Existing profile pool differs")
            r["action"]="reuse"
        elif not r["issues"]:
            profiles[name]={"id":None,"name":name,"pool":pool}
            r["action"]="create"
        if r.get("ignored_fields"):
            r["warning"]="Other profile properties remain on RouterOS"
    for r in rows:
        if r["kind"]!="secret" or r["issues"]:
            continue
        name=r["name"]
        if name in seen_users or conn.execute("SELECT 1 FROM zradius_l2tp_users WHERE username=%s",(name,)).fetchone():
            r["issues"].append("Duplicate or existing username")
        seen_users.add(name)
        profile=profiles.get(r["profile"])
        if profile is None:
            r["issues"].append("PPP profile not found")
            continue
        try:
            address=static_address(r["remote_address"])
        except ValueError:
            r["issues"].append("Secret remote-address must be static IPv4 or omitted")
            continue
        r["static_ip"]=address
        if address:
            if address in seen_ips or conn.execute("""SELECT 1 FROM zradius_l2tp_users WHERE (nas_id=%s OR address_space_id=%s)
                AND static_ip=%s::inet""",(body.nas_id,body.address_space_id,address)).fetchone():
                r["issues"].append("Duplicate static IPv4")
            seen_ips.add(address)
            if conn.execute("""SELECT 1 FROM zradius_vpn_pools WHERE (nas_id=%s OR address_space_id=%s)
                AND %s::inet BETWEEN first_ip AND last_ip""",(body.nas_id,body.address_space_id,address)).fetchone():
                r["issues"].append("Static IPv4 overlaps registered pool")
        elif not profile["pool"]:
            r["issues"].append("No static IPv4 or profile pool")
        else:
            pool=conn.execute("SELECT address_space_id FROM zradius_vpn_pools WHERE nas_id=%s AND name=%s",(body.nas_id,profile["pool"])).fetchone()
            if pool and pool["address_space_id"]!=body.address_space_id:
                r["issues"].append("Pool address space differs")
        r["action"]="create_disabled"
    return rows

@app.post("/api/v1/ppp/import/preview",dependencies=[Depends(auth)])
def preview_ppp_import(body:PppImportRequest):
    with db() as conn:
        rows=plan_ppp_import(conn,body)
    return {"rows":rows,"can_apply":not any(r["issues"] for r in rows)}

@app.post("/api/v1/ppp/import/apply",dependencies=[Depends(auth)])
def apply_ppp_import(body:PppImportRequest):
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            rows=plan_ppp_import(conn,body)
            if any(r["issues"] for r in rows):
                raise HTTPException(409,"Import has conflicts; run preview again")
            created_profiles=created_users=0
            for r in rows:
                if r["kind"]=="profile" and r.get("action")=="create":
                    conn.execute("INSERT INTO zradius_ppp_profiles(name,pool,description) VALUES (%s,%s,%s)",(r["name"],r["remote_address"],r["comment"]))
                    created_profiles+=1
            for r in rows:
                if r["kind"]!="secret":
                    continue
                profile=conn.execute("SELECT id FROM zradius_ppp_profiles WHERE name=%s",(r["profile"],)).fetchone()
                assignment=L2tpAssignment(nas_id=body.nas_id,address_space_id=body.address_space_id,profile_id=profile["id"],static_ip=r["static_ip"],description=r["comment"])
                validate_l2tp_assignment(conn,assignment,r["static_ip"])
                # Random unknown credential, never returned. Explicit password reset required before use.
                nt,digest=ppp_credentials(secrets.token_urlsafe(48))
                conn.execute("""INSERT INTO zradius_l2tp_users(username,nt_password,password_hash,nas_id,profile_id,address_space_id,static_ip,description,enabled)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::inet,%s,false)""",(r["name"],nt,digest,body.nas_id,profile["id"],body.address_space_id,r["static_ip"],r["comment"]))
                created_users+=1
            audit(conn,"ppp.import.apply",f"{created_profiles}:{created_users}")
            return {"profiles":created_profiles,"users_disabled":created_users}
    except UniqueViolation:
        raise HTTPException(409,"Concurrent import conflict; run preview again")


from routeros_ppp import generate as generate_routeros_ppp, local_secret_commands

class RouterosPppConfig(BaseModel):
    nas_id:int=Field(gt=0)
    radius_ip:IPvAnyAddress
    api_egress_ip:IPvAnyAddress|None=None
    interim_seconds:int=Field(default=300,ge=60,le=86400)
    disconnect:bool=False
    user_id:int|None=Field(default=None,gt=0)

@app.post("/api/v1/ppp/routeros-config",dependencies=[Depends(auth)])
def routeros_ppp_config(body:RouterosPppConfig,response:Response):
    response.headers["Cache-Control"]="no-store"
    with db() as conn:
        nas=conn.execute("""SELECT n.id,n.nasname,n.shortname FROM nas n JOIN zradius_nas_services s ON s.nas_id=n.id
            WHERE n.id=%s AND n.type='mikrotik' AND s.service_code='l2tp'""",(body.nas_id,)).fetchone()
        if not nas:
            raise HTTPException(409,"Registered MikroTik NAS with L2TP service required")
        try:
            sections=generate_routeros_ppp(str(body.radius_ip),nas["nasname"],str(body.api_egress_ip) if body.api_egress_ip else None,body.interim_seconds,body.disconnect)
        except ValueError:
            raise HTTPException(422,"Valid IPv4 endpoints and API egress IP required")
        user=None
        if body.user_id is not None:
            user=conn.execute("SELECT username,enabled FROM zradius_l2tp_users WHERE id=%s AND nas_id=%s",(body.user_id,body.nas_id)).fetchone()
            if not user:
                raise HTTPException(404,"VPN user not assigned to NAS")
            if not user["enabled"]:
                raise HTTPException(409,"Set password and enable VPN user before generating cutover")
            try:
                commands=local_secret_commands(user["username"])
            except ValueError:
                raise HTTPException(422,"Unsupported local username")
            sections.append({"name":"user_cutover","commands":"\n".join(commands.values())})
        audit(conn,"ppp.routeros.config.generate",str(body.nas_id))
        return {"nas":nas["shortname"],"sections":sections,"warnings":[
            "Review commands individually. All changes are commented out; no router connection is performed.",
            "Replace secret manually using the secure NAS credential source; stored shared secrets are never returned.",
            "PPP AAA and service=ppp affect other PPP protocols. A realm is not proof of L2TP.",
            "Keep local secret until test authorization succeeds using a separate test identity. Record previous settings before cutover.",
            "Disconnect requires actual API egress reachability, COA_ENABLED and COA_ALLOWED_NETWORKS.",
            "PPP profiles and named pools must already exist on RouterOS. No automatic creation or deletion."
        ]}


@app.get("/api/v1/ppp/monitoring",dependencies=[Depends(auth)])
def vpn_monitoring():
    # One read-only snapshot: no synthetic sessions or inferred protocol from username.
    with db() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        inventory=conn.execute("""SELECT
            (SELECT count(*) FROM zradius_l2tp_users) AS users,
            (SELECT count(*) FROM zradius_l2tp_users WHERE enabled) AS enabled_users,
            (SELECT count(*) FROM zradius_l2tp_users WHERE static_ip IS NOT NULL) AS static_users,
            (SELECT count(*) FROM zradius_ppp_profiles) AS profiles,
            (SELECT count(*) FROM zradius_vpn_groups) AS groups,
            (SELECT count(*) FROM zradius_vpn_pools) AS pools,
            (SELECT count(*) FROM zradius_nas_services WHERE service_code='l2tp') AS configured_nas""").fetchone()
        sessions=conn.execute("""WITH classified AS (
            SELECT a.*, CASE WHEN a.acctstoptime IS NOT NULL THEN 'closed'
              WHEN a.acctupdatetime IS NULL THEN 'unknown'
              WHEN a.acctupdatetime<now()-make_interval(secs=>GREATEST(900,COALESCE(p.interim_seconds,300)*3)) THEN 'stale'
              ELSE 'reported_open' END AS state
            FROM radacct a LEFT JOIN nas n ON n.nasname=host(a.nasipaddress)
            LEFT JOIN zradius_l2tp_users u ON u.username=a.username AND u.nas_id=n.id
            LEFT JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            WHERE a.zradius_service='l2tp'
        ) SELECT count(*) AS recorded,
            count(*) FILTER(WHERE state='reported_open') AS reported_open,
            count(*) FILTER(WHERE state='stale') AS stale,
            count(*) FILTER(WHERE state='unknown') AS unknown,
            count(*) FILTER(WHERE state='closed') AS closed,
            count(*) FILTER(WHERE acctstarttime>=now()-interval '24 hours') AS starts_24h,
            count(*) FILTER(WHERE acctstoptime>=now()-interval '24 hours') AS stops_24h,
            COALESCE(sum(acctinputoctets) FILTER(WHERE acctstoptime IS NULL),0)::text AS open_rx_bytes,
            COALESCE(sum(acctoutputoctets) FILTER(WHERE acctstoptime IS NULL),0)::text AS open_tx_bytes,
            max(acctupdatetime) AS last_accounting
            FROM classified""").fetchone()
        by_nas=conn.execute("""SELECT host(a.nasipaddress) AS address,COALESCE(n.shortname,host(a.nasipaddress)) AS name,
            count(*) AS open_records,
            count(*) FILTER(WHERE a.acctupdatetime IS NULL OR a.acctupdatetime<now()-make_interval(secs=>GREATEST(900,COALESCE(p.interim_seconds,300)*3))) AS needs_review,
            COALESCE(sum(a.acctinputoctets),0)::text AS rx_bytes,COALESCE(sum(a.acctoutputoctets),0)::text AS tx_bytes
            FROM radacct a LEFT JOIN nas n ON n.nasname=host(a.nasipaddress)
            LEFT JOIN zradius_l2tp_users u ON u.username=a.username AND u.nas_id=n.id
            LEFT JOIN zradius_l2tp_effective_profiles p ON p.user_id=u.id
            WHERE a.zradius_service='l2tp' AND a.acctstoptime IS NULL
            GROUP BY a.nasipaddress,n.shortname ORDER BY open_records DESC,address LIMIT 500""").fetchall()
        disconnect=conn.execute("""SELECT c.status,count(*) AS count FROM zradius_coa_requests c
            JOIN radacct a ON a.radacctid=c.radacctid
            WHERE a.zradius_service='l2tp' AND c.action='disconnect' AND c.created_at>=now()-interval '24 hours'
            GROUP BY c.status ORDER BY c.status""").fetchall()
        return {"generated_at":conn.execute("SELECT now() AS ts").fetchone()["ts"],
                "inventory":inventory,"sessions":sessions,"by_nas":by_nas,"disconnect_24h":disconnect}


class IdentityDeviceAssignment(DeviceGrant):
    nas_id:int=Field(gt=0)

class IdentityPppoeAssignment(BaseModel):
    nas_id:int=Field(gt=0)
    rate_limit:str=Field(pattern=r"^[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M$")
    pool:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    interim_seconds:int=Field(default=300,ge=60,le=86400)

def set_identity_pppoe(conn,identity_id,assignment):
    if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(assignment.nas_id,)).fetchone():
        raise HTTPException(404,"MikroTik NAS not found")
    if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='pppoe'",(assignment.nas_id,)).fetchone():
        raise HTTPException(409,"Assign PPPoE service to NAS first")
    conn.execute("""INSERT INTO zradius_identity_pppoe(identity_id,nas_id,rate_limit,pool,interim_seconds)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT(identity_id) DO UPDATE SET
        nas_id=excluded.nas_id,rate_limit=excluded.rate_limit,pool=excluded.pool,interim_seconds=excluded.interim_seconds""",
        (identity_id,assignment.nas_id,assignment.rate_limit,assignment.pool,assignment.interim_seconds))

class IdentityHotspotAssignment(BaseModel):
    nas_id:int=Field(gt=0)
    rate_limit:str=Field(pattern=r"^[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M$")
    session_seconds:int=Field(default=3600,ge=60,le=86400)
    idle_seconds:int=Field(default=300,ge=60,le=86400)

def set_identity_hotspot(conn,identity_id,assignment):
    if assignment.idle_seconds>assignment.session_seconds:
        raise HTTPException(422,"Idle timeout exceeds session timeout")
    if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(assignment.nas_id,)).fetchone():
        raise HTTPException(404,"MikroTik NAS not found")
    if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='hotspot'",(assignment.nas_id,)).fetchone():
        raise HTTPException(409,"Assign Hotspot service to NAS first")
    conn.execute("""INSERT INTO zradius_identity_hotspot(identity_id,nas_id,rate_limit,session_seconds,idle_seconds)
        VALUES (%s,%s,%s,%s,%s) ON CONFLICT(identity_id) DO UPDATE SET
        nas_id=excluded.nas_id,rate_limit=excluded.rate_limit,session_seconds=excluded.session_seconds,idle_seconds=excluded.idle_seconds""",
        (identity_id,assignment.nas_id,assignment.rate_limit,assignment.session_seconds,assignment.idle_seconds))

class IdentityCreate(BaseModel):
    username:str=Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9_.-]+$")
    full_name:str=Field(default="",max_length=200)
    department:str=Field(default="",max_length=200)
    password:SecretStr=Field(min_length=16,max_length=128)
    device:IdentityDeviceAssignment|None=None
    l2tp:L2tpAssignment|None=None
    pppoe:IdentityPppoeAssignment|None=None
    hotspot:IdentityHotspotAssignment|None=None

@app.get("/api/v1/identities",dependencies=[Depends(auth)])
def identities(limit:int=100,offset:int=0):
    if not 1<=limit<=500 or offset<0:
        raise HTTPException(422,"Invalid pagination")
    with db() as conn:
        return conn.execute("""SELECT i.id,i.username,i.full_name,i.department,i.enabled,
            d.id AS device_id,d.enabled AS device_enabled,v.id AS l2tp_id,v.enabled AS l2tp_enabled,
            (c.identity_id IS NOT NULL) AS credentials_ready,(c.nt_password IS NOT NULL) AS mschap_ready,
            pp.identity_id IS NOT NULL AS pppoe_assigned,pp.enabled AS pppoe_enabled,
            hs.identity_id IS NOT NULL AS hotspot_assigned,hs.enabled AS hotspot_enabled
            FROM zradius_identities i LEFT JOIN zradius_identity_credentials c ON c.identity_id=i.id LEFT JOIN zradius_device_users d ON d.identity_id=i.id
            LEFT JOIN zradius_l2tp_users v ON v.identity_id=i.id
            LEFT JOIN zradius_identity_pppoe pp ON pp.identity_id=i.id
            LEFT JOIN zradius_identity_hotspot hs ON hs.identity_id=i.id
            ORDER BY i.username LIMIT %s OFFSET %s""",(limit,offset)).fetchall()

@app.post("/api/v1/identities",status_code=201,dependencies=[Depends(auth)])
def create_identity(body:IdentityCreate):
    if __import__('re').fullmatch(r'hs-[a-f0-9]{20}',body.username):
        raise HTTPException(422,'Reserved voucher username')
    try:
        nt,digest=ppp_credentials(body.password.get_secret_value())
        address=static_address(body.l2tp.static_ip) if body.l2tp else None
    except ValueError:
        raise HTTPException(422,"Invalid password or IPv4")
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            # Never merge or adopt a pre-existing service login by name.
            if conn.execute("""SELECT 1 FROM zradius_device_users WHERE username=%s
                UNION ALL SELECT 1 FROM zradius_l2tp_users WHERE username=%s
                UNION ALL SELECT 1 FROM radcheck WHERE username=%s
                UNION ALL SELECT 1 FROM zradius_eap_users WHERE username=%s
                UNION ALL SELECT 1 FROM zradius_admin_users WHERE username=%s
                UNION ALL SELECT 1 FROM zradius_hotspot_vouchers WHERE username=%s LIMIT 1""",(body.username,)*6).fetchone():
                raise HTTPException(409,"Existing service login requires explicit migration")
            row=conn.execute("INSERT INTO zradius_identities(username,full_name,department) VALUES (%s,%s,%s) RETURNING id,username,enabled",(body.username,body.full_name,body.department)).fetchone()
            conn.execute("INSERT INTO zradius_identity_credentials(identity_id,password_hash,nt_password) VALUES (%s,%s,%s)",(row["id"],digest,nt))
            if body.device:
                d=body.device
                if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(d.nas_id,)).fetchone():
                    raise HTTPException(404,"MikroTik NAS not found")
                if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(d.nas_id,)).fetchone():
                    raise HTTPException(409,"Assign Device AAA service first")
                role,filter_id,profile_id=resolve_device_grant(conn,d)
                device=conn.execute("INSERT INTO zradius_device_users(username,identity_id) VALUES (%s,%s) RETURNING id",(body.username,row["id"])).fetchone()
                conn.execute("INSERT INTO zradius_device_grants(user_id,nas_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)",(device["id"],d.nas_id,role,filter_id,profile_id))
            if body.l2tp:
                v=body.l2tp
                validate_l2tp_assignment(conn,v,address)
                conn.execute("""INSERT INTO zradius_l2tp_users(username,nas_id,profile_id,group_id,address_space_id,static_ip,description,identity_id)
                    VALUES (%s,%s,%s,%s,%s,%s::inet,%s,%s)""",(body.username,v.nas_id,v.profile_id,v.group_id,v.address_space_id,address,v.description,row["id"]))
            if body.pppoe:
                set_identity_pppoe(conn,row["id"],body.pppoe)
            if body.hotspot:
                set_identity_hotspot(conn,row['id'],body.hotspot)
            audit(conn,"identity.create",body.username)
            return row
    except UniqueViolation:
        raise HTTPException(409,"Identity, username or static IP already assigned")

@app.put("/api/v1/identities/{identity_id}/state",dependencies=[Depends(auth)])
def identity_state(identity_id:int,body:UserState):
    with db() as conn:
        row=conn.execute("UPDATE zradius_identities SET enabled=%s,updated_at=now() WHERE id=%s RETURNING id,username,enabled",(body.enabled,identity_id)).fetchone()
        if not row:
            raise HTTPException(404,"Identity not found")
        audit(conn,"identity.state",row["username"])
        return row

@app.put("/api/v1/identities/{identity_id}/password",dependencies=[Depends(auth)])
def identity_password(identity_id:int,body:PppPassword):
    try:
        nt,digest=ppp_credentials(body.password.get_secret_value())
    except ValueError:
        raise HTTPException(422,"Invalid password")
    with db() as conn:
        row=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Identity not found")
        conn.execute("""INSERT INTO zradius_identity_credentials(identity_id,password_hash,nt_password) VALUES (%s,%s,%s)
            ON CONFLICT(identity_id) DO UPDATE SET password_hash=excluded.password_hash,nt_password=excluded.nt_password,updated_at=now()""",(identity_id,digest,nt))
        conn.execute("UPDATE zradius_identities SET updated_at=now() WHERE id=%s",(identity_id,))
        audit(conn,"identity.password",row["username"])
    return {"status":"updated"}

class IdentityServices(BaseModel):
    device:bool=False
    l2tp:bool=False
    device_assignment:IdentityDeviceAssignment|None=None
    l2tp_assignment:L2tpAssignment|None=None

@app.put("/api/v1/identities/{identity_id}/services",dependencies=[Depends(auth)])
def identity_services(identity_id:int,body:IdentityServices):
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            row=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
            if not row:
                raise HTTPException(404,"Identity not found")
            creds=conn.execute("SELECT nt_password FROM zradius_identity_credentials WHERE identity_id=%s",(identity_id,)).fetchone()
            if (body.device or body.l2tp) and not creds:
                raise HTTPException(409,"Reset unified password first")
            if body.l2tp and not creds["nt_password"]:
                raise HTTPException(409,"Reset unified password to enable L2TP")
            d=conn.execute("SELECT id FROM zradius_device_users WHERE identity_id=%s",(identity_id,)).fetchone()
            v=conn.execute("SELECT id FROM zradius_l2tp_users WHERE identity_id=%s",(identity_id,)).fetchone()
            if body.device and (not d or body.device_assignment):
                a=body.device_assignment
                if not a:
                    raise HTTPException(422,"Device NAS and role required")
                if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(a.nas_id,)).fetchone():
                    raise HTTPException(404,"MikroTik NAS not found")
                if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(a.nas_id,)).fetchone():
                    raise HTTPException(409,"Assign Device AAA service first")
                role,filter_id,profile_id=resolve_device_grant(conn,a)
                if not d:
                    d=conn.execute("INSERT INTO zradius_device_users(username,identity_id) VALUES (%s,%s) RETURNING id",(row["username"],identity_id)).fetchone()
                conn.execute("""INSERT INTO zradius_device_grants(user_id,nas_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT(user_id,nas_id) DO UPDATE SET role=excluded.role,filter_id=excluded.filter_id,profile_id=excluded.profile_id""",(d["id"],a.nas_id,role,filter_id,profile_id))
            if body.l2tp and (not v or body.l2tp_assignment):
                a=body.l2tp_assignment
                if not a:
                    raise HTTPException(422,"VPN NAS and PPP profile required")
                try:
                    address=static_address(a.static_ip)
                except ValueError:
                    raise HTTPException(422,"Invalid static IPv4")
                validate_l2tp_assignment(conn,a,address)
                if not v:
                    conn.execute("""INSERT INTO zradius_l2tp_users(username,identity_id,nas_id,profile_id,group_id,address_space_id,static_ip,description)
                        VALUES (%s,%s,%s,%s,%s,%s,%s::inet,%s)""",(row["username"],identity_id,a.nas_id,a.profile_id,a.group_id,a.address_space_id,address,a.description))
                else:
                    conn.execute("""UPDATE zradius_l2tp_users SET nas_id=%s,profile_id=%s,group_id=%s,address_space_id=%s,static_ip=%s::inet,description=%s WHERE id=%s""",(a.nas_id,a.profile_id,a.group_id,a.address_space_id,address,a.description,v["id"]))
            conn.execute("UPDATE zradius_device_users SET enabled=%s WHERE identity_id=%s",(body.device,identity_id))
            conn.execute("UPDATE zradius_l2tp_users SET enabled=%s WHERE identity_id=%s",(body.l2tp,identity_id))
            audit(conn,"identity.services",row["username"])
        return {"status":"updated"}
    except UniqueViolation:
        raise HTTPException(409,"Existing independent login or static IP conflict")


@app.get("/api/v1/identities/{identity_id}/assignments",dependencies=[Depends(auth)])
def identity_assignments(identity_id:int):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_identities WHERE id=%s",(identity_id,)).fetchone():
            raise HTTPException(404,"Identity not found")
        direct=conn.execute("""SELECT g.nas_id,g.role,g.filter_id,g.profile_id FROM zradius_device_grants g
            JOIN zradius_device_users u ON u.id=g.user_id WHERE u.identity_id=%s ORDER BY g.nas_id""",(identity_id,)).fetchall()
        inherited=conn.execute("""SELECT g.id,g.name FROM zradius_device_user_groups g JOIN zradius_device_user_members m ON m.group_id=g.id
            JOIN zradius_device_users u ON u.id=m.user_id WHERE u.identity_id=%s ORDER BY g.name""",(identity_id,)).fetchall()
        vpn=conn.execute("""SELECT nas_id,profile_id,group_id,address_space_id,host(static_ip) AS static_ip,description
            FROM zradius_l2tp_users WHERE identity_id=%s""",(identity_id,)).fetchone()
        return {"device_grants":direct,"device_groups":inherited,"l2tp":vpn}

class IdentityGrantSet(BaseModel):
    grants:list[IdentityDeviceAssignment]=Field(max_length=200)
    group_ids:list[int]=Field(default_factory=list,max_length=200)

@app.put("/api/v1/identities/{identity_id}/device-policy",dependencies=[Depends(auth)])
def identity_device_policy(identity_id:int,body:IdentityGrantSet):
    if len({g.nas_id for g in body.grants})!=len(body.grants) or len(set(body.group_ids))!=len(body.group_ids):
        raise HTTPException(422,"Duplicate assignment")
    with db() as conn:
        identity=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not identity:
            raise HTTPException(404,"Identity not found")
        user=conn.execute("SELECT id FROM zradius_device_users WHERE identity_id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not user:
            raise HTTPException(409,"Assign Device AAA service first")
        prepared=[]
        for grant in sorted(body.grants,key=lambda x:x.nas_id):
            if not conn.execute("SELECT id FROM nas WHERE id=%s AND type='mikrotik' FOR UPDATE",(grant.nas_id,)).fetchone():
                raise HTTPException(404,"MikroTik NAS not found")
            if not conn.execute("SELECT 1 FROM zradius_nas_services WHERE nas_id=%s AND service_code='device-aaa'",(grant.nas_id,)).fetchone():
                raise HTTPException(409,"Assign Device AAA service first")
            role,filter_id,profile_id=resolve_device_grant(conn,grant)
            prepared.append((user["id"],grant.nas_id,role,filter_id,profile_id))
        for group_id in sorted(body.group_ids):
            if not conn.execute("SELECT id FROM zradius_device_user_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
                raise HTTPException(404,"Device group not found")
        conn.execute("DELETE FROM zradius_device_grants WHERE user_id=%s",(user["id"],))
        for row in prepared:
            conn.execute("INSERT INTO zradius_device_grants(user_id,nas_id,role,filter_id,profile_id) VALUES (%s,%s,%s,%s,%s)",row)
        conn.execute("DELETE FROM zradius_device_user_members WHERE user_id=%s",(user["id"],))
        for group_id in body.group_ids:
            conn.execute("INSERT INTO zradius_device_user_members(group_id,user_id) VALUES (%s,%s)",(group_id,user["id"]))
        audit(conn,"identity.device.policy",identity["username"])
    return {"status":"updated"}

@app.put("/api/v1/identities/{identity_id}/vpn-policy",dependencies=[Depends(auth)])
def identity_vpn_policy(identity_id:int,body:L2tpAssignment):
    try:
        address=static_address(body.static_ip)
        with db() as conn:
            lock_ppp_policy(conn)
            identity=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
            if not identity:
                raise HTTPException(404,"Identity not found")
            validate_l2tp_assignment(conn,body,address)
            row=conn.execute("""UPDATE zradius_l2tp_users SET nas_id=%s,profile_id=%s,group_id=%s,address_space_id=%s,static_ip=%s::inet,description=%s
                WHERE identity_id=%s RETURNING id""",(body.nas_id,body.profile_id,body.group_id,body.address_space_id,address,body.description,identity_id)).fetchone()
            if not row:
                raise HTTPException(409,"Assign L2TP service first")
            audit(conn,"identity.vpn.policy",identity["username"])
        return {"status":"updated"}
    except ValueError:
        raise HTTPException(422,"Invalid static IPv4")
    except UniqueViolation:
        raise HTTPException(409,"Static IP already assigned")


class IdentityGroupBindings(BaseModel):
    device_group_ids:list[int]=Field(default_factory=list,max_length=200)

class IdentityGroupMembership(BaseModel):
    group_ids:list[int]=Field(default_factory=list,max_length=200)

@app.get("/api/v1/identities/groups",dependencies=[Depends(auth)])
def identity_groups():
    with db() as conn:
        return conn.execute("""SELECT g.id,g.name,g.description,
            ARRAY(SELECT b.device_group_id FROM zradius_identity_group_device_bindings b WHERE b.group_id=g.id ORDER BY b.device_group_id) AS device_group_ids,
            (SELECT count(*) FROM zradius_identity_group_members m WHERE m.group_id=g.id) AS members
            FROM zradius_identity_groups g ORDER BY g.name""").fetchall()

@app.post("/api/v1/identities/groups",status_code=201,dependencies=[Depends(auth)])
def create_identity_group(body:DeviceRoleCreate):
    with db() as conn:
        row=conn.execute("INSERT INTO zradius_identity_groups(name,description) VALUES (%s,%s) ON CONFLICT DO NOTHING RETURNING id,name,description",(body.name,body.description)).fetchone()
        if not row:
            raise HTTPException(409,"Identity group exists")
        audit(conn,"identity.group.create",str(row["id"]))
        return row

@app.put("/api/v1/identities/groups/{group_id}/bindings",dependencies=[Depends(auth)])
def identity_group_bindings(group_id:int,body:IdentityGroupBindings):
    ids=sorted(set(body.device_group_ids))
    with db() as conn:
        if not conn.execute("SELECT id FROM zradius_identity_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
            raise HTTPException(404,"Identity group not found")
        for gid in ids:
            if not conn.execute("SELECT id FROM zradius_device_user_groups WHERE id=%s FOR KEY SHARE",(gid,)).fetchone():
                raise HTTPException(404,"Device group not found")
        conn.execute("DELETE FROM zradius_identity_group_device_bindings WHERE group_id=%s",(group_id,))
        for gid in ids:
            conn.execute("INSERT INTO zradius_identity_group_device_bindings(group_id,device_group_id) VALUES (%s,%s)",(group_id,gid))
        audit(conn,"identity.group.bindings",str(group_id))
    return {"status":"updated"}

@app.get("/api/v1/identities/{identity_id}/groups",dependencies=[Depends(auth)])
def identity_membership(identity_id:int):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_identities WHERE id=%s",(identity_id,)).fetchone():
            raise HTTPException(404,"Identity not found")
        return {"group_ids":[r["group_id"] for r in conn.execute("SELECT group_id FROM zradius_identity_group_members WHERE identity_id=%s ORDER BY group_id",(identity_id,)).fetchall()]}

@app.put("/api/v1/identities/{identity_id}/groups",dependencies=[Depends(auth)])
def set_identity_membership(identity_id:int,body:IdentityGroupMembership):
    ids=sorted(set(body.group_ids))
    with db() as conn:
        row=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Identity not found")
        for gid in ids:
            if not conn.execute("SELECT id FROM zradius_identity_groups WHERE id=%s FOR KEY SHARE",(gid,)).fetchone():
                raise HTTPException(404,"Identity group not found")
        conn.execute("DELETE FROM zradius_identity_group_members WHERE identity_id=%s",(identity_id,))
        for gid in ids:
            conn.execute("INSERT INTO zradius_identity_group_members(group_id,identity_id) VALUES (%s,%s)",(gid,identity_id))
        audit(conn,"identity.groups",row["username"])
    return {"status":"updated"}

@app.get("/api/v1/identities/{identity_id}/effective-device-grants",dependencies=[Depends(auth)])
def identity_effective_device_grants(identity_id:int):
    with db() as conn:
        return conn.execute("""SELECT g.nas_id,n.shortname,g.role,g.filter_id,g.source
            FROM zradius_device_effective_grants g JOIN zradius_device_users u ON u.id=g.user_id
            JOIN zradius_identities i ON i.id=u.identity_id AND i.enabled
            JOIN zradius_identity_credentials c ON c.identity_id=i.id
            JOIN nas n ON n.id=g.nas_id WHERE i.id=%s ORDER BY n.shortname""",(identity_id,)).fetchall()


class IdentityVpnTemplate(BaseModel):
    nas_id:int=Field(gt=0)
    profile_id:int=Field(gt=0)
    address_space_id:int|None=Field(default=None,gt=0)

@app.get("/api/v1/identities/groups/{group_id}/vpn-template",dependencies=[Depends(auth)])
def identity_group_vpn_template(group_id:int):
    with db() as conn:
        return conn.execute("SELECT nas_id,profile_id,address_space_id FROM zradius_identity_group_vpn_templates WHERE group_id=%s",(group_id,)).fetchone()

@app.put("/api/v1/identities/groups/{group_id}/vpn-template",dependencies=[Depends(auth)])
def set_identity_group_vpn_template(group_id:int,body:IdentityVpnTemplate):
    with db() as conn:
        lock_ppp_policy(conn)
        if not conn.execute("SELECT id FROM zradius_identity_groups WHERE id=%s FOR UPDATE",(group_id,)).fetchone():
            raise HTTPException(404,"Identity group not found")
        assignment=L2tpAssignment(**body.model_dump())
        validate_l2tp_assignment(conn,assignment,None)
        conn.execute("""INSERT INTO zradius_identity_group_vpn_templates(group_id,nas_id,profile_id,address_space_id)
            VALUES (%s,%s,%s,%s) ON CONFLICT(group_id) DO UPDATE SET nas_id=excluded.nas_id,profile_id=excluded.profile_id,address_space_id=excluded.address_space_id""",
            (group_id,body.nas_id,body.profile_id,body.address_space_id))
        audit(conn,"identity.group.vpn.template",str(group_id))
    return {"status":"updated"}

@app.delete("/api/v1/identities/groups/{group_id}/vpn-template",dependencies=[Depends(auth)])
def remove_identity_group_vpn_template(group_id:int):
    with db() as conn:
        lock_ppp_policy(conn)
        conn.execute("DELETE FROM zradius_identity_group_vpn_templates WHERE group_id=%s",(group_id,))
        audit(conn,"identity.group.vpn.template.remove",str(group_id))
    return {"status":"removed"}

def resolve_identity_vpn_template(conn,identity_id):
    rows=conn.execute("""SELECT DISTINCT t.nas_id,t.profile_id,t.address_space_id
        FROM zradius_identity_group_members m JOIN zradius_identity_group_vpn_templates t ON t.group_id=m.group_id
        WHERE m.identity_id=%s""",(identity_id,)).fetchall()
    if len(rows)!=1:
        raise HTTPException(409,"No group VPN template or conflicting templates")
    assignment=L2tpAssignment(**rows[0])
    validate_l2tp_assignment(conn,assignment,None)
    return assignment

@app.get("/api/v1/identities/{identity_id}/vpn-template",dependencies=[Depends(auth)])
def preview_identity_vpn_template(identity_id:int):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM zradius_identities WHERE id=%s",(identity_id,)).fetchone():
            raise HTTPException(404,"Identity not found")
        return resolve_identity_vpn_template(conn,identity_id).model_dump()

@app.post("/api/v1/identities/{identity_id}/vpn-template/apply",dependencies=[Depends(auth)])
def apply_identity_vpn_template(identity_id:int):
    try:
        with db() as conn:
            lock_ppp_policy(conn)
            identity=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
            if not identity:
                raise HTTPException(404,"Identity not found")
            if conn.execute("SELECT 1 FROM zradius_l2tp_users WHERE identity_id=%s",(identity_id,)).fetchone():
                raise HTTPException(409,"Existing individual VPN assignment is preserved")
            if not conn.execute("SELECT 1 FROM zradius_identity_credentials WHERE identity_id=%s AND nt_password IS NOT NULL",(identity_id,)).fetchone():
                raise HTTPException(409,"Set unified password first")
            a=resolve_identity_vpn_template(conn,identity_id)
            conn.execute("""INSERT INTO zradius_l2tp_users(username,identity_id,nas_id,profile_id,address_space_id,enabled)
                VALUES (%s,%s,%s,%s,%s,false)""",(identity["username"],identity_id,a.nas_id,a.profile_id,a.address_space_id))
            audit(conn,"identity.vpn.template.apply",identity["username"])
        return {"status":"created_disabled"}
    except UniqueViolation:
        raise HTTPException(409,"Existing VPN login conflict")


class IdentityPppoeUpdate(BaseModel):
    enabled:bool
    assignment:IdentityPppoeAssignment|None=None

@app.get("/api/v1/identities/{identity_id}/pppoe",dependencies=[Depends(auth)])
def identity_pppoe(identity_id:int):
    with db() as conn:
        return conn.execute("SELECT nas_id,rate_limit,pool,interim_seconds,enabled FROM zradius_identity_pppoe WHERE identity_id=%s",(identity_id,)).fetchone()

@app.put("/api/v1/identities/{identity_id}/pppoe",dependencies=[Depends(auth)])
def update_identity_pppoe(identity_id:int,body:IdentityPppoeUpdate):
    with db() as conn:
        row=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Identity not found")
        if body.enabled and not conn.execute("SELECT 1 FROM zradius_identity_credentials WHERE identity_id=%s",(identity_id,)).fetchone():
            raise HTTPException(409,"Set unified password first")
        if body.assignment:
            set_identity_pppoe(conn,identity_id,body.assignment)
        changed=conn.execute("UPDATE zradius_identity_pppoe SET enabled=%s WHERE identity_id=%s RETURNING identity_id",(body.enabled,identity_id)).fetchone()
        if body.enabled and not changed:
            raise HTTPException(422,"PPPoE assignment required")
        audit(conn,"identity.pppoe",row["username"])
    return {"status":"updated"}


class IdentityHotspotUpdate(BaseModel):
    enabled:bool
    assignment:IdentityHotspotAssignment|None=None

@app.get("/api/v1/identities/{identity_id}/hotspot",dependencies=[Depends(auth)])
def identity_hotspot(identity_id:int):
    with db() as conn:
        return conn.execute("SELECT nas_id,rate_limit,session_seconds,idle_seconds,enabled FROM zradius_identity_hotspot WHERE identity_id=%s",(identity_id,)).fetchone()

@app.put("/api/v1/identities/{identity_id}/hotspot",dependencies=[Depends(auth)])
def update_identity_hotspot(identity_id:int,body:IdentityHotspotUpdate):
    with db() as conn:
        row=conn.execute("SELECT username FROM zradius_identities WHERE id=%s FOR UPDATE",(identity_id,)).fetchone()
        if not row:
            raise HTTPException(404,"Identity not found")
        if body.enabled:
            if __import__('re').fullmatch(r'hs-[a-f0-9]{20}',row["username"]):
                raise HTTPException(422,"Reserved voucher username")
            if not conn.execute("SELECT 1 FROM zradius_identity_credentials WHERE identity_id=%s",(identity_id,)).fetchone():
                raise HTTPException(409,"Set unified password first")
        if body.assignment:
            set_identity_hotspot(conn,identity_id,body.assignment)
        changed=conn.execute("UPDATE zradius_identity_hotspot SET enabled=%s WHERE identity_id=%s RETURNING identity_id",(body.enabled,identity_id)).fetchone()
        if body.enabled and not changed:
            raise HTTPException(422,"Hotspot assignment required")
        audit(conn,"identity.hotspot",row["username"])
    return {"status":"updated"}
