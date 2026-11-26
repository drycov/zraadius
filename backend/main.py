import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, SecretStr

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
        return conn.execute("SELECT DISTINCT username FROM radcheck ORDER BY username LIMIT %s OFFSET %s",(limit,offset)).fetchall()

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
