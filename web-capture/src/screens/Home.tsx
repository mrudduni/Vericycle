import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { DEMO_PARTIES, getSession, setSession } from '../lib/session';
import { COGNITO } from '../lib/auth';
import { Link } from '../components/ui';
import { Icon, Mark, type IconName } from '../components/Icon';

const SignIn = lazy(() => import('./SignIn'));
const initials = (s: string) => s.replace(/[^A-Z0-9]/g, '').slice(0, 3);

function Welcome({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <main>
      <div className="welcome">
        <Mark size={64} />
        <h2>{t('home.welcome')}</h2>
        <p>{t('home.welcomeBody')}</p>
      </div>
      {children}
      <div className="linkrow">
        <Link to="/open"><Icon name="shield" size={17} />{t('home.verifyLink')}</Link>
        <Link to="/privacy"><Icon name="lock" size={17} />{t('home.privacy')}</Link>
      </div>
    </main>
  );
}

export default function Home() {
  const { t } = useTranslation();
  const s = getSession();
  if (!s && COGNITO) {
    return (
      <Welcome>
        <div className="panel">
          <h3 style={{ marginBottom: 14 }}>{t('signIn')}</h3>
          <Suspense fallback={<div className="skel" style={{ height: 240 }} />}><SignIn /></Suspense>
        </div>
      </Welcome>
    );
  }
  if (!s) {
    return (
      <Welcome>
        <h3 style={{ margin: '26px 0 6px' }}>{t('chooseAccount')}</h3>
        <p className="small muted" style={{ marginTop: 0 }}>{t('demoNote')}</p>
        <div className="grid">
          {DEMO_PARTIES.map((p) => (
            <button key={p.party_id} className="tile" onClick={() => setSession(p)}>
              <span className="ic-wrap" style={{ fontWeight: 750, fontSize: 13 }}>{initials(p.party_id)}</span>{p.label}
            </button>
          ))}
        </div>
      </Welcome>
    );
  }
  const tiles: [string, IconName, string, string][] = [];
  if (['AGGREGATOR', 'RECYCLER', 'COLLECTOR'].includes(s.role)) tiles.push(['/scan', 'qr', t('home.scan'), t('home.scanSub')]);
  tiles.push(['/open', 'box', t('home.batch'), t('home.batchSub')], ['/privacy', 'lock', t('home.privacy'), t('home.privacySub')]);
  return (
    <main>
      <div className="hello">
        <span className="avatar" aria-hidden="true">{initials(s.party_id)}</span>
        <div><h2>{t('home.hello')}</h2><p>{s.label} · {t(`home.role.${s.role}`)}</p></div>
      </div>
      {s.role === 'COLLECTOR' && (
        <Link to="/chat" className="hero-card">
          <span className="bub"><Icon name="chat" /></span>
          <strong>{t('home.chat')}</strong>
          <span>{t('home.chatSub')}</span>
          <span className="go">{t('home.start')}<Icon name="arrow" size={18} /></span>
        </Link>
      )}
      <div className="grid" style={{ marginTop: 14 }}>
        {tiles.map(([to, ic, label, sub]) => (
          <Link key={to} to={to} className="tile">
            <span className="ic-wrap"><Icon name={ic} /></span>
            <span>{label}<span className="sub">{sub}</span></span>
            <Icon name="arrow" className="chev" size={18} />
          </Link>
        ))}
      </div>
    </main>
  );
}
