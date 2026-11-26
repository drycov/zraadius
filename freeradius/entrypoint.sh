#!/bin/sh
set -eu
# Reset package defaults on every startup, including reused containers.
conf=/etc/freeradius/3.0
umask 027
rm -f "$conf/mods-enabled/eap" "$conf/mods-enabled/sqlippool"
rm -f "$conf/sites-enabled/"*
ln -s ../sites-available/zradius "$conf/sites-enabled/zradius"
ln -sf ../mods-available/sql "$conf/mods-enabled/sql"
grep -Eq '^[[:space:]]*client_table[[:space:]]*=[[:space:]]*"nas"' "$conf/mods-available/sql" || { echo 'ZRADIUS: SQL client_table missing; rebuild image' >&2; exit 1; }
for flag in RADIUS_ENABLE_NAS RADIUS_ENABLE_SQLIPPOOL RADIUS_ENABLE_EAP RADIUS_ENABLE_EAP_TLS RADIUS_ENABLE_PROXY; do
  value=$(printenv "$flag" || true)
  case "$value" in true|false|"") ;; *) echo "Invalid boolean: $flag" >&2; exit 1;; esac
done
if [ "${RADIUS_ENABLE_EAP_TLS:-false}" = true ] && [ "${RADIUS_ENABLE_EAP:-false}" != true ]; then
  echo 'ZRADIUS: EAP-TLS requires EAP' >&2; exit 1
fi
printf 'ZRADIUS startup: NAS=%s SQLIPPOOL=%s EAP=%s EAP_TLS=%s PROXY=%s\n' "${RADIUS_ENABLE_NAS:-false}" "${RADIUS_ENABLE_SQLIPPOOL:-false}" "${RADIUS_ENABLE_EAP:-false}" "${RADIUS_ENABLE_EAP_TLS:-false}" "${RADIUS_ENABLE_PROXY:-false}"
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
export PGCONNECT_TIMEOUT=3
wait_schema() {
  attempt=0
  while :; do
    if result=$(psql -X -w -h postgres -U zradius_runtime -d radius -v ON_ERROR_STOP=1 -Atqc "$1" 2>&1); then
      if [ "$result" = t ]; then return 0; fi
      reason='required schema or privileges missing'
    else
      reason="$result"
    fi
    attempt=$((attempt + 1))
    if [ "$attempt" -eq 1 ] || [ "$((attempt % 10))" -eq 0 ]; then
      printf 'ZRADIUS database readiness (%s/60): %s\n' "$attempt" "$reason" >&2
    fi
    if [ "$attempt" -ge 60 ]; then
      echo 'Database schema readiness timeout; run docker compose run --rm migrate and verify runtime credentials' >&2
      exit 1
    fi
    sleep 2
  done
}
wait_schema "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='radacct' AND column_name='zradius_service')"
wait_schema "SELECT NOT EXISTS (SELECT 1 FROM unnest(ARRAY['radcheck','radreply','radgroupcheck','radgroupreply','radusergroup','radacct','radpostauth','nas','nasreload','zradius_device_auth_log','zradius_hotspot_vouchers','zradius_ipoe_bindings','zradius_nas_services','zradius_device_users','zradius_device_grants','zradius_device_user_members','zradius_device_group_grants','zradius_device_effective_grants','zradius_nas_group_members','zradius_nas_group_networks','zradius_device_nas_group_grants','zradius_nas_group_effective_members','zradius_ppp_profiles','zradius_l2tp_users','zradius_vpn_groups','zradius_l2tp_effective_profiles','zradius_identities','zradius_identity_credentials']) AS t(name) WHERE to_regclass('public.'||name) IS NULL OR NOT COALESCE(has_table_privilege(current_user,to_regclass('public.'||name),'SELECT'),false))"

if [ "${RADIUS_ENABLE_NAS:-false}" = true ]; then
  umask 027
  python3 /opt/zradius/render_secrets.py nas > /etc/freeradius/3.0/zradius-clients.conf
  chmod 640 /etc/freeradius/3.0/zradius-clients.conf
  chgrp freerad /etc/freeradius/3.0/zradius-clients.conf
  printf '\n$INCLUDE /etc/freeradius/3.0/zradius-clients.conf\n' >> /etc/freeradius/3.0/clients.conf
fi
if [ "${RADIUS_ENABLE_SQLIPPOOL:-false}" = true ]; then
  /usr/local/bin/zradius-prepare-sqlippool
  wait_schema "SELECT to_regclass('public.radippool') IS NOT NULL AND to_regclass('public.zradius_radius_pool_active') IS NOT NULL"
  ln -sf ../mods-available/sqlippool /etc/freeradius/3.0/mods-enabled/sqlippool
  sed '/# ZRADIUS_POOL_POLICY/r /etc/freeradius/3.0/zradius-pool-policy' /etc/freeradius/3.0/sites-available/zradius > /etc/freeradius/3.0/sites-available/zradius-pool-runtime
  ln -sf ../sites-available/zradius-pool-runtime /etc/freeradius/3.0/sites-enabled/zradius
else
  rm -f /etc/freeradius/3.0/mods-enabled/sqlippool
  ln -sf ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius
