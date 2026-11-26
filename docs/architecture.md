# Architecture

The initial slice is a single-tenant development management plane. It does not yet start FreeRADIUS. Before attaching a real server, replace the minimal SQL bootstrap with versioned migrations based on the upstream FreeRADIUS PostgreSQL schema, configure separate database roles, and test Access-Accept/Reject and Accounting. The Cleartext-Password attribute is deliberately used for compatibility testing; protect database and backups, and select credential formats per authentication protocol.

Next: FreeRADIUS container and SQL integration; full CRUD and profiles; accounting; NAS management; CoA; RBAC; React console; Go deployment agent. Management must not be required for AAA requests.
