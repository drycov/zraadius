# ZRADIUS

Self-hosted FreeRADIUS management platform — development alpha.

Copy .env.example to .env and replace all three secrets with independent random hex values (openssl rand -hex 32). Run docker compose up --build -d. Open http://localhost:8080 and enter ADMIN_TOKEN. API documentation: http://localhost:8080/docs.

React + TypeScript + Ant Design console is served through nginx; API is internal. Dashboard uses database counts, not synthetic telemetry. Open accounting records may be stale. User and NAS management, MikroTik profiles, dictionary catalog, accounting and audit are available. NAS inventory is not applied to runtime. Tokens are kept in browser memory only. See docs/management.md and docs/radius.md. Not production-ready; validate Docker startup and AAA behavior before use.
