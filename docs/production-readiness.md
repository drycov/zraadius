# Production readiness — release gate
Stage 63 is deferred. No automatic legacy account merge.
## Required validation
- Clean installation and upgrade of a copy of an existing database.
- Frontend TypeScript build and browser smoke tests.
- API import, OpenAPI, unit tests and role grants.
- FreeRADIUS configuration check, positive and negative PAP for Device AAA, L2TP, PPPoE, Hotspot (integration-identity.py).
- Separate MS-CHAPv2, PEAP with trusted server certificate, VLAN, IAM/MFA and RouterOS Accounting/CoA tests on a lab NAS.
- Load test, backup and restore, log/secret review.
The CI identity test uses the existing localhost static test client and inserts a fixture NAS into the isolated database only. Never run it against production. Existing network credentials are still sensitive; the runtime DB role no longer has SELECT on the web Argon2id column. API-level username reservation is not a database-wide constraint; direct SQL writers and legacy imports need separate collision controls. CI results must be green before deployment. EAP-TLS remains experimental, not a production recommendation.
