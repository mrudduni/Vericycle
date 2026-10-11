import { lazy, Suspense } from 'react';
import { COGNITO, signOutCognito } from './lib/auth';
import { toggleLang, useT } from './lib/i18n';
import { usePath } from './lib/router';
import { DEV_AUTH, DEV_USERS, setSession, useSession } from './lib/session';
import { SourceDrawerHost } from './components/ui';
import { Icon, Mark } from './components/Icon';
import ClaimList from './screens/ClaimList';
import ClaimDetail from './screens/ClaimDetail';
import Impact from './screens/Impact';
import Landing, { CAPTURE_WEB } from './screens/Landing';

const SignIn = lazy(() => import('./screens/SignIn'));

function SignInPage() {
  const t = useT();
  if (!COGNITO) {
    return <main><p className="error">Sign-in is not configured. Set VITE_USER_POOL_ID and VITE_USER_POOL_CLIENT_ID, or VITE_DEV_AUTH=1 for local use.</p></main>;
  }
  return (
    <div className="signin">
      <aside className="side">
        <span className="eyebrow">ClaimGuard review</span>
        <h2>Every flag shows its numbers, its evidence and its source.</h2>
        <p>Sign in as an auditor, recycler or producer to see the claims you are allowed to read.</p>
        <ul>
          <li><Icon name="shield" /> Access is decided per claim by Cedar policies, evaluated in AWS (AVP).</li>
          <li><Icon name="scale" /> Nine deterministic rules. AI explains; it never raises or clears a flag.</li>
          <li><Icon name="link" /> Custody records are hash-chained and signed with AWS KMS.</li>
        </ul>
      </aside>
      <div className="form">
        <div>
          <span className="eyebrow">{t('app')}</span>
          <h2>{t('signIn')}</h2>
          <p className="muted" style={{ marginTop: 0, marginBottom: 24 }}>{t('signInHint')}</p>
          <Suspense fallback={<div className="skel" style={{ height: 260 }} />}><SignIn /></Suspense>
        </div>
      </div>
    </div>
  );
}

const initials = (s: string) => s.replace(/[^A-Z0-9]/g, '').slice(0, 3) || '•';

export default function App() {
  const t = useT();
  const path = usePath();
  const s = useSession();
  const m = /^\/claims\/([^/]+)$/.exec(path);
  const isImpact = path === '/impact';
  const isLanding = path === '/welcome' || (!s && path === '/');

  let screen: JSX.Element;
  if (isLanding) screen = <Landing />;
  else if (isImpact) screen = <Impact />;
  else if (!s) screen = <SignInPage />;
  else if (m) screen = <ClaimDetail key={m[1]} id={decodeURIComponent(m[1])} />;
  else screen = <ClaimList />;

  return (
    <SourceDrawerHost>
      <div className={`app ${isLanding ? 'landing' : ''}`}>
        <header className="top noprint">
          <a className="brand" href={s ? '#/' : '#/welcome'} aria-label="OpenAEye home">
            <Mark size={34} />
            <span><span className="word">Open<em>AE</em>ye</span><span className="sub">{s ? 'ClaimGuard review' : t('tagline')}</span></span>
          </a>
          <nav aria-label="Main">
            {s && <a href="#/" aria-current={!isImpact && !isLanding ? 'page' : undefined}><Icon name="layers" size={17} />{t('claims')}</a>}
            <a href="#/impact" aria-current={isImpact ? 'page' : undefined}><Icon name="leaf" size={17} />{t('impact')}</a>
            <a href="#/welcome" aria-current={isLanding ? 'page' : undefined}><Icon name="eye" size={17} />{t('about')}</a>
          </nav>
          <span className="spacer" />
          {CAPTURE_WEB && !s && <a className="tbtn" href={CAPTURE_WEB} target="_blank" rel="noreferrer">{t('collectorApp')} <Icon name="ext" size={15} /></a>}
          <button className="tbtn" onClick={toggleLang} aria-label="Switch language"><Icon name="globe" size={16} />{t('lang')}</button>
          {DEV_AUTH && s && (
            <label className="devpick">{t('role')}
              <select value={s.party_id} onChange={(e) => setSession(DEV_USERS.find((u) => u.party_id === e.target.value) ?? s)}>
                {DEV_USERS.map((u) => <option key={u.party_id} value={u.party_id}>{u.label}</option>)}
              </select>
            </label>
          )}
          {!DEV_AUTH && s && (
            <span className="who">
              <span className="avatar" aria-hidden="true">{initials(s.party_id)}</span>
              <span className="meta"><strong>{s.party_id}</strong><span className="role">{s.role.toLowerCase()}</span></span>
            </span>
          )}
          {!DEV_AUTH && s && (
            <button className="tbtn" onClick={() => { void signOutCognito().finally(() => { setSession(null); location.hash = '/welcome'; }); }}>
              <Icon name="out" size={16} />{t('signOut')}
            </button>
          )}
          {!s && path !== '/signin' && <a className="btn" href="#/signin" style={{ minHeight: 40 }}>{t('signIn')}<Icon name="arrow" size={16} /></a>}
        </header>
        {screen}
        <footer className="foot noprint">
          <span>{t('footer')}</span>
          <span>{t('footerData')}</span>
        </footer>
      </div>
    </SourceDrawerHost>
  );
}
