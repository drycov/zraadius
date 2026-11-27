"""Build a diagnostic reconciliation plan. Never mutate permissions."""
SERVICE_FIELDS={
    "device-aaa":"device","l2tp":"l2tp","pppoe":"pppoe",
    "hotspot":"hotspot","dot1x":"dot1x","wpa-enterprise":"wpa_enterprise",
    "console":"console_role",
}

def build_plan(effective, overrides=None):
    overrides=overrides or {}
    comparison=effective["comparison"]
    template=comparison["template"]
    if effective["source"] not in ("direct","group") or not template:
        return {"status":"blocked","reason":effective["source"],"operations":[],"runtime_changed":False}
    expected=set(comparison["expected_services"])
    actual=set(comparison["actual_services"])
    parameters=template.get("parameters") or {}
    operations=[]
    for service in sorted(expected|actual|set(overrides)):
        differences=[r for r in comparison.get("parameter_comparison",[]) if r["service"]==service and r["status"]!="match"]
        configured=parameters.get(SERVICE_FIELDS[service])
        if service not in expected and service not in actual:
            action,reason="KEEP","no_detected_difference"
        elif service not in expected:
            action,reason="DISABLE","individual_assignment_requires_review"
        elif service not in actual:
            action,reason="CREATE","missing_service_parameters" if configured is None else "missing_or_disabled_assignment"
        elif differences:
            action,reason="UPDATE","individual_parameters_require_review"
        else:
            action,reason="KEEP","no_detected_difference"
        override=overrides.get(service)
        proposed_action=action
        if override:
            action,reason="KEEP","protected_by_override"
        operations.append({"override":override,"proposed_action":proposed_action,"service":service,"action":action,"reason":reason,
            "expected_parameters":configured,"differences":differences,
            "requires_review":action!="KEEP","apply_supported":False})
    return {"status":"review_required" if any(o["requires_review"] for o in operations) else "protected" if any(o["override"] and o["proposed_action"]!="KEEP" for o in operations) else "in_sync",
        "reason":None,"operations":operations,"runtime_changed":False}
