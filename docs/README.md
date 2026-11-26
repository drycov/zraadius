# ZRADIUS documentation

Документация сверена с кодом на ветке `main` (API `backend/main.py`, IAM, FreeRADIUS entrypoint, Compose). Статус продукта: **development alpha**.

## Старт и устройство

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Quick start, `.env`, bootstrap admin |
| [architecture.md](architecture.md) | Топология, слои, домены identity |
| [secrets.md](secrets.md) | Env-секреты, AES-GCM envelopes |
| [db-roles.md](db-roles.md) | `radius` / `zradius_api` / `zradius_runtime` |

## Управление доступом к консоли

| Документ | Содержание |
|----------|------------|
| [iam.md](iam.md) | Админы, роли, сессии, limiter, legacy token |
| [mfa.md](mfa.md) | TOTP и recovery codes |

## RADIUS runtime

| Документ | Содержание |
|----------|------------|
| [radius.md](radius.md) | Контейнер FreeRADIUS, флаги, healthcheck |
| [unified-radius.md](unified-radius.md) | Один listener 1812/1813, realms |
| [nas-runtime.md](nas-runtime.md) | Внешние NAS-клиенты, CoA |
| [services.md](services.md) | Каталог сервисов ≠ включение протокола |

## Доменные runbooks

| Документ | Содержание |
|----------|------------|
| [identities.md](identities.md) | Unified identities API |
| [management.md](management.md) | Legacy users/groups/NAS/accounting |
| [ppp.md](ppp.md) | L2TP/PPP profiles, pools, sessions, import |
| [ipam.md](ipam.md) | IP pools, allocations, radius export |
| [device-aaa.md](device-aaa.md) | Device users, grants, groups, reply profiles |
| [hotspot.md](hotspot.md) | Vouchers |
| [ipoe.md](ipoe.md) | MAC/IPoE bindings |

## Experimental overlays

| Документ | Содержание |
|----------|------------|
| [eap.md](eap.md) | PEAP path, `compose.eap.yaml`, PKI mount |
| [eap-tls.md](eap-tls.md) | EAP-TLS on top of EAP |
| [pki.md](pki.md) | Public cert inventory API (no private keys) |
| [proxy.md](proxy.md) | Outbound proxy realms |

## Operations

| Документ | Содержание |
|----------|------------|
| [operations.md](operations.md) | Boot, migrate repair, stale images, flags, backup |

## Исторические заметки в git

- `alpha-validation.md`, `integration-tests.md` — CI gate, не day-to-day runbook
- `db-recovery.md` / `runtime-recovery.md` — смысл перенесён в [operations.md](operations.md)
- `compose.hotspot.yaml`, `compose.ipoe.yaml`, `compose.device-aaa.yaml` — empty deprecated stubs; сервисы на unified 1812/1813
- `compose.eap.yaml`, `compose.eap-tls.yaml`, `compose.proxy.yaml` — **живые** overlay

При расхождении **код и OpenAPI `/docs` важнее** markdown.
