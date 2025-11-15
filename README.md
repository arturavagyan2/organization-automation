1) Extract usernames

In the e-learning homework submissions page, open DevTools → Console, paste the JS from extract_username_from_browser.txt.
Save output as github_usernames.json:

2) Invite to org

Dry-run:
```bash
python3 invite_to_org.py --org DS-223-2025-Fall --file github_usernames.json --dry-run
```


Execute:
```bash
python3 invite_to_org.py --org DS-223-2025-Fall --file github_usernames.json
```

3) Create teams & add members

(Requires group in the JSON for each student. If needed, first merge from your sheet using assign_groups.py.)
```bash
python3 manage_groups.py \
  --org DS-223-2025-Fall \
  --file github_usernames.json \
  --instructors hovhannisyan91,arturavagyan2
```

Verify
```bash
gh api orgs/DS-223-2025-Fall/invitations --jq '.[].login'
gh api orgs/DS-223-2025-Fall/members --jq '.[].login'
gh api orgs/DS-223-2025-Fall/teams --jq '.[].slug'
```
