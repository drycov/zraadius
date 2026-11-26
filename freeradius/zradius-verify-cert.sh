#!/bin/sh
# Called only by OpenSSL-backed EAP-TLS verifier after chain validation.
set -eu
[ "$#" -eq 2 ] || exit 1
case "$1" in /run/zradius-client-certs/*) ;; *) exit 1;; esac
case "$2" in ""|*[!0-9.]*) exit 1;; esac
[ -f "$1" ] || exit 1
fingerprint=$(openssl x509 -in "$1" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':' | tr 'A-F' 'a-f')
case "$fingerprint" in ""|*[!0-9a-f]*) exit 1;; esac
[ "${#fingerprint}" -eq 64 ] || exit 1
export PGPASSWORD="$RADIUS_DB_PASSWORD"
export PGCONNECT_TIMEOUT=3
# Input is restricted above; psql variables are quoted as SQL literals.
result=$(psql -X -h postgres -U radius -d radius -v ON_ERROR_STOP=1 -At -v fp="$fingerprint" -v source="$2" <<'SQL'
SELECT count(*) FROM zradius_pki_certificates c
JOIN zradius_pki_grants g ON g.fingerprint=c.fingerprint
JOIN nas n ON n.id=g.nas_id
WHERE c.fingerprint=:'fp' AND n.nasname=:'source'
AND c.purpose='client' AND c.revoked_at IS NULL
AND c.not_before<=now() AND c.not_after>now()
AND EXISTS (SELECT 1 FROM zradius_nas_services s WHERE s.nas_id=n.id AND s.service_code IN ('dot1x','wpa-enterprise'));
SQL
)
[ "$result" = 1 ]
