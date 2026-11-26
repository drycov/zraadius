CREATE TABLE IF NOT EXISTS radcheck (
 id bigserial PRIMARY KEY, username varchar(64) NOT NULL,
 attribute varchar(64) NOT NULL, op varchar(2) NOT NULL DEFAULT ':=',
 value varchar(253) NOT NULL
);
CREATE INDEX IF NOT EXISTS radcheck_username_idx ON radcheck(username);
CREATE TABLE IF NOT EXISTS radreply (LIKE radcheck INCLUDING ALL);
CREATE TABLE IF NOT EXISTS radgroupcheck (
 id bigserial PRIMARY KEY, groupname varchar(64) NOT NULL,
 attribute varchar(64) NOT NULL, op varchar(2) NOT NULL, value varchar(253) NOT NULL
);
CREATE TABLE IF NOT EXISTS radgroupreply (LIKE radgroupcheck INCLUDING ALL);
CREATE TABLE IF NOT EXISTS radusergroup (
 username varchar(64) NOT NULL, groupname varchar(64) NOT NULL,
 priority integer NOT NULL DEFAULT 1, PRIMARY KEY(username,groupname)
);
CREATE TABLE IF NOT EXISTS zradius_groups (name varchar(64) PRIMARY KEY);
CREATE TABLE IF NOT EXISTS zradius_audit (
 id bigserial PRIMARY KEY, action text NOT NULL, subject text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);

-- Accounting columns compatible with the packaged PostgreSQL queries.
CREATE TABLE IF NOT EXISTS radacct (
 radacctid bigserial PRIMARY KEY,
 acctsessionid text NOT NULL, acctuniqueid text NOT NULL UNIQUE,
 username text, realm text, nasipaddress inet NOT NULL, nasportid text,
 nasporttype text, acctstarttime timestamptz, acctupdatetime timestamptz,
 acctstoptime timestamptz, acctinterval bigint, acctsessiontime bigint,
 acctauthentic text, connectinfo_start text, connectinfo_stop text,
 acctinputoctets bigint, acctoutputoctets bigint, calledstationid text,
 callingstationid text, acctterminatecause text, servicetype text,
 framedprotocol text, framedipaddress inet, framedipv6address inet,
 framedipv6prefix inet, framedinterfaceid text, delegatedipv6prefix inet,
 class text
);
CREATE INDEX IF NOT EXISTS radacct_active_idx ON radacct(username) WHERE acctstoptime IS NULL;
CREATE TABLE IF NOT EXISTS radpostauth (
 id bigserial PRIMARY KEY, username text NOT NULL, pass text,
 reply text, authdate timestamptz DEFAULT now(), class text
);

