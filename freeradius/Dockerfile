FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends freeradius freeradius-postgresql freeradius-utils postgresql-client && rm -rf /var/lib/apt/lists/*
COPY sql /etc/freeradius/3.0/mods-available/sql
COPY zradius-site /etc/freeradius/3.0/sites-available/zradius
RUN awk '/^allocate_existing = / { skip=1; next } skip && /RETURNING cte.framedipaddress"/ { skip=0; next } !skip { print }' /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/queries.conf > /etc/freeradius/3.0/mods-config/sql/ippool/postgresql/zradius-queries.conf
COPY sqlippool /etc/freeradius/3.0/mods-available/sqlippool
COPY zradius-pool-postauth /etc/freeradius/3.0/zradius-pool-postauth
COPY entrypoint.sh /usr/local/bin/zradius-entrypoint
RUN sed -i 's/\r$//' /etc/freeradius/3.0/mods-available/sqlippool /etc/freeradius/3.0/zradius-pool-postauth
RUN sed -i 's/\r$//' /usr/local/bin/zradius-entrypoint /etc/freeradius/3.0/mods-available/sql /etc/freeradius/3.0/sites-available/zradius && /bin/sh -n /usr/local/bin/zradius-entrypoint && chmod 755 /usr/local/bin/zradius-entrypoint && rm -f /etc/freeradius/3.0/mods-enabled/eap && rm -f /etc/freeradius/3.0/sites-enabled/* && ln -s ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius && ln -sf ../mods-available/sql /etc/freeradius/3.0/mods-enabled/sql
ENTRYPOINT ["/bin/sh", "/usr/local/bin/zradius-entrypoint"]
