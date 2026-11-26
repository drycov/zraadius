"""Create the initial admin interactively; never use command-line passwords."""
import getpass
import re
import psycopg
from iam import hash_password

def main():
    username=input("Administrator username: ").strip()
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}",username):
        raise SystemExit("Invalid username")
    password=getpass.getpass("Password (16-128 characters): ")
    if password!=getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    digest=hash_password(password)
    with psycopg.connect(connect_timeout=5) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(7281192202)")
        if conn.execute("SELECT 1 FROM zradius_admin_users WHERE role='admin' AND enabled").fetchone():
            raise SystemExit("Active administrator already exists; use IAM API")
        conn.execute("INSERT INTO zradius_admin_users(username,password_hash,role) VALUES (%s,%s,'admin')",(username,digest))
    print("Administrator created")
if __name__=="__main__":
    main()
