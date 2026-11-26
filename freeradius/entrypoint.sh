#!/bin/sh
set -eu
case "${RADIUS_TEST_SECRET:-}" in
  ""|replace_with*|*[!a-zA-Z0-9]*) echo "Set a random alphanumeric RADIUS_TEST_SECRET" >&2; exit 1;;
esac
[ "${#RADIUS_TEST_SECRET}" -ge 32 ] || exit 1
cat > /etc/freeradius/3.0/clients.conf <<EOF
client localhost {
 ipaddr = 127.0.0.1
 secret = "$RADIUS_TEST_SECRET"
 require_message_authenticator = yes
}
EOF
export PGPASSWORD="$RADIUS_DB_PASSWORD"
until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.radcheck') IS NOT NULL AND to_regclass('public.radacct') IS NOT NULL AND to_regclass('public.nas') IS NOT NULL AND to_regclass('public.nasreload') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
if [ "${RADIUS_ENABLE_NAS:-false}" = true ]; then
  umask 027
  psql -h postgres -U radius -d radius -v ON_ERROR_STOP=1 -At <<'SQL' > /etc/freeradius/3.0/zradius-clients.conf
SELECT format(E'client managed_%s {\n ipaddr = %s\n secret = "%s"\n require_message_authenticator = yes\n}', id, host(nasname::inet), secret)
FROM nas
WHERE nasname !~ '/' AND secret ~ '^[A-Za-z0-9]{32,128}$'
AND NOT (nasname::inet <<= '127.0.0.0/8'::inet OR nasname::inet = '::1'::inet)
ORDER BY id;
SQL
  chmod 640 /etc/freeradius/3.0/zradius-clients.conf
  chgrp freerad /etc/freeradius/3.0/zradius-clients.conf
  printf '\n$INCLUDE /etc/freeradius/3.0/zradius-clients.conf\n' >> /etc/freeradius/3.0/clients.conf
fi
if [ "${RADIUS_ENABLE_SQLIPPOOL:-false}" = true ]; then
  until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.radippool') IS NOT NULL AND to_regclass('public.zradius_radius_pool_active') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
  ln -sf ../mods-available/sqlippool /etc/freeradius/3.0/mods-enabled/sqlippool
  # Always start from the immutable template to avoid duplicate sections on restart.
  cp /etc/freeradius/3.0/sites-available/zradius /etc/freeradius/3.0/sites-available/zradius-pool-runtime
  sed -i '$d' /etc/freeradius/3.0/sites-available/zradius-pool-runtime
  cat /etc/freeradius/3.0/zradius-pool-postauth >> /etc/freeradius/3.0/sites-available/zradius-pool-runtime
  printf '\n}\n' >> /etc/freeradius/3.0/sites-available/zradius-pool-runtime
  ln -sf ../sites-available/zradius-pool-runtime /etc/freeradius/3.0/sites-enabled/zradius
else
  rm -f /etc/freeradius/3.0/mods-enabled/sqlippool
  ln -sf ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius
fi
if [ "${RADIUS_ENABLE_IPOE:-false}" = true ]; then
  until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.zradius_ipoe_bindings') IS NOT NULL AND to_regclass('public.zradius_nas_services') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
  ln -sf ../sites-available/zradius-ipoe /etc/freeradius/3.0/sites-enabled/zradius-ipoe
else
  rm -f /etc/freeradius/3.0/sites-enabled/zradius-ipoe
fi
if [ "${RADIUS_ENABLE_HOTSPOT:-false}" = true ]; then
  until [ "$(psql -h postgres -U radius -d radius -Atqc "SELECT to_regclass('public.zradius_hotspot_vouchers') IS NOT NULL" 2>/dev/null || true)" = t ]; do sleep 2; done
  ln -sf ../sites-available/zradius-hotspot /etc/freeradius/3.0/sites-enabled/zradius-hotspot
else
  rm -f /etc/freeradius/3.0/sites-enabled/zradius-hotspot
fi
unset PGPASSWORD
freeradius -C
exec freeradius -f -l stdout