CREATE TABLE IF NOT EXISTS zradius_disabled_users (
 username varchar(64) PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS nas (
 id bigserial PRIMARY KEY, nasname varchar(128) NOT NULL UNIQUE,
 shortname varchar(64) NOT NULL UNIQUE, type varchar(30) NOT NULL DEFAULT 'other',
 ports integer, secret varchar(253) NOT NULL, server varchar(64),
 community varchar(64), description varchar(200)
);

CREATE TABLE IF NOT EXISTS zradius_coa_requests (
 id bigserial PRIMARY KEY,
 radacctid bigint NOT NULL,
 action text NOT NULL CHECK (action IN ('disconnect','coa')),
 status text NOT NULL CHECK (status IN ('pending','ack','nak','unknown')),
 created_at timestamptz NOT NULL DEFAULT now(),
 completed_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS zradius_coa_pending_idx ON zradius_coa_requests(radacctid) WHERE status='pending';

CREATE TABLE IF NOT EXISTS nasreload (
 nasipaddress inet PRIMARY KEY,
 reloadtime timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS radacct_nas_open_idx ON radacct(nasipaddress) WHERE acctstoptime IS NULL;

CREATE TABLE IF NOT EXISTS zradius_services (
 code text PRIMARY KEY, name text NOT NULL, methods text NOT NULL,
 maturity text NOT NULL CHECK (maturity IN ('experimental','planned','validated'))
);
INSERT INTO zradius_services(code,name,methods,maturity) VALUES
('pppoe','PPPoE','PAP / CHAP / MS-CHAPv2','experimental'),
('ipoe','IPoE','DHCP / MAC Auth','planned'),
('l2tp','L2TP','PAP / CHAP / MS-CHAPv2','experimental'),
('hotspot','Hotspot','Captive Portal','planned'),
('dot1x','802.1X','EAP','planned'),
('wpa-enterprise','WPA Enterprise','PEAP / EAP-TLS','planned'),
('device-aaa','Device AAA','SSH / WinBox','planned'),
('proxy','RADIUS Proxy','Realm routing','planned')
ON CONFLICT (code) DO NOTHING;
CREATE TABLE IF NOT EXISTS zradius_nas_services (
 nas_id bigint REFERENCES nas(id) ON DELETE CASCADE,
 service_code text REFERENCES zradius_services(code),
 PRIMARY KEY(nas_id,service_code)
);
CREATE TABLE IF NOT EXISTS zradius_group_services (
 groupname varchar(64) REFERENCES zradius_groups(name) ON DELETE CASCADE,
 service_code text REFERENCES zradius_services(code),
 PRIMARY KEY(groupname,service_code)
);

CREATE TABLE IF NOT EXISTS zradius_device_roles (
 groupname varchar(64) PRIMARY KEY REFERENCES zradius_groups(name) ON DELETE CASCADE,
 mikrotik_group varchar(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS zradius_ipoe_bindings (
 id bigserial PRIMARY KEY,
 nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
 mac macaddr NOT NULL,
 static_ip inet,
 circuit_id varchar(253),
 remote_id varchar(253),
 enabled boolean NOT NULL DEFAULT true,
 description varchar(200) NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(nas_id,mac),
 CHECK (static_ip IS NULL OR (family(static_ip)=4 AND masklen(static_ip)=32))
);
CREATE UNIQUE INDEX IF NOT EXISTS zradius_ipoe_static_ip_idx
 ON zradius_ipoe_bindings(nas_id,static_ip) WHERE static_ip IS NOT NULL;

CREATE TABLE IF NOT EXISTS zradius_ip_pools (
 id bigserial PRIMARY KEY,
 name varchar(64) UNIQUE NOT NULL,
 network cidr NOT NULL,
 first_ip inet NOT NULL,
 last_ip inet NOT NULL,
 capacity numeric(39,0) NOT NULL CHECK(capacity>0),
 description varchar(200) NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(first_ip <<= network AND last_ip <<= network AND first_ip <= last_ip),
 EXCLUDE USING gist (network inet_ops WITH &&)
);
CREATE TABLE IF NOT EXISTS zradius_ip_allocations (
 id bigserial PRIMARY KEY,
 pool_id bigint NOT NULL REFERENCES zradius_ip_pools(id) ON DELETE RESTRICT,
 address inet NOT NULL UNIQUE,
 owner varchar(128) NOT NULL,
 kind text NOT NULL CHECK(kind IN ('reserved','allocated')),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(masklen(address)=CASE family(address) WHEN 4 THEN 32 ELSE 128 END)
);
CREATE INDEX IF NOT EXISTS zradius_ip_allocations_pool_idx ON zradius_ip_allocations(pool_id,address);

-- Dedicated runtime pool staging. No lease allocation by FreeRADIUS yet.
CREATE TABLE IF NOT EXISTS zradius_radius_pool_exports (
 pool_id bigint PRIMARY KEY REFERENCES zradius_ip_pools(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS zradius_radius_pool_addresses (
 pool_id bigint NOT NULL REFERENCES zradius_radius_pool_exports(pool_id) ON DELETE CASCADE,
 address inet NOT NULL UNIQUE,
 PRIMARY KEY(pool_id,address),
 CHECK(family(address)=4 AND masklen(address)=32)
);
CREATE TABLE IF NOT EXISTS zradius_radius_pool_groups (
 groupname varchar(64) PRIMARY KEY REFERENCES zradius_groups(name) ON DELETE CASCADE,
 pool_id bigint NOT NULL REFERENCES zradius_radius_pool_exports(pool_id) ON DELETE RESTRICT
);

-- FreeRADIUS 3.2.x PostgreSQL sqlippool-compatible lease storage.
CREATE TABLE IF NOT EXISTS radippool (
 id bigserial PRIMARY KEY,
 pool_name text NOT NULL,
 framedipaddress inet NOT NULL UNIQUE,
 nasipaddress text NOT NULL DEFAULT '',
 pool_key text NOT NULL DEFAULT '',
 calledstationid text NOT NULL DEFAULT '',
 callingstationid text NOT NULL DEFAULT '',
 expiry_time timestamp(0) without time zone NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'),
 username text DEFAULT ''
);
CREATE INDEX IF NOT EXISTS radippool_poolname_expire ON radippool(pool_name,expiry_time);
CREATE INDEX IF NOT EXISTS radippool_nasip_poolkey_ipaddress ON radippool(nasipaddress,pool_key,framedipaddress);
CREATE TABLE IF NOT EXISTS zradius_radius_pool_active (
 pool_id bigint PRIMARY KEY REFERENCES zradius_radius_pool_exports(pool_id) ON DELETE RESTRICT,
 activated_at timestamptz NOT NULL DEFAULT now()
);

-- Lease correlation uses an opaque generation token returned in Class.
ALTER TABLE radippool ADD COLUMN IF NOT EXISTS lease_token uuid;
ALTER TABLE radippool ADD COLUMN IF NOT EXISTS lease_session text;
ALTER TABLE radippool ADD COLUMN IF NOT EXISTS lease_started_at timestamptz;
CREATE UNIQUE INDEX IF NOT EXISTS radippool_lease_token_idx ON radippool(lease_token) WHERE lease_token IS NOT NULL;

CREATE OR REPLACE FUNCTION zradius_accounting_lease() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE token uuid;
BEGIN
 -- Never match by username, NAS port or IP alone.
 IF NEW.class IS NULL OR NEW.class !~ '^zradius:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    OR NEW.framedipaddress IS NULL OR NEW.acctuniqueid IS NULL THEN
   RETURN NEW;
 END IF;
 token := substring(NEW.class from 9)::uuid;
 IF NEW.acctstoptime IS NOT NULL THEN
   UPDATE radippool SET expiry_time=LEAST(expiry_time,now() AT TIME ZONE 'UTC'),
     lease_token=NULL,lease_session=NULL,lease_started_at=NULL
   WHERE lease_token=token AND framedipaddress=NEW.framedipaddress
     AND username=NEW.username AND nasipaddress=host(NEW.nasipaddress)
     AND lease_session=NEW.acctuniqueid
     AND NEW.acctstoptime>=lease_started_at;
 ELSE
   UPDATE radippool SET lease_session=NEW.acctuniqueid
   WHERE lease_token=token AND framedipaddress=NEW.framedipaddress
     AND username=NEW.username AND nasipaddress=host(NEW.nasipaddress)
     AND (lease_session IS NULL OR lease_session=NEW.acctuniqueid)
     AND NEW.acctstarttime>=lease_started_at
     AND expiry_time>now() AT TIME ZONE 'UTC';
 END IF;
 RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS zradius_accounting_lease_trigger ON radacct;
CREATE TRIGGER zradius_accounting_lease_trigger AFTER INSERT OR UPDATE ON radacct
FOR EACH ROW EXECUTE FUNCTION zradius_accounting_lease();

-- IPoE runtime exists as opt-in static IPv4 authentication, not validated on hardware.
UPDATE zradius_services SET maturity='experimental' WHERE code='ipoe' AND maturity='planned';

CREATE TABLE IF NOT EXISTS zradius_hotspot_vouchers (
 id bigserial PRIMARY KEY,
 nas_id bigint NOT NULL REFERENCES nas(id) ON DELETE RESTRICT,
 username varchar(64) NOT NULL UNIQUE,
 password_hash text NOT NULL,
 expires_at timestamptz NOT NULL,
 session_seconds integer NOT NULL CHECK(session_seconds BETWEEN 60 AND 86400),
 idle_seconds integer NOT NULL CHECK(idle_seconds BETWEEN 60 AND 86400),
 rate_limit varchar(64),
 enabled boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS zradius_hotspot_nas_idx ON zradius_hotspot_vouchers(nas_id);
UPDATE zradius_services SET maturity='experimental' WHERE code='hotspot' AND maturity='planned';

CREATE TABLE IF NOT EXISTS zradius_device_users (
 id bigserial PRIMARY KEY, username varchar(64) UNIQUE NOT NULL,
 password_hash text NOT NULL, enabled boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS zradius_device_grants (
 user_id bigint REFERENCES zradius_device_users(id) ON DELETE CASCADE,
 nas_id bigint REFERENCES nas(id) ON DELETE CASCADE,
 role text NOT NULL CHECK(role IN ('read','write','full')),
 PRIMARY KEY(user_id,nas_id)
);
CREATE TABLE IF NOT EXISTS zradius_device_auth_log (
 id bigserial PRIMARY KEY, username text NOT NULL, source_ip inet NOT NULL,
 result text NOT NULL CHECK(result IN ('accept','reject')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS zradius_device_auth_time_idx ON zradius_device_auth_log(created_at);
UPDATE zradius_services SET maturity='experimental' WHERE code='device-aaa' AND maturity='planned';
