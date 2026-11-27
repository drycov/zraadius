"""Conservative inventory of legacy RADIUS policies. Never return credential values."""
import re

def assess(checks,replies,groups,disabled):
    blockers=[]
    credentials=[r for r in checks if r["attribute"]=="Cleartext-Password" and r["op"]==":="]
    if len(credentials)!=1:
        blockers.append("Exactly one Cleartext-Password check is required")
    for r in checks:
        if r["attribute"]=="Cleartext-Password" and r["op"]==":=":
            continue
        if disabled and r["attribute"]=="Auth-Type" and r["op"]==":=" and r["value"]=="Reject":
            continue
        blockers.append("Unsupported check: "+r["attribute"]+" "+r["op"])
    if groups:
        blockers.append("Group membership requires explicit policy reconciliation")
    allowed={"Mikrotik-Rate-Limit","Framed-Pool","Acct-Interim-Interval"}
    values={}
    for r in replies:
        name=r["attribute"]
        if name not in allowed or r["op"]!=":=" or name in values:
            blockers.append("Unsupported or duplicate reply: "+name+" "+r["op"])
        else:
            values[name]=r["value"]
    rate=values.get("Mikrotik-Rate-Limit","")
    pool=values.get("Framed-Pool","")
    interval=values.get("Acct-Interim-Interval","")
    if not re.fullmatch(r"[1-9][0-9]{0,5}M/[1-9][0-9]{0,5}M",rate):
        blockers.append("Explicit supported rate limit required")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",pool):
        blockers.append("Explicit supported NAS pool required")
    if not re.fullmatch(r"[0-9]{1,5}",interval) or not 60<=int(interval)<=86400:
        blockers.append("Explicit supported interim interval required")
    return {"attributes_compatible":not blockers,"blockers":blockers,
            "proposed_parameters":None if blockers else {"rate_limit":rate,"pool":pool,"interim_seconds":int(interval)},
            "legacy_enabled":not disabled,"requires_manual_review":True,"can_apply":False}
