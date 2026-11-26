# ZRADIUS

Self-hosted FreeRADIUS management platform. Initial development release; not production-ready.

## Development

Copy `.env.example` to `.env`, replace all secrets and run `docker compose up --build -d`. Management UI binds to localhost:8080. API documentation: http://localhost:8080/docs.

Initial scope: PostgreSQL-backed RADIUS users, groups and accounting inspection. Single administrative token; full RBAC, NAS management, CoA and configuration deployment are future milestones. FreeRADIUS integration must be validated before connecting production NAS.
