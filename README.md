# ZRADIUS

Self-hosted FreeRADIUS management platform — 0.1.0-alpha.

## Run management prototype

Copy .env.example to .env and replace both secrets with independent random values (e.g. openssl rand -hex 32). Run:

    docker compose up --build -d

Open http://localhost:8080 and enter ADMIN_TOKEN. API documentation: http://localhost:8080/docs.

Implemented: management API, PostgreSQL bootstrap, create/list RADIUS users and groups, group assignment API, audit and health endpoints, minimal browser console. Single administrative token. No production NAS should connect yet: FreeRADIUS runtime, full upstream SQL schema, RBAC, accounting and CoA are not implemented. See docs/architecture.md.
