"""Explain configured unified AAA eligibility, not a RADIUS authentication result."""
SERVICES=("device-aaa","l2tp","pppoe","hotspot","dot1x","wpa-enterprise")

def explain_service(service, identity_enabled, assigned, enabled, credential_ready, targets, requested_nas=None):
    candidates=[t for t in targets if requested_nas is None or t["nas_id"]==requested_nas]
    reasons=[]
    if not identity_enabled:
        reasons.append("identity_disabled")
    if not assigned:
        reasons.append("service_not_assigned")
    elif not enabled:
        reasons.append("service_disabled")
    if not credential_ready:
        reasons.append("credential_missing")
    if assigned and not candidates:
        reasons.append("no_effective_nas")
    elif assigned and not any(t["eligible"] for t in candidates):
        reasons.append("nas_or_policy_ineligible")
    return {"service":service,"assigned":assigned,"enabled":enabled,
            "credential_ready":credential_ready,"status":"blocked" if reasons else "configured",
            "reasons":reasons,"targets":candidates}

def inspect_identity(conn, identity_id, nas_id=None):
    identity=conn.execute("""SELECT i.id,i.username,i.enabled,
        COALESCE(c.password_hash ~ '^[A-Za-z0-9+/]{107}=$',false) AS pap_ready,
        COALESCE(c.nt_password ~ '^[0-9a-f]{32}$',false) AS mschap_ready
        FROM zradius_identities i LEFT JOIN zradius_identity_credentials c ON c.identity_id=i.id
        WHERE i.id=%s""",(identity_id,)).fetchone()
    if not identity:
        return None
    assignments=conn.execute("""SELECT 'device-aaa' AS service,enabled FROM zradius_device_users WHERE identity_id=%s
        UNION ALL SELECT 'l2tp',enabled FROM zradius_l2tp_users WHERE identity_id=%s
        UNION ALL SELECT 'pppoe',enabled FROM zradius_identity_pppoe WHERE identity_id=%s
        UNION ALL SELECT 'hotspot',enabled FROM zradius_identity_hotspot WHERE identity_id=%s
        UNION ALL SELECT service_code,enabled FROM zradius_identity_eap WHERE identity_id=%s""",(identity_id,)*5).fetchall()
    targets=conn.execute("""WITH targets AS (
        SELECT 'device-aaa' AS service,g.nas_id,true AS policy_ready,g.source::text AS source
            FROM zradius_device_users u JOIN zradius_device_effective_grants g ON g.user_id=u.id WHERE u.identity_id=%s
        UNION ALL SELECT 'l2tp',u.nas_id,EXISTS(SELECT 1 FROM zradius_l2tp_effective_profiles p WHERE p.user_id=u.id),'direct'
            FROM zradius_l2tp_users u WHERE u.identity_id=%s
        UNION ALL SELECT 'pppoe',nas_id,true,'direct' FROM zradius_identity_pppoe WHERE identity_id=%s
        UNION ALL SELECT 'hotspot',nas_id,true,'direct' FROM zradius_identity_hotspot WHERE identity_id=%s
        UNION ALL SELECT service_code,nas_id,true,'direct' FROM zradius_identity_eap WHERE identity_id=%s
    ) SELECT t.service,t.nas_id,n.shortname,t.source,
        (t.policy_ready AND EXISTS(SELECT 1 FROM zradius_nas_services s WHERE s.nas_id=t.nas_id AND s.service_code=t.service)
         AND CASE WHEN t.service IN ('dot1x','wpa-enterprise') THEN
            (SELECT count(*) FROM zradius_nas_services s WHERE s.nas_id=t.nas_id AND s.service_code IN ('dot1x','wpa-enterprise'))=1
         ELSE n.type='mikrotik' END) AS eligible
        FROM targets t JOIN nas n ON n.id=t.nas_id ORDER BY t.service,t.nas_id""",(identity_id,)*5).fetchall()
    by_service={a["service"]:a for a in assignments}
    services=[]
    for service in SERVICES:
        assignment=by_service.get(service)
        credential=identity["mschap_ready"] if service in ("dot1x","wpa-enterprise") else identity["pap_ready"]
        if service in ("pppoe","l2tp"):
            credential=identity["pap_ready"] or identity["mschap_ready"]
        services.append(explain_service(service,identity["enabled"],assignment is not None,
            bool(assignment and assignment["enabled"]),credential,
            [t for t in targets if t["service"]==service],nas_id))
    groups=conn.execute("""SELECT g.id,g.name FROM zradius_identity_groups g JOIN zradius_identity_group_members m ON m.group_id=g.id
        WHERE m.identity_id=%s ORDER BY g.name""",(identity_id,)).fetchall()
    return {"identity":identity,"requested_nas_id":nas_id,"services":services,"groups":groups,
            "mode":"configuration_only","runtime_verified":False}
