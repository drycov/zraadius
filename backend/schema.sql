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