fi
rm -f /etc/freeradius/3.0/sites-enabled/zradius-ipoe /etc/freeradius/3.0/sites-enabled/zradius-hotspot /etc/freeradius/3.0/sites-enabled/zradius-device-aaa
if [ "${RADIUS_ENABLE_EAP:-false}" = true ]; then
  for f in server.key server.pem ca.pem; do
    [ -r "/run/zradius-pki/$f" ] || { echo "Missing EAP PKI file: $f" >&2; exit 1; }
  done
  wait_schema "SELECT to_regclass('public.zradius_eap_users') IS NOT NULL AND to_regclass('public.zradius_eap_grants') IS NOT NULL"
  if [ "${RADIUS_ENABLE_EAP_TLS:-false}" = true ]; then
    wait_schema "SELECT to_regclass('public.zradius_pki_certificates') IS NOT NULL AND to_regclass('public.zradius_pki_grants') IS NOT NULL"
    install -d -m 0700 -o freerad -g freerad /run/zradius-client-certs
    sed '/# ZRADIUS_TLS_CONFIG/r /etc/freeradius/3.0/zradius-tls-config' /etc/freeradius/3.0/mods-available/zradius-eap > /etc/freeradius/3.0/mods-available/zradius-eap-tls-runtime
    ln -sf ../mods-available/zradius-eap-tls-runtime /etc/freeradius/3.0/mods-enabled/eap
    ln -sf ../sites-available/zradius-check-eap-tls /etc/freeradius/3.0/sites-enabled/zradius-check-eap-tls
  else
    rm -f /etc/freeradius/3.0/sites-enabled/zradius-check-eap-tls
    ln -sf ../mods-available/zradius-eap /etc/freeradius/3.0/mods-enabled/eap
  fi
  ln -sf ../sites-available/zradius-inner-tunnel /etc/freeradius/3.0/sites-enabled/zradius-inner-tunnel
  cp -L /etc/freeradius/3.0/sites-enabled/zradius /tmp/zradius-eap-site
  sed '/# ZRADIUS_EAP_AUTHORIZE/r /etc/freeradius/3.0/zradius-eap-authorize' /tmp/zradius-eap-site | sed '/# ZRADIUS_EAP_AUTHENTICATE/a\  Auth-Type EAP {\n   eap\n  }' > /etc/freeradius/3.0/sites-available/zradius-eap-runtime
  ln -sf ../sites-available/zradius-eap-runtime /etc/freeradius/3.0/sites-enabled/zradius
else
  rm -f /etc/freeradius/3.0/mods-enabled/eap /etc/freeradius/3.0/sites-enabled/zradius-inner-tunnel /etc/freeradius/3.0/sites-enabled/zradius-check-eap-tls
fi
# Replace packaged sample proxy realms even when disabled.
printf 'proxy server {\n default_fallback = no\n}\n' > /etc/freeradius/3.0/proxy.conf
if [ "${RADIUS_ENABLE_PROXY:-false}" = true ]; then
  wait_schema "SELECT to_regclass('public.zradius_proxy_realms') IS NOT NULL AND to_regclass('public.zradius_proxy_grants') IS NOT NULL"
  umask 077
  python3 /opt/zradius/render_secrets.py proxy >> /etc/freeradius/3.0/proxy.conf
  chgrp freerad /etc/freeradius/3.0/proxy.conf
  chmod 640 /etc/freeradius/3.0/proxy.conf
  cp -L /etc/freeradius/3.0/sites-enabled/zradius /tmp/zradius-proxy-site
  sed '/# ZRADIUS_PROXY_AUTHORIZE/r /etc/freeradius/3.0/zradius-proxy-policy' /tmp/zradius-proxy-site | sed '/# ZRADIUS_PROXY_ACCOUNTING/r /etc/freeradius/3.0/zradius-proxy-accounting' > /etc/freeradius/3.0/sites-available/zradius-proxy-runtime
  ln -sf ../sites-available/zradius-proxy-runtime /etc/freeradius/3.0/sites-enabled/zradius
fi
# Verify the actual linked configuration before invoking FreeRADIUS.
if [ "${RADIUS_ENABLE_EAP:-false}" = true ]; then
  test -L "$conf/mods-enabled/eap"
  grep -Eq '^[[:space:]]*Auth-Type EAP[[:space:]]*\{' "$conf/sites-enabled/zradius" || { echo 'ZRADIUS: missing outer Auth-Type EAP' >&2; exit 1; }
  test -L "$conf/sites-enabled/zradius-inner-tunnel"
else
  test ! -e "$conf/mods-enabled/eap"
  test ! -L "$conf/mods-enabled/eap"
fi
chgrp freerad "$conf/clients.conf" "$conf/proxy.conf"
chmod 640 "$conf/clients.conf" "$conf/proxy.conf"
for f in "$conf/sites-available"/zradius-*-runtime "$conf/mods-available"/zradius-eap-tls-runtime; do
  [ -f "$f" ] || continue
  chgrp freerad "$f"
  chmod 640 "$f"
done
unset PGPASSWORD ZRADIUS_SECRET_KEY
echo 'ZRADIUS: validating configuration'
# Explicit diagnostic mode only: verbose configuration output can contain secrets.
if [ "${1:-}" = --check-debug ]; then exec freeradius -XC; fi
if freeradius -C -l stdout; then
  echo 'ZRADIUS: configuration validation complete'
else
  status=$?
  printf 'ZRADIUS: configuration validation failed (exit=%s)\n' "$status" >&2
  echo 'For a local configuration trace, run the radius service with --check-debug; redact all secrets before sharing output.' >&2
  exit "$status"
fi
if [ "${1:-}" = --check-config ]; then exit 0; fi
exec freeradius -f -l stdout
