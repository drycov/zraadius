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
