FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends freeradius freeradius-postgresql freeradius-utils postgresql-client && rm -rf /var/lib/apt/lists/*
COPY sql /etc/freeradius/3.0/mods-available/sql
COPY zradius-site /etc/freeradius/3.0/sites-available/zradius
COPY entrypoint.sh /usr/local/bin/zradius-entrypoint
RUN sed -i 's/\r$//' /usr/local/bin/zradius-entrypoint /etc/freeradius/3.0/mods-available/sql /etc/freeradius/3.0/sites-available/zradius && /bin/sh -n /usr/local/bin/zradius-entrypoint && chmod 755 /usr/local/bin/zradius-entrypoint && rm -f /etc/freeradius/3.0/sites-enabled/* && ln -s ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius && ln -sf ../mods-available/sql /etc/freeradius/3.0/mods-enabled/sql
ENTRYPOINT ["/bin/sh", "/usr/local/bin/zradius-entrypoint"]
