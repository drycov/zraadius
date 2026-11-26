# PPP / L2TP

Routes `/api/v1/ppp/*`, helpers `ppp_vpn.py`, `ppp_import.py`, `routeros_ppp.py`. UI: `#/ppp`.

## Model

| Entity | Purpose |
|--------|----------|
| Profile | Reply template |
| L2TP user | VPN/PPP account with password, state, assignment |
| VPN group | Group + members |
| Address space | Spaces; `.../conflicts` for overlaps |
| Pool | Address pools |
| Session | Sessions, summary, disconnect, history |
| Import | `preview` → `apply` |
| RouterOS config | NAS config fragments |
| Monitoring | PPP status summary |

## Passwords (`ppp_vpn.credentials`)

- Length **16–128** characters, ≤128 UTF-8 bytes, no NUL
- **NT hash** (MD4 over UTF-16LE) for MS-CHAPv2 and salted SHA-512 storage form
- Not the same rules as management IAM (Argon2)

## RADIUS side

- Unified endpoint: realm `pppoe` or `l2tp`
- Optional SQL IP pool only with `RADIUS_ENABLE_SQLIPPOOL=true`
- Disconnect uses CoA when enabled

Alpha: lab-test before production use.
