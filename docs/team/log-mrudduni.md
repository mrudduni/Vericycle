# Mrudduni build log

## 2026-10-10

- Set up: AWS CLI v2 extracted (no admin rights available; used
  `msiexec /a` administrative extract to `%LOCALAPPDATA%\AWSCLIV2`
  instead of the normal installer, which failed with Error 1925 —
  insufficient privileges). `uv` and AWS CDK CLI installed cleanly.
  Signed in with `aws login` (console-credential flow); `sts
  get-caller-identity` confirms account `773870812969`.
- **Blocked:** `aws cloudformation describe-stacks` (and likely any
  CloudFormation/CDK call) returns `OptInRequired: The AWS Access Key Id
  needs a subscription for the service`. This usually means the account
  itself hasn't finished activation (billing/signup not fully complete)
  rather than a permissions problem. CDK bootstrap in `ap-south-1` is
  blocked on this. **Needs Mrudduni to check the account's billing/signup
  status in the AWS console before any `cdk deploy` can run.**
- Branch `mrudduni/claimguard` created and pushed.
- Built the whole offline rule engine (services/claimguard/), with zero
  AWS imports, matching docs/team/CONTRACT.md:
  - `model.py`: every enum and dataclass from CONTRACT §3/§5/§7, plus the
    per-field and per-event confirmation-status logic.
  - `sources.py` + `data/sources.yaml`: P3 discipline ("no source, no
    rule"). Real citations where I could trace them to
    problem_statement.md; everything else marked `DEMO_VALUE` with a note
    on what to verify before the demo (lead fraction, energy bands, IPCC
    GWP values — I found secondary-source numbers by web search but have
    not read the primary IPCC AR6 table, so they stay DEMO_VALUE on
    purpose).
  - `solar.py`: NOAA solar position algorithm, implemented and verified
    against Hapur 16 June 2025: sunset matches the published ~19:19 IST
    within 15 seconds (using the standard refraction+semidiameter
    convention), civil dusk within 15 seconds, nautical dusk within 35
    seconds. One correction to CONTRACT/SOLUTION: the specific degree
    figures "-7.0° at sunset+29min" and "-12.6° at sunset+60min" in
    SOLUTION.md section 21 are approximate/hand-rounded; my algorithm
    gives -6.4° and -12.1° at those exact offsets from the *standard*
    sunset instant. Close enough to keep the "about -7, about -12.6"
    language honest, but not exact to a tenth of a degree. Doesn't affect
    any rule outcome.
  - Rules R1 through R8, `engine.py`, `scores.py` (three scores, never
    blended).
  - `scripts/claimguard/generate_sample_data.py`: deterministic generator
    for facilities.json, the ledger fixture, and all 9 claims.
  - 24 tests, all passing: the full acceptance table from CONTRACT §8 (10
    tests) plus unit tests for R1 boundaries, the R2 mass-balance property
    test, R4 impossible order, R5 solar accuracy, R7 GSTIN check digit
    (validated against a known real-world test vector), sources
    discipline, the refrigerant-claim type guard, and a prompt-injection
    sanity check.
- **One data correction worth flagging:** SOLUTION.md's Journey A example
  ("4 batteries, about 80 kg") implies 20 kg per battery, which can't be
  right if 20 kg is already the *lead content alone* per battery
  (Newslaundry's figure). Demo data uses ~30 kg per whole battery instead,
  noted in `data/sources.yaml`.
- Not started yet: CDK stacks (blocked on the OptInRequired issue above),
  Textract evidence processor, review dashboard, copilot.

**What works now:** the full offline rule engine and acceptance test, 24/24
green, pushed to `mrudduni/claimguard`.

**What's next:** fix the AWS account issue, then CDK (`Claims`,
`ClaimGuard`, `ReviewApi` stacks) and deploy to stage `mrudduni`.

**Blocked on:** the AWS account's `OptInRequired` error — needs your
attention in the console before I can deploy anything.
