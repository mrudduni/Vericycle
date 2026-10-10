# Shaurya's work log (ChainTrack)

**Submission deadline:** _not confirmed yet. Ask Mrudduni and fill in._

## 2026-10-10 08:55 IST: setup

- Works: repo cloned, branch `shaurya/chaintrack` created, contract and solution read.
- Next: ledger library (canonical hash, writer, verify_chain, Merkle digest) with offline tests; Cedar policies; CDK Core stack.
- Blocked: the Claude GitHub app cannot see `mrudduni/OpenAEye` (Mrudduni must add the repo to her Claude app installation), so pushes wait. AWS login not done yet (needs Shaurya at a browser). WhatsApp number and collector sign-in method not decided.

## Third-party libraries and licences

| Library | Used in | Licence |
|---|---|---|
| cryptography | ledger signatures | Apache-2.0 / BSD-3-Clause |
| boto3 | AWS adapters | Apache-2.0 |
| cedarpy | Cedar policy tests | Apache-2.0 |
| pytest | tests | MIT |
