# IPAM

Routes `/api/v1/ipam/*`, bounds logic in `ipam.py`. UI: `#/ipam`.

## Purpose

Inventory of IPv4/IPv6 pools, allocations, RADIUS export/activate. **Not** a full DHCPd.

## Pool bounds (`pool_bounds`)

- Strict `ipaddress.ip_network`
- IPv4 prefix < 31 excludes network/broadcast from usable range
- IPv6 prefix < 127 excludes network address
- Multicast / invalid networks rejected

## API

```
GET/POST   /api/v1/ipam/pools
DELETE     /api/v1/ipam/pools/{pool_id}
GET/POST   /api/v1/ipam/pools/{pool_id}/allocations
DELETE     /api/v1/ipam/pools/{pool_id}/allocations/{allocation_id}
POST       /api/v1/ipam/pools/{pool_id}/radius-export
GET        /api/v1/ipam/radius-exports
DELETE     /api/v1/ipam/pools/{pool_id}/radius-export
POST       /api/v1/ipam/pools/{pool_id}/radius-activate
GET        /api/v1/ipam/radius-leases
```

Without `RADIUS_ENABLE_SQLIPPOOL=true`, pools remain management inventory.
