import { useTranslation } from 'react-i18next';
import { DEMO_PARTIES, getSession, setSession } from '../lib/session';
import { Link } from '../components/ui';

export default function Home() {
  const { t } = useTranslation();
  const s = getSession();
  if (!s) {
    return (
      <main>
        <h2>{t('chooseAccount')}</h2>
        <p className="small muted">{t('demoNote')}</p>
        <div className="grid">
          {DEMO_PARTIES.map((p) => <button key={p.party_id} className="tile" onClick={() => setSession(p)}>{p.label}</button>)}
        </div>
        <p style={{ marginTop: 24 }}><Link to="/privacy">{t('home.privacy')}</Link></p>
      </main>
    );
  }
  const tiles: [string, string, string][] = [];
  if (s.role === 'COLLECTOR') tiles.push(['/chat', '💬', t('home.chat')]);
  if (['AGGREGATOR', 'RECYCLER', 'COLLECTOR'].includes(s.role)) tiles.push(['/scan', '📷', t('home.scan')]);
  tiles.push(['/open', '📦', t('home.batch')], ['/privacy', '🔒', t('home.privacy')]);
  return (
    <main>
      <p className="muted small">{s.label}</p>
      <div className="grid">
        {tiles.map(([to, ic, label]) => <Link key={to} to={to} className="tile"><span className="ic" aria-hidden="true">{ic}</span>{label}</Link>)}
      </div>
    </main>
  );
}
