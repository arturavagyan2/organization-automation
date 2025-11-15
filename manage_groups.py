#!/usr/bin/env python3
import argparse, json, re, subprocess, sys
from pathlib import Path

def run(cmd, *, input_text=None):
    return subprocess.run(cmd, text=True, input=input_text, capture_output=True)

def gh_ok(org: str):
    if run(["gh","auth","status"]).returncode != 0:
        print("Not authed; run `gh auth login`"); sys.exit(1)
    if run(["gh","api", f"orgs/{org}", "--jq", ".login"]).returncode != 0:
        print(f"Org '{org}' not accessible"); sys.exit(1)

def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "team"

def team_exists(org: str, slug: str) -> bool:
    return run(["gh","api", f"orgs/{org}/teams/{slug}"]).returncode == 0

def create_team(org: str, name: str, privacy="closed", description="") -> str:
    body = {"name": name, "privacy": privacy, "description": description}
    cp = run(["gh","api","--method","POST", f"orgs/{org}/teams",
              "-H","Content-Type: application/json","--input","-"],
             input_text=json.dumps(body))
    if cp.returncode != 0:
        print(f"✖ create team '{name}' failed:\n{cp.stderr or cp.stdout}"); sys.exit(1)
    data = json.loads(cp.stdout) if cp.stdout.strip() else {}
    return data["slug"]

def team_membership(org: str, slug: str, username: str) -> str | None:
    """Return 'member' or 'maintainer' if in team, otherwise None."""
    cp = run(["gh","api", f"orgs/{org}/teams/{slug}/memberships/{username}", "--jq", ".role"])
    if cp.returncode == 0 and cp.stdout.strip() in ("member","maintainer"):
        return cp.stdout.strip()
    return None

def add_to_team(org: str, slug: str, username: str, role="member") -> bool:
    body = {"role": role}  # "member" or "maintainer"
    cp = run(["gh","api","--method","PUT", f"orgs/{org}/teams/{slug}/memberships/{username}",
              "-H","Content-Type: application/json","--input","-"],
             input_text=json.dumps(body))
    if cp.returncode == 0:
        return True
    # Non-fatal: if user is not yet in org, GitHub will invite them automatically on team add
    print(f"  ! add_to_team {slug}:{username} failed: {cp.stderr or cp.stdout}".strip())
    return False

def load_students(path: Path):
    raw = path.read_text(encoding="utf-8")
    # tolerate trailing commas if present
    cleaned = re.sub(r',\s*([}\]])', r'\1', raw)
    data = json.loads(cleaned)
    rows = []
    for it in data:
        if not isinstance(it, dict): continue
        u = (it.get("username") or "").strip().lstrip("@")
        g = (it.get("group") or "").strip()
        n = (it.get("name") or "").strip()
        if u and g:
            rows.append({"name": n, "username": u, "group": g})
    if not rows:
        print("✖ No students with 'username' and 'group' found"); sys.exit(1)
    return rows

def main():
    ap = argparse.ArgumentParser(description="Create teams if missing and add members (students + instructors).")
    ap.add_argument("--org", required=True)
    ap.add_argument("--file", required=True, help="students file with fields: name, username, group")
    ap.add_argument("--instructors", required=True, help="comma-separated usernames to be in every team")
    ap.add_argument("--team-privacy", default="closed", choices=["closed","secret"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gh_ok(args.org)
    students = load_students(Path(args.file))

    # build group -> members mapping
    groups = {}
    for s in students:
        groups.setdefault(s["group"], []).append(s["username"])
    instr = [u.strip().lstrip("@") for u in args.instructors.split(",") if u.strip()]

    print(f"Found {len(groups)} groups; ensuring teams exist and memberships are set.")
    for i, (group_name, members) in enumerate(sorted(groups.items()), 1):
        team_name  = group_name        # display name
        team_slug  = slugify(group_name)  # team slug
        print(f"\n[{i}/{len(groups)}] Team '{team_name}' (slug: {team_slug})")

        # Check/create team
        if team_exists(args.org, team_slug):
            print("  • team exists")
        else:
            if args.dry_run:
                print("  • DRY: would create team")
            else:
                created_slug = create_team(args.org, team_name, privacy=args.team_privacy)
                print(f"  • created team (slug={created_slug})")

        # Ensure instructors present as maintainers
        for u in instr:
            role_now = team_membership(args.org, team_slug, u)
            if role_now == "maintainer":
                print(f"  • instructor {u}: already maintainer")
            elif role_now == "member":
                if args.dry_run:
                    print(f"  • DRY: would promote {u} to maintainer")
                else:
                    ok = add_to_team(args.org, team_slug, u, role="maintainer")
                    print(f"  • instructor {u}: promote to maintainer -> {'ok' if ok else 'fail'}")
            else:
                if args.dry_run:
                    print(f"  • DRY: would add instructor {u} as maintainer")
                else:
                    ok = add_to_team(args.org, team_slug, u, role="maintainer")
                    print(f"  • instructor {u}: add maintainer -> {'ok' if ok else 'fail'}")

        # Ensure students present as members
        for u in members:
            role_now = team_membership(args.org, team_slug, u)
            if role_now in ("member","maintainer"):
                print(f"  • {u}: already in team ({role_now})")
            else:
                if args.dry_run:
                    print(f"  • DRY: would add {u} as member")
                else:
                    ok = add_to_team(args.org, team_slug, u, role="member")
                    print(f"  • {u}: add member -> {'ok' if ok else 'fail'}")

    print("\nDone.")

if __name__ == "__main__":
    main()


# python3 manage_groups.py --org DS-223-2025-Fall --file github_usernames.json --instructors hovhannisyan91,arturavagyan2 --dry-run