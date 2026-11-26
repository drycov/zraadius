#!/usr/bin/env python3
"""Probe the actual RADIUS auth listener instead of relying on a PID file."""
import subprocess
import time
for attempt in range(60):
    try:
        result=subprocess.run(["docker","compose","exec","-T","radius","sh","-ec",
            'printf "User-Name = zradius-readiness-invalid\\nUser-Password = invalid\\nMessage-Authenticator = 0x00\\n" | radclient -r 1 -t 2 127.0.0.1:1812 auth "$RADIUS_TEST_SECRET"'],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=8)
        if "Access-Reject" in result.stdout:
            print("RADIUS authentication listener ready")
            break
    except subprocess.TimeoutExpired:
        pass
    time.sleep(2)
else:
    raise SystemExit("RADIUS readiness timeout")
