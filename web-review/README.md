# web-review

OpenAEye ClaimGuard review dashboard (auditors, producers, recyclers). React 18, Vite, TypeScript, plain SVG/CSS. No chart libraries.

Screens: claim list (`#/`), claim detail (`#/claims/<id>`), public impact panel (`#/impact`, no sign-in).

## Run locally

```
# 1. API (from the repo root; pre-runs all 9 demo claims)
services/claimguard/.venv/Scripts/python.exe scripts/claimguard/local_review_api.py --port 8788
# 2. Dashboard
cd web-review
cp .env.example .env.local      # VITE_DEV_AUTH=1 shows a role picker (AUD-01, REC-01, PRD-01)
npm install
npm run dev                     # http://localhost:5174
```

## Build, budget, test

```
npm run build        # tsc --noEmit && vite build
npm run size         # fails if initial JS is over 150 KB gzipped (Amplify sign-in and lineage view are lazy)
npm run preview      # http://localhost:4173
node ../tests/claimguard/e2e/review_flow.mjs   # needs the API and preview running; set PLAYWRIGHT_PATH / CHROME_PATH if needed
```

## Configuration (build-time env)

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Review API base URL, no trailing slash |
| `VITE_DEV_AUTH` | `1` for local use only: sends `X-Dev-Role` / `X-Dev-Party` headers, never set in prod |
| `VITE_USER_POOL_ID`, `VITE_USER_POOL_CLIENT_ID` | Cognito pool; sign-in uses the Amplify UI Authenticator and sends the ID token |

## Deploy

Build with the stage values (`VITE_API_URL` from the ReviewApi stack output, pool ids from SSM) and upload `dist/` to Amplify Hosting (or any static host). Routing is hash based, so no rewrite rules are needed.

## Notes

- Three scores are always shown separately; there is no combined score.
- Hindi toggle translates static UI labels only; server text is shown as received.
- Print the claim report with the Print button (print stylesheet hides controls).
