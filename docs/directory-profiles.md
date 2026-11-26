# Directory profiles (66.0.2)

Migration 0028 adds API-only directory profiles. Personal administrators create/update/list/delete disabled profiles and test LDAPS bind plus base search. Password is encrypted with AES-256-GCM using ZRADIUS_SECRET_KEY and AAD bound to profile ID, host and bind DN. Update requires a fresh password. API never returns plaintext or ciphertext. No RADIUS role grant.

Set ZRADIUS_LDAP_ENABLED=true and ZRADIUS_LDAP_ALLOWED_HOSTS=dc01.corp.local,dc02.corp.local in .env; Compose passes them to API. For private PKI mount the CA read-only into the API and set ZRADIUS_LDAP_CA_FILE to the container path. Do not permit untrusted DNS changes; restrict API egress to approved DCs on TCP 636. TLS verification mandatory. Profiles disabled by default; disabled profiles can be tested. Legacy environment preview remains available, subject to allowlist. No automatic failover, import or authentication. Live tests/build pending.
