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
