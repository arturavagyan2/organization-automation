#!/usr/bin/env python3
import argparse, json, re, subprocess, sys
from pathlib import Path

def run(cmd, *, input_text=None, check=True, desc=None):
    if desc: print(f"→ {desc}: {' '.join(cmd)}")
    cp = subprocess.run(cmd, text=True, input=input_text, capture_output=True)
    if cp.stdout.strip(): print(cp.stdout.strip())
    if cp.stderr.strip(): print("(stderr)", cp.stderr.strip())
    if check and cp.returncode != 0: sys.exit(cp.returncode)
    return cp

def load_students(path: Path):
    raw = path.read_text(encoding="utf-8")
    cleaned = re.sub(r',\s*([}\]])', r'\1', raw)  # tolerate trailing commas
    data = json.loads(cleaned)
    rows = []
    for it in data:
        if isinstance(it, dict) and it.get("username"):
            rows.append({"name": (it.get("name") or "").strip(),
                         "username": it["username"].strip().lstrip("@")})
    if not rows:
        print("✖ No students found"); sys.exit(1)
    return rows

def gh_prechecks(org):
    run(["gh","--version"], desc="check gh")
    run(["gh","auth","status"], desc="check auth")
    run(["gh","api",f"orgs/{org}","--jq",".login"], desc=f"check org {org}")

def resolve_uid(username: str) -> int | None:
    cp = subprocess.run(["gh","api",f"users/{username}","--jq",".id"], text=True, capture_output=True)
    if cp.returncode != 0: return None
    try: return int(cp.stdout.strip())
    except: return None

def is_member(org: str, username: str) -> bool:
    return subprocess.run(["gh","api","-X","GET",f"orgs/{org}/memberships/{username}"], text=True, capture_output=True).returncode == 0

def has_pending(org: str, user: str) -> bool:
    cp = subprocess.run([
        "gh","api",f"orgs/{org}/invitations?per_page=100",
        "--jq",f".[] | select((.login? // \"\") == \"{user}\" or (.email? // \"\") == \"{user}\") | .id"
    ], text=True, capture_output=True)
    return bool(cp.stdout.strip())

def invite(org: str, uid: int, role: str) -> bool:
    body = {"invitee_id": uid, "role": role}
    cp = subprocess.run(
        ["gh","api","--method","POST",f"orgs/{org}/invitations",
         "-H","Content-Type: application/json","--input","-"],
        text=True, input=json.dumps(body), capture_output=True
    )
    if cp.returncode == 0: print("   ✓ invited"); return True
    print("   ✖ invite failed")
    if cp.stdout.strip(): print(cp.stdout.strip())
    if cp.stderr.strip(): print(cp.stderr.strip())
    return False

def main():
    ap = argparse.ArgumentParser(description="Invite students to a GitHub org (JSON body).")
    ap.add_argument("--org", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--role", default="direct_member", choices=["direct_member","admin"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gh_prechecks(args.org)
    students = load_students(Path(args.file))
    # de-dupe by username
    seen=set(); students=[s for s in students if not (s["username"] in seen or seen.add(s["username"]))]

    print(f"Inviting {len(students)} to '{args.org}' as '{args.role}'")
    ok=sk=fail=0
    for i,s in enumerate(students,1):
        name=s["name"] or s["username"]; u=s["username"]
        print(f"[{i}/{len(students)}] {name} ({u})")
        if "@" not in u and is_member(args.org,u): print("   … already member → skip"); sk+=1; continue
        if has_pending(args.org,u): print("   … pending invite → skip"); sk+=1; continue
        if args.dry_run: print("   [DRY] would invite"); ok+=1; continue
        uid=resolve_uid(u)
        if uid is None: print("   ✖ cannot resolve user id"); fail+=1; continue
        if invite(args.org, uid, args.role): ok+=1
        else: fail+=1
    print(f"Summary: ok={ok} skip={sk} fail={fail}")

if __name__ == "__main__":
    main()

# python3 invite_to_org.py --org DS-223-2025-Fall --file github_usernames.json --dry-run
