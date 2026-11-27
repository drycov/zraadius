"""Deterministic planning resolver. Does not authorize requests."""
def resolve(rows):
    buckets={}
    for r in rows:
        if r["enabled"]:
            buckets.setdefault((r["attribute_list"],r["name"]),[]).append(r)
    effective=[]; conflicts=[]
    for (attribute_list,name),items in sorted(buckets.items()):
        def rank(r):
            return (r["source"]=="identity",r["nas_id"] is not None,r["priority"])
        best=max(map(rank,items))
        winners=[r for r in items if rank(r)==best]
        if len({(r["operator"],r["value"]) for r in winners})!=1:
            conflicts.append({"name":name,"attribute_list":attribute_list,"policy_ids":sorted({r["policy_id"] for r in winners})})
        else:
            effective.append({**winners[0],"policy_ids":sorted({r["policy_id"] for r in winners})})
    return {"effective":effective,"conflicts":conflicts,"runtime_enforced":False,"can_apply":False}
