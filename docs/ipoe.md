# IPoE / MAC bindings

Routes `/api/v1/ipoe/*`, normalization in `ipoe.py`. UI: `#/ipoe`. Realm: `ipoe`.

## Normalization

**MAC**: 12 hex / colon / dash / Cisco dotted → lowercase `aa:bb:cc:dd:ee:ff`. Rejects all-zero and multicast.

**IPv4**: optional; rejects multicast, unspecified, loopback, link-local, broadcast.

## API

```
GET/POST   /api/v1/ipoe/bindings
PUT/DELETE /api/v1/ipoe/bindings/{binding_id}
POST       /api/v1/ipoe/preview
```

`compose.ipoe.yaml` is deprecated empty; unified ports only. Experimental until lab-tested on your NAS/DHCP path.
