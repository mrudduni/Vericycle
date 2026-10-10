"""Create the CONTRACT §8 business users in the stage's Cognito pool (username + password).

    python scripts/chaintrack/create_demo_users.py --stage shaurya [--profile openaeye]

Usernames are the party IDs in lower case (col-118, agg-01, rec-01, ...). Each gets a random strong
password, written ONLY to ~/.openaeye_demo_users_<stage>.txt (mode 600, outside the repo) and printed
once. Re-running resets the passwords. Handlers never get accounts.
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

USERS = [("COL-118", "COLLECTOR"), ("COL-207", "COLLECTOR"), ("COL-330", "COLLECTOR"), ("AGG-01", "AGGREGATOR"),
         ("REC-01", "RECYCLER"), ("REC-02", "RECYCLER"), ("AUD-01", "AUDITOR"), ("PRD-01", "PRODUCER")]


def password() -> str:
    # Readable on a phone keyboard: no look-alikes; still meets the 12+ / upper / lower / digit / symbol policy.
    a = "ABCDEFGHJKMNPQRSTUVWXYZ", "abcdefghjkmnpqrstuvwxyz", "23456789", "-_!@"
    core = [secrets.choice(x) for x in a] + [secrets.choice("".join(a[:3])) for _ in range(10)]
    secrets.SystemRandom().shuffle(core)
    return "".join(core)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    ap.add_argument("--region", default="ap-south-1")
    a = ap.parse_args(argv)
    if a.stage == "mrudduni":
        ap.error("never touch Mrudduni's stage")
    import boto3
    sess = boto3.Session(profile_name=a.profile, region_name=a.region)
    pool = sess.client("ssm").get_parameter(Name=f"/openaeye/{a.stage}/auth/user-pool-id")["Parameter"]["Value"]
    idp = sess.client("cognito-idp")
    out = Path.home() / f".openaeye_demo_users_{a.stage}.txt"
    lines = []
    for party, role in USERS:
        user = party.lower()
        pw = password()
        try:
            idp.admin_create_user(UserPoolId=pool, Username=user, MessageAction="SUPPRESS",
                                  UserAttributes=[{"Name": "custom:party_id", "Value": party}])
        except idp.exceptions.UsernameExistsException:
            pass
        idp.admin_set_user_password(UserPoolId=pool, Username=user, Password=pw, Permanent=True)
        idp.admin_add_user_to_group(UserPoolId=pool, Username=user, GroupName=role)
        lines.append(f"{user:8} {role:10} {pw}")
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nSaved to {out} (not in git). Share passwords only with the team.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
