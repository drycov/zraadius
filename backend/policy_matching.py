"""Pure diagnostic scope matcher; no authorization side effects."""
SERVICES=("device-aaa","l2tp","pppoe","hotspot","dot1x","wpa-enterprise")

def match_rules(rules, service, nas_id):
    if service not in SERVICES or not isinstance(nas_id,int) or isinstance(nas_id,bool) or nas_id<=0:
        raise ValueError("Explicit service and positive NAS ID required")
    items=[]
    for rule in sorted(rules,key=lambda r:r["id"]):
        reasons=[]
        if not rule["enabled"]:
            reasons.append("rule_disabled")
        if rule["service"] is not None and rule["service"]!=service:
            reasons.append("service_mismatch")
        if rule["nas_id"] is not None and rule["nas_id"]!=nas_id:
            reasons.append("nas_mismatch")
        scope=("service_nas" if rule["service"] is not None and rule["nas_id"] is not None
               else "service" if rule["service"] is not None else "nas" if rule["nas_id"] is not None else "global")
        items.append({**rule,"scope":scope,"matched":not reasons,"exclusion_reasons":reasons})
    matched=[r for r in items if r["matched"]]
    allows=[r["id"] for r in matched if r["effect"]=="ALLOW"]
    denies=[r["id"] for r in matched if r["effect"]=="DENY"]
    return {"items":items,"matched_count":len(matched),"allow_rule_ids":allows,
            "deny_rule_ids":denies,"mixed_effects":bool(allows and denies),
            "resolution":"not_evaluated","runtime_enforced":False}
