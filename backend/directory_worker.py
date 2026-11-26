"""Opt-in periodic metadata reconciliation; never grants or revokes access."""
import logging
import os
import time
from main import db, reconcile_directory_profile, audit, actor_context
from schema_version import require_schema

log = logging.getLogger("directory-worker")


def run_once():
    # Session advisory lock spans LDAP requests and separate per-profile transactions.
    with db() as lock:
        lock.autocommit = True
        if not lock.execute("SELECT pg_try_advisory_lock(7281192266) AS acquired").fetchone()["acquired"]:
            return
        try:
            profiles = lock.execute("SELECT id FROM zradius_directory_profiles WHERE enabled ORDER BY id").fetchall()
            for profile in profiles:
                pid = profile["id"]
                token = actor_context.set("directory-worker")
                try:
                    result = reconcile_directory_profile(pid, False)
                    log.info("Directory profile %s synchronized: %s changes", pid, result["changed"])
                except Exception:
                    # Do not log LDAP exception details, which may contain directory data.
                    log.warning("Directory profile %s synchronization failed", pid)
                    with db() as conn:
                        audit(conn, "directory.bulk.failed", str(pid))
                finally:
                    actor_context.reset(token)
        finally:
            lock.execute("SELECT pg_advisory_unlock(7281192266)")


def main():
    logging.basicConfig(level=logging.INFO)
    interval = int(os.getenv("ZRADIUS_DIRECTORY_SYNC_INTERVAL", "900"))
    if not 60 <= interval <= 86400:
        raise RuntimeError("Directory sync interval must be 60..86400 seconds")
    with db() as conn:
        require_schema(conn)
    while True:
        try:
            run_once()
        except Exception:
            log.warning("Directory worker cycle failed")
        time.sleep(interval)


if __name__ == "__main__":
    main()
