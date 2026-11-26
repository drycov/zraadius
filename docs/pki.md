# PKI inventory

`backend/pki.py`, API `/api/v1/pki/*`. UI: `#/pki`.

## Principle

**Public certificates only.** API never accepts or stores private keys.

## Import rules

- Exactly one PEM CERTIFICATE block
- Not expired
- `purpose=ca` ↔ BasicConstraints CA
- `client` / `server` require matching ExtendedKeyUsage
- Returns SHA-256 fingerprint, subject, issuer, serial, validity

## API

```
GET/POST  /api/v1/pki/certificates
GET       /api/v1/pki/certificates/{fingerprint}/pem
POST      /api/v1/pki/certificates/{fingerprint}/revoke
GET/PUT/DELETE grants on NAS
```

Server material for FreeRADIUS is separate host files under `RADIUS_PKI_DIR` (`server.key`, `server.pem`, `ca.pem`). Helper: `scripts/pki-server-csr.sh`.
