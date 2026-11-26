# EAP-TLS (experimental)

Requires EAP overlay as well:

```bash
docker compose -f compose.yaml -f compose.eap.yaml -f compose.eap-tls.yaml up -d --force-recreate radius
```

Sets `RADIUS_ENABLE_EAP_TLS=true`. Entrypoint refuses TLS without EAP.

When enabled: waits for PKI tables, prepares `/run/zradius-client-certs`, builds EAP-TLS runtime mod, enables `zradius-check-eap-tls` site.

Client certificates via public PKI inventory API (no private keys). More experimental than PEAP.
