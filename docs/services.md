# Service catalog

`GET /api/v1/services` and NAS/group service bindings are **inventory and policy metadata** for the management plane and unified radius site logic.

They are **not** an automatic license to enable protocols:

| Catalog / UI area | Runtime requirement |
|-------------------|---------------------|
| PPP / L2TP profiles | FreeRADIUS PPP branch + NAS realm + optional pools |
| IPoE | Trusted circuit/MAC identity; NAS DHCP behavior |
| Hotspot | Captive portal + vouchers API |
| Device AAA | Roles, grants, separate auth log |
| EAP / PKI | Certs, flags, inner tunnel |
| Proxy | Home servers, loop prevention |

No compose flag is flipped merely by inserting a catalog row. Use explicit env flags and overlay files, then lab-test Accept/Reject and accounting.
