# Unified RADIUS endpoint

One radius container, one public authentication listener **UDP 1812** and accounting **UDP 1813**.

## Realms (RouterOS `/radius`)

- `pppoe`
- `l2tp`
- `ipoe`
- `hotspot`
- `device-aaa`

Configure a **separate** `/radius` entry per service on MikroTik if needed, same destination and secret, different realm.

RouterOS PPP may not distinguish PPPoE vs L2TP by realm on the same NAS; assign one PPP realm until NAS-Port-Type policy exists.

## Request acceptance rules (design intent)

- Remote requests require assigned service, real source IPv4, and matching registered MikroTik NAS (when NAS runtime is enabled)
- Unknown or missing realms → reject
- Local **loopback without realm** reserved for development tests and healthcheck
- Do not put a proxy in front that rewrites source IP to loopback
- Accounting for managed NAS expects consistent NAS-IP-Address vs packet source

## Removed

Older per-service high ports (18120/18121/18122) are gone.

## Optional SQL pool

Invoked only on the PPP branch when `RADIUS_ENABLE_SQLIPPOOL=true`.

## EAP / Proxy

Code paths and compose overlays exist; default base stack leaves them disabled.
