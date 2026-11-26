#!/bin/sh
set -eu
# Run from repository root. Requires a running development stack.
docker compose exec -T radius sh -eu -c '
  printf "User-Name = zradius-smoke\\nUser-Password = wrong-password\\nMessage-Authenticator = 0x00\\n" |
  radclient -x -r 1 -t 3 127.0.0.1:1812 auth "$RADIUS_TEST_SECRET" 2>&1 | grep "Received Access-Reject"
'
