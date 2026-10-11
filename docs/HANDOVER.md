# Handover: OpenAEye MVP

State as of 11 Oct 2026. Replaces the 10 Oct handover. Read `docs/team/CONTRACT.md`, then this file, then `docs/DEPLOY.md`.

## 1. Where things stand

**`prod` is deployed and working in account `206690614182`, region `ap-southeast-2` (Sydney).** Mrudduni and Shaurya agreed this contract change on 10 Oct (CONTRACT §2, §10). The old account 773870812969 was never activated.

| What | URL |
|---|---|
| Capture app | https://main.d2aof528zfa6ax.amplifyapp.com |
| Review dashboard | https://main.dgf1yym1lb668.amplifyapp.com |
| Capture API | https://m5mvi60sjd.execute-api.ap-southeast-2.amazonaws.com |
| Review API | https://kzztwu22mi.execute-api.ap-southeast-2.amazonaws.com |

Stacks: `OAE-Prod-Core`, `OAE-Prod-CaptureWeb`, `OAE-Prod-Capture` (ChainTrack); `OAE-Prod-ReviewWeb`, `OAE-Prod-Claims` (ClaimGuard). Stage `shaurya` also exists in the same account and region.

Demo users (col-118, col-207, col-330, agg-01, rec-01, rec-02, aud-01, prd-01) exist in the prod Cognito pool. Their passwords are only in `~/.openaeye_demo_users_prod.txt` on Shaurya's Mac.

## 2. Verified on real AWS (11 Oct)

- Ledger seeded through the real writer (8 batches, KMS-signed). `verify_chain` for B-0046 and the public `/verify/B-0042` both return `ok: true`.
- Acceptance table: `seed_claims.py --stage prod --ledger-stage prod` matches CONTRACT §8 for all nine claims (C-101 no flags and 82% coverage … C-108 no flags and 0%).
- Step Functions: a workflow run for C-104 succeeded with 1 flag.
- Verified Permissions (Cedar) through the review Lambda: auditor sees all 9 claims; PRD-01 and REC-01 see their 7; REC-02 sees C-106 and C-108; a collector sees none. Anonymous requests to `/claims` get 401.
- Presign: the owning recycler gets an upload URL; another recycler gets 403. The upload itself was not run, to keep demo data unchanged.
- Copilot: returns the deterministic cited explanation (Bedrock still pending). 1–2 s warm, about 22 s cold.
- Capture chat: a typed message returns a read-back draft through the deterministic reader.

Not yet verified: signing in through the web UIs with Cognito. Do this with the demo users before recording.

## 3. What the account blocks

The account belongs to an AWS organisation whose service control policy denies these. They will not start working.

| Service | Effect | What the code does |
|---|---|---|
| `ap-south-1` | Nothing can be deployed in Mumbai | Everything is in Sydney; the privacy page says so |
| Amazon Transcribe | No voice notes | Deployed with `-c voice=off` / `OAE_VOICE=off`: mic hidden, typed chat only |
| Amazon Textract | No weigh-slip/bill field reading | File is still hashed and stored; `extracted.unavailable` is set; rules return `INSUFFICIENT_EVIDENCE` |
| End User Messaging Social | No WhatsApp | Not deployed; the PWA's WhatsApp-style chat is the demo path |

**Bedrock** is different: on 10 Oct it said "account is being verified"; on 11 Oct it returned `ThrottlingException: Too many tokens per day`, so access exists but the new account's daily quota is exhausted or very low. Check Service Quotas → Amazon Bedrock for Nova Lite tokens per day and request an increase. When calls succeed, extraction and the copilot use Nova Lite automatically. Test it with the `converse` command in DEPLOY.md §0.

## 4. Fixes made during the handover (branch `shaurya/deploy-fixes`)

- Ported six unpushed ChainTrack deploy fixes from Shaurya's old local branch `integration/oct10`.
- Region moved to `ap-southeast-2` everywhere; `prod` is pinned there.
- Fallbacks for a Bedrock outage, missing Transcribe and missing Textract (with tests).
- Review API `/impact` returned 500 on AWS (an import of a module that boto3 does not ship). Fixed and tested.
- Copilot timed out at 29 s while Bedrock was denied. Added a fast-fail client, a 12 s budget and a 5-minute cool-down.
- Offline reader missed plural "batteries". Fixed, tested and redeployed; the live chat now reads "4 × lead-acid battery, about 120 kg (stated), from a driver".
- cdk-nag keys made safe when the account is unresolved at synth.

Tests: 117 ChainTrack, 60 ClaimGuard, all passing.

## 5. Next steps

1. Request a Bedrock quota increase for Nova Lite tokens per day (Service Quotas, ap-southeast-2).
2. Sign in to both web apps as the demo users; run the capture chat → confirm → transfer → intake flow, and the dashboard review flow.
3. Push `shaurya/deploy-fixes` and merge it to `main` (CONTRACT changes need both people; both agreed).
4. Budget alarms at $20, $50, $100.
5. Untrained-user test with at least 3 people; 3-minute video showing the console and deployed URLs; writeup from the README's "What is deployed, and what is not".
6. Once Bedrock clears: rerun a copilot question and a chat message to confirm `model_used: true`.

## 6. Gotchas

- The `Desktop/Work Work ` folder name ends in a space; quote paths.
- Python scripts using the `aws login` profile need `botocore[crt]`.
- `deploy_all.sh` exports short-lived credentials; a long run can outlive them. If a late step fails with "credentials … expired", rerun that step with `AWS_PROFILE=openaeye`.
- In zsh, `set -- $var` does not split words. Use a function with separate arguments.
- CDK needs `CDK_DEFAULT_ACCOUNT=206690614182` when run outside `deploy_all.sh`.
