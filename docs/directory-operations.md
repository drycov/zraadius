# Directory operations (66.x consolidation)

The directory integration is an alpha management-plane feature, not AD password authentication.
Enable LDAPS and explicitly allow controller DNS names. Replica mappings must refer to controllers
of the same AD domain. Mount the private CA read-only in both API and directory-worker if required.

## Manual operation
The Directory page supports per-identity and bulk metadata reconciliation, group observation,
group mapping configuration, controller testing and audit history. Bulk snapshots are capped at
10000 entries; incomplete snapshots and duplicate GUIDs are rejected. Missing objects are not
treated as deleted. Group mappings are not live RADIUS policy.

## Scheduler
Run `docker compose --profile directory-sync up -d --build directory-worker`.
Set ZRADIUS_DIRECTORY_SYNC_INTERVAL (60..86400 seconds, default 900).
The worker periodically reconciles metadata for enabled profiles, uses a PostgreSQL session
advisory lock against duplicate worker instances, and logs success/failure. It does not reconcile
group membership or grant/revoke network access. Manual requests are not covered by the worker lock.
The directory profile row lock serializes writes, not LDAP snapshot collection.

## Revocation
A personal administrator must preview and explicitly confirm revocation of a currently observed
disabled AD account. Unknown or missing directory state does not qualify. Management identities
are excluded. Local identity disable is committed before optional CoA requests. CoA requires its
existing deployment flags and NAS allowlist; up to 100 attributed network sessions are examined.
Results are best effort and Accounting-Stop remains authoritative. No automatic re-enable.

## Validation
Run `docker compose run --rm --no-deps api python -m unittest test_directory_reconcile`.
Run backend compile checks and frontend build before deployment. Live AD, PostgreSQL and
NAS integration checks are required. No new database migration is introduced by this consolidation.

## Remaining work
Full AD authentication, live directory group policy enforcement, automated group reconciliation,
persistent controller health and scheduled retry/backoff, immutable preview tokens, end-to-end
tests and production hardening remain outstanding.
