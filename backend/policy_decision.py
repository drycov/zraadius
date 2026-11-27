"""Centralized policy decision overlay; never grants authentication."""
def resolve_decision(baseline, matches, nas_service_configured):
    reasons=list(baseline.get("reasons", []))
    if baseline.get("status")!="configured" and not reasons:
        reasons.append("baseline_not_configured")
    if not nas_service_configured:
        reasons.append("nas_service_not_configured")
    denies=matches["deny_rule_ids"]
    allows=matches["allow_rule_ids"]
    if denies:
        reasons.append("explicit_deny")
    if reasons:
        decision="DENY"
    elif allows:
        decision="ALLOW"
    else:
        decision="EXISTING_POLICY"
    return {"decision":decision,"reasons":list(dict.fromkeys(reasons)),
        "decisive_rule_ids":denies if denies else allows if decision=="ALLOW" else [],
        "baseline_status":baseline.get("status"),
        "algorithm":"deny_overrides","authentication_required":True,
        "runtime_enforced":False}
