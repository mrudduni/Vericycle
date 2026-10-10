import { lazy, Suspense } from 'react';
import { COGNITO, signOutCognito } from './lib/auth';
import { toggleLang, useT } from './lib/i18n';
import { usePath } from './lib/router';
import { DEV_AUTH, DEV_USERS, setSession, useSession } from './lib/session';
import { SourceDrawerHost } from './components/ui';
import ClaimList from './screens/ClaimList';
import ClaimDetail from './screens/ClaimDetail';
import Impact from './screens/Impact';

const SignIn = lazy(() => import('./screens/SignIn'));

export default function App() {
  const t = useT();
  const path = usePath();
  const s = useSession();
  const m = /^\/claims\/([^/]+)$/.exec(path);
  const isImpact = path === '/impact';

  let screen: JSX.Element;
  if (isImpact) screen = <Impact />;
  else if (!s) {
    screen = COGNITO
      ? <main><h2>Sign in to review claims</h2><Suspense fallback={<p className="muted">…</p>}><SignIn /></Suspense></main>
      : <main><p className="error">Sign-in is not configured. Set VITE_USER_POOL_ID and VITE_USER_POOL_CLIENT_ID, or VITE_DEV_AUTH=1 for local use.</p></main>;
  } else if (m) screen = <ClaimDetail key={m[1]} id={decodeURIComponent(m[1])} />;
  else screen = <ClaimList />;

  return (
    <SourceDrawerHost>
      <div className="app">
        <header className="top noprint">
          <a className="brand" href="#/"><h1>{t('app')}</h1></a>
          <nav aria-label="Main">
            <a href="#/" aria-current={!isImpact ? 'page' : undefined}>{t('claims')}</a>
            <a href="#/impact" aria-current={isImpact ? 'page' : undefined}>{t('impact')}</a>
          </nav>
          <span className="spacer" />
          {DEV_AUTH && s && (
            <label className="devpick">{t('role')}
              <select value={s.party_id} onChange={(e) => setSession(DEV_USERS.find((u) => u.party_id === e.target.value) ?? s)}>
                {DEV_USERS.map((u) => <option key={u.party_id} value={u.party_id}>{u.label}</option>)}
              </select>
            </label>
          )}
          {!DEV_AUTH && s && <span className="small who">{s.label}</span>}
          <button onClick={toggleLang}>{t('lang')}</button>
          {!DEV_AUTH && s && <button onClick={() => { void signOutCognito().finally(() => setSession(null)); }}>{t('signOut')}</button>}
        </header>
        {screen}
      </div>
    </SourceDrawerHost>
  );
}
