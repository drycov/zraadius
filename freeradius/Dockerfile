FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends freeradius freeradius-postgresql freeradius-utils postgresql-client openssl && rm -rf /var/lib/apt/lists/*
COPY sql /etc/freeradius/3.0/mods-available/sql
COPY zradius-site /etc/freeradius/3.0/sites-available/zradius
COPY prepare-sqlippool.sh /usr/local/bin/zradius-prepare-sqlippool
RUN sed -i 's/\r$//' /usr/local/bin/zradius-prepare-sqlippool && chmod 755 /usr/local/bin/zradius-prepare-sqlippool && sh -n /usr/local/bin/zradius-prepare-sqlippool
COPY sqlippool /etc/freeradius/3.0/mods-available/sqlippool
COPY zradius-pool-policy /etc/freeradius/3.0/zradius-pool-policy
COPY zradius-eap /etc/freeradius/3.0/mods-available/zradius-eap
COPY zradius-inner-tunnel /etc/freeradius/3.0/sites-available/zradius-inner-tunnel
COPY zradius-eap-authorize /etc/freeradius/3.0/zradius-eap-authorize
RUN sed -i 's/\r$//' /etc/freeradius/3.0/mods-available/zradius-eap /etc/freeradius/3.0/sites-available/zradius-inner-tunnel /etc/freeradius/3.0/zradius-eap-authorize
COPY zradius-tls-config /etc/freeradius/3.0/zradius-tls-config
COPY zradius-check-eap-tls /etc/freeradius/3.0/sites-available/zradius-check-eap-tls
COPY zradius-verify-cert.sh /usr/local/bin/zradius-verify-cert
RUN sed -i 's/\r$//' /etc/freeradius/3.0/zradius-tls-config /etc/freeradius/3.0/sites-available/zradius-check-eap-tls /usr/local/bin/zradius-verify-cert && chmod 755 /usr/local/bin/zradius-verify-cert && sh -n /usr/local/bin/zradius-verify-cert
COPY zradius-proxy-policy /etc/freeradius/3.0/zradius-proxy-policy
COPY zradius-proxy-accounting /etc/freeradius/3.0/zradius-proxy-accounting
RUN sed -i 's/\r$//' /etc/freeradius/3.0/zradius-proxy-policy /etc/freeradius/3.0/zradius-proxy-accounting
COPY entrypoint.sh /usr/local/bin/zradius-entrypoint
RUN sed -i 's/\r$//' /etc/freeradius/3.0/mods-available/sqlippool /etc/freeradius/3.0/zradius-pool-policy
RUN sed -i 's/\r$//' /usr/local/bin/zradius-entrypoint /etc/freeradius/3.0/mods-available/sql /etc/freeradius/3.0/sites-available/zradius && /bin/sh -n /usr/local/bin/zradius-entrypoint && chmod 755 /usr/local/bin/zradius-entrypoint && rm -f /etc/freeradius/3.0/mods-enabled/eap && rm -f /etc/freeradius/3.0/sites-enabled/* && ln -s ../sites-available/zradius /etc/freeradius/3.0/sites-enabled/zradius && ln -sf ../mods-available/sql /etc/freeradius/3.0/mods-enabled/sql
ENTRYPOINT ["/bin/sh", "/usr/local/bin/zradius-entrypoint"]
