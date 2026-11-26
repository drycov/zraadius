"""Restricted RouterOS export reader. Never execute RouterOS commands."""
import re
import shlex

NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
USER = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
PROFILE_FIELDS = {"name", "remote-address", "comment"}
SECRET_FIELDS = {"name", "profile", "remote-address", "service", "disabled", "comment", "password"}

def parse_export(source):
    if len(source.encode("utf-8")) > 262144:
        raise ValueError("Export exceeds 256 KiB")
    # Support ordinary exported continuation lines only; no script evaluation.
    source = re.sub(r"\\\r?\n[ \t]*", "", source)
    section = None
    rows = []
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("/"):
            match = re.fullmatch(r"/ppp (profile|secret)(?: (add .+))?", line)
            section = match.group(1) if match else None
            if not match or not match.group(2):
                continue
            line = match.group(2)
        if section is None:
            continue
        if len(rows) >= 500:
            raise ValueError("At most 500 PPP records per import")
        row = {"line": lineno, "kind": section, "name": "", "issues": []}
        rows.append(row)
        if not line.startswith("add "):
            row["issues"].append("Only add records are supported")
            continue
        # RouterOS escape syntax is not shell syntax; reject escapes instead of silently changing values.
        if any(c in line for c in ('\\', '$', '[', ']', ';', '\x00')):
            row["issues"].append("Unsupported RouterOS escape or expression")
            continue
        try:
            tokens = shlex.split(line, comments=False, posix=True)[1:]
        except ValueError:
            row["issues"].append("Malformed quoted value")
            continue
        values = {}
        for token in tokens:
            key, sep, value = token.partition("=")
            if not sep or not key or key in values:
                row["issues"].append("Malformed or repeated property")
                break
            values[key] = value
        name = values.get("name", "")
        if not (NAME if section == "profile" else USER).fullmatch(name):
            row["issues"].append("Invalid or missing name")
        else:
            row["name"] = name
        row["comment"] = values.get("comment", "")[:200]
        row["remote_address"] = values.get("remote-address") or None
        if section == "profile":
            row["ignored_fields"] = sorted(set(values)-PROFILE_FIELDS)
        else:
            row["ignored_fields"] = sorted(set(values)-SECRET_FIELDS)
            row["profile"] = values.get("profile") or "default"
            row["service"] = values.get("service") or "any"
            row["disabled"] = values.get("disabled", "no")
            if row["service"] != "l2tp":
                row["issues"].append("Only explicit service=l2tp can be imported")
            if row["disabled"] not in ("yes", "no"):
                row["issues"].append("Invalid disabled value")
            if row["ignored_fields"]:
                row["issues"].append("Unsupported secret properties require manual review")
        # Export passwords are intentionally discarded. Never return or store them.
    if not rows:
        raise ValueError("No PPP profile or secret records found")
    return rows
