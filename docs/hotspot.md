# Hotspot / vouchers

Routes `/api/v1/hotspot/vouchers`, generation in `hotspot.py`. UI: `#/hotspot`. Realm: `hotspot`.

## Voucher credentials

- Username: `hs-` + 20 hex chars
- Password: 32 hex chars
- RADIUS form: **SSHA2-512-Password** = Base64(SHA512(password||salt)||salt)

## API

```
POST   /api/v1/hotspot/vouchers
GET    /api/v1/hotspot/vouchers
DELETE /api/v1/hotspot/vouchers/{voucher_id}
```

`compose.hotspot.yaml` is a **deprecated empty stub**; use unified 1812/1813. Captive portal remains on the NAS.
