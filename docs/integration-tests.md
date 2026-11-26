# AAA integration checks

CI builds and starts an isolated Compose project and runs scripts/integration-radius.py. It creates a temporary RADIUS user, checks PAP success/rejection and blocking, then checks SQL Accounting Start, Interim and Stop including octet counters. The test deliberately leaves historical accounting records in the disposable CI database. Never run against production. Physical NAS / CoA ACK and NAK verification remains a separate lab test. The CI cleanup deletes only the ephemeral CI volume; do not copy this cleanup command to production.
