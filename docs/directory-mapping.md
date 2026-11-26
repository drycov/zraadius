# Directory group policy mapping (66.0.5 foundation)

Migration 0031 stores explicit many-to-many links from observed AD security groups to existing Unified Identity groups. Personal administrators can inspect the observed members and replace target mappings atomically. No manual membership or RADIUS authorization changes occur. No runtime grants. Live inheritance, freshness enforcement, revocation and automatic service provisioning require further implementation and tests. Do not interpret mapping as access assignment. Build and migrations not verified.
