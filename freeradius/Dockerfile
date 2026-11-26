FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends freeradius freeradius-postgresql freeradius-utils postgresql-client && rm -rf /var/lib/apt/lists/*
COPY sql /etc/freeradius/3.0/mods-available/sql
COPY zradius-site /etc/freeradius/3.0/sites-available/zradius
RUN awk '/^allocate_existing = / { skip=1; next } skip && /RETURNING cte.framedipaddress"/ { skip=0; next } !skip { print }' /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/queries.conf > /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/zradius-queries.conf
# Reset the lease generation atomically on every allocation.
RUN awk '/^allocate_find = / { active=1 } active && /username = / { print; printf "        lease_token = gen_random_uuid(), lease_session = NULL, lease_started_at = date_trunc(%csecond%c, now()), %c\n",39,39,92; found=1; next } {print} active && /RETURNING cte.framedipaddress"/ {active=0} END {if (!found) exit 1}' /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/zradius-queries.conf > /tmp/zradius-queries.conf && mv /tmp/zradius-queries.conf /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/zradius-queries.conf
COPY sqlippool /etc/freeradius/3.0/mods-available/sqlippool
COPY zradius-pool-postauth /etc/freeradius/3.0/zradius-pool-postauth
COPY zradius-ipoe /etc/freeradius/3.0/sites-available/zradius-ipoe
RUN sed -i 's/\r$//' /etc/freeradius/3.0/sites-available/zradius-ipoe
COPY zradius-hotspot /etc/freeradius/3.0/sites-available/zradius-hotspot
RUN sed -i 's/\r$//' /etc/freeradius/3.0/sites-available/zradius-hotspot
COPY entrypoint.sh /usr/local/bin/zradius-entrypoint
RUN sed -i 's/\r$//' /etc/freeradius/3.0/mods-available/sqlippool /etc/freeradius/3.0/zradius-pool-postauth
RUN sed -i 's/\r$//' /usr/local/bin/zradius-entrypoint /etc/freeradius/3.0/mods-available/sql /etc/freeradius/3.0/sites-available/zradius && /bin/sh -n /usr/local/bin/zradius-entrypoint && chmod 755 /usr/local/bin/zradius-entrypoint && rm -f /etc/freeradius/3.0/mods-enabled/eap && rm -f /etc/freeradius/3.0/sites-enabled/* && ln -s ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius && ln -sf ../mods-available/sql /etc/freeradius/3.0/mods-enabled/sql
ENTRYPOINT ["/bin/sh", "/usr/local/bin/zradius-entrypoint"]
