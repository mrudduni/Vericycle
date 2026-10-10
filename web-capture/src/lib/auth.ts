// Business-user sign-in with Cognito (username + password, SRP). Loaded lazily so the first
// download stays small. Without VITE_USER_POOL_ID (local dev) the demo-party picker is used instead.
import type { Role, Session } from './session';

export const POOL_ID = import.meta.env.VITE_USER_POOL_ID as string | undefined;
export const CLIENT_ID = import.meta.env.VITE_USER_POOL_CLIENT_ID as string | undefined;
export const COGNITO = Boolean(POOL_ID && CLIENT_ID);
const ROLES: Role[] = ['COLLECTOR', 'AGGREGATOR', 'RECYCLER', 'AUDITOR', 'PRODUCER'];

let configured: Promise<void> | null = null;
export function configure(): Promise<void> {
  if (!configured) {
    configured = import('aws-amplify').then(({ Amplify }) => {
      Amplify.configure({ Auth: { Cognito: { userPoolId: POOL_ID!, userPoolClientId: CLIENT_ID!, loginWith: { username: true } } } });
    });
  }
  return configured;
}

/** Current ID token (it carries custom:party_id and cognito:groups); refreshed by Amplify when needed. */
export async function idToken(): Promise<string | null> {
  if (!COGNITO) return null;
  await configure();
  const { fetchAuthSession } = await import('aws-amplify/auth');
  const s = await fetchAuthSession();
  return s.tokens?.idToken?.toString() ?? null;
}

export async function sessionFromToken(): Promise<Session | null> {
  if (!COGNITO) return null;
  await configure();
  const { fetchAuthSession } = await import('aws-amplify/auth');
  const p = (await fetchAuthSession()).tokens?.idToken?.payload as Record<string, unknown> | undefined;
  if (!p) return null;
  const groups = (p['cognito:groups'] as string[] | undefined) ?? [];
  const role = ROLES.find((r) => groups.includes(r));
  const party = p['custom:party_id'] as string | undefined;
  if (!role || !party) return null;
  return { party_id: party, role, label: `${p['cognito:username'] ?? party} · ${party}`, cognito: true };
}

export async function signOutCognito(): Promise<void> {
  if (!COGNITO) return;
  await configure();
  const { signOut } = await import('aws-amplify/auth');
  await signOut();
}
