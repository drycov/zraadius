# ZRADIUS

Development alpha. Copy .env.example to .env and replace the three secrets with independent random hex values. Run docker compose up --build -d; console http://localhost:8080, API docs /docs.

React management console, users/groups, MikroTik profiles, NAS inventory, accounting and audit. Optional NAS runtime snapshot on startup and RFC 5176 Disconnect/CoA rate API with explicit network allowlist. Disabled by default. See docs/nas-runtime.md. Not production-ready; validate Docker startup and AAA behavior first.

## Unified RADIUS endpoint
All current runtime services share UDP 1812/1813. Managed MikroTik NAS must send an explicit per-service Mikrotik-Realm and have that service assigned in ZRADIUS. Old service overlays are compatibility no-ops. See docs/unified-radius.md. EAP and proxy remain disabled pending implementation. Local loopback smoke tests retain PPP compatibility; no remote fallback.
