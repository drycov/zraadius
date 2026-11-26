"""Bounded, read-only reconciliation planning for directory identities."""
from uuid import UUID


def plan_identities(linked, snapshot):
    if snapshot.get("limited") is not False:
        raise ValueError("Incomplete directory snapshot")
    entries = {}
    for item in snapshot["items"]:
        guid = UUID(str(item["object_guid"]))
        if guid in entries:
            raise ValueError("Duplicate directory GUID")
        entries[guid] = item
    changes = []
    missing = 0
    incompatible = 0
    disabled = 0
    for row in linked:
        entry = entries.get(UUID(str(row["object_guid"])))
        if entry is None:
            missing += 1
            continue
        if not entry["compatible"]:
            incompatible += 1
        name = entry["username"] if entry["compatible"] else row["directory_username"]
        enabled = entry["directory_enabled"]
        if not enabled:
            disabled += 1
        if name != row["directory_username"] or enabled != row["directory_enabled"]:
            changes.append((row["identity_id"], name, enabled))
    return changes, {"linked":len(linked),"observed":len(entries),"changed":len(changes),
                     "not_observed":missing,"incompatible":incompatible,"directory_disabled":disabled}
