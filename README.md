# ZRADIUS

Self-hosted FreeRADIUS management platform — development alpha.

Copy .env.example to .env and replace all three secrets with independent random hex values (openssl rand -hex 32). Run docker compose up --build -d. Open http://localhost:8080 and enter ADMIN_TOKEN. API documentation: http://localhost:8080/docs.

Features: users, groups, MikroTik group profiles, NAS inventory, accounting inspection, audit and a development FreeRADIUS SQL runtime. NAS inventory is not applied to runtime. See docs/management.md and docs/radius.md. Not production-ready; validate Docker startup and AAA behavior before use.
