#!/bin/sh
set -eu
case "${RADIUS_TEST_SECRET:-}" in
  ""|replace_with*|*[!a-zA-Z0-9]*) echo "Set a random alphanumeric RADIUS_TEST_SECRET" >&2; exit 1;;
esac
[ "${#RADIUS_TEST_SECRET}" -ge 32 ] || exit 1
# Only local container clients are trusted; external NAS configuration is a separate milestone.
cat > /etc/freeradius/3.0/clients.conf <<EOF
client localhost {
 ipaddr = 127.0.0.1
 secret = "$RADIUS_TEST_SECRET"
 require_message_authenticator = yes
}
EOF
# Wait for schema bootstrap, without depending on API availability afterwards.
export PGPASSWORD="$RADIUS_DB_PASSWORD"
until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.radcheck') IS NOT NULL AND to_regclass('public.radacct') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
unset PGPASSWORD
freeradius -XC
exec freeradius -f
