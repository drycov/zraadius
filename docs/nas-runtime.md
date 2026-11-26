# NAS runtime and CoA

## Defaults

- RADIUS clients: **loopback only**
- `RADIUS_ENABLE_NAS=false`
- `COA_ENABLED=false`

## Enabling external NAS

1. Register NAS in management API/UI (secret sealed in DB)
2. Set in `.env`:

```env
RADIUS_ENABLE_NAS=true
RADIUS_BIND_IP=<trusted host address>
```

3. Firewall UDP 1812/1813 to trusted sources only
4. **Recreate** the radius container so entrypoint re-renders clients from DB snapshot

There is no hot reload. Message-Authenticator is required on Access-Request.

## CoA / Disconnect (RFC 5176)

```env
COA_ENABLED=true
COA_ALLOWED_NETWORKS=10.0.0.0/8,192.168.0.0/16
```

- Explicit CIDR allowlist only
- API sends only to registered NAS with open accounting context as coded
- UDP **3799** from Docker egress; MikroTik `/radius incoming set accept=yes port=3799`
- ACK does not close accounting rows

## Security

Do not expose NAS-enabled RADIUS to the Internet. Secrets in rendered client files are plaintext inside the container.
