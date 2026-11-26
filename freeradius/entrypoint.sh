#!/bin/sh
set -eu
case "${RADIUS_TEST_SECRET:-}" in
  ""|replace_with*|*[!a-zA-Z0-9]*) echo "Set a random alphanumeric RADIUS_TEST_SECRET" >&2; exit 1;;
esac
[ "${#RADIUS_TEST_SECRET}" -ge 32 ] || exit 1
# Static loopback client; managed clients are generated from the NAS registry.
cat > /etc/freeradius/3.0/clients.conf <<EOF
client localhost {
 ipaddr = 127.0.0.1
 secret = "$RADIUS_TEST_SECRET"
 require_message_authenticator = yes
}
EOF
# Wait for schema bootstrap, without depending on API availability afterwards.
export PGPASSWORD="$RADIUS_DB_PASSWORD"
until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.radcheck') IS NOT NULL AND to_regclass('public.radacct') IS NOT NULL AND to_regclass('public.nas') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
# Generate an explicit client config with mandatory Message-Authenticator.
# Validate every row in SQL; reject unsafe values rather than interpolating them.
if [ "${RADIUS_ENABLE_NAS:-false}" = true ]; then
  psql -h postgres -U radius -d radius -v ON_ERROR_STOP=1 -Atqc "SELECT 'client managed_' || id || E' {\n ipaddr = ' || host(nasname::inet) || E'\n secret = \"' || secret || E'\"\n require_message_authenticator = yes\n}' FROM nas WHERE nasname !~ '/' AND secret ~ '^[A-Za-z0-9]{32,128}
exec freeradius -f
 AND NOT (nasname::inet <<= '127.0.0.0/8'::inet OR nasname::inet = '::1'::inet) ORDER BY id" > /etc/freeradius/3.0/zradius-clients.conf
  chmod 640 /etc/freeradius/3.0/zradius-clients.conf
  chgrp freerad /etc/freeradius/3.0/zradius-clients.conf
  printf '\n$INCLUDE zradius-clients.conf\n' >> /etc/freeradius/3.0/clients.conf
fi
unset PGPASSWORD
freeradius -XC
exec freeradius -f
