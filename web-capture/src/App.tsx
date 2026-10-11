import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { match, navigate, usePath } from './lib/router';
import { getSession, setSession } from './lib/session';
import { setLang } from './i18n';
import { signOutCognito } from './lib/auth';
import { QueueBanner } from './components/ui';
import { Icon, Mark } from './components/Icon';
import Home from './screens/Home';
import Chat from './screens/Chat';
import Batch, { OpenBatch } from './screens/Batch';
import EventForm from './screens/EventForm';
import Scan from './screens/Scan';
import { Confirm, Privacy, Receipt, Verify } from './screens/Public';

export default function App() {
  const { t, i18n } = useTranslation();
  const path = usePath();
  const [, force] = useState(0);
  useEffect(() => {
    const on = () => force((x) => x + 1);
    window.addEventListener('oae-session', on);
    return () => window.removeEventListener('oae-session', on);
  }, []);
  const s = getSession();
  const isPublic = /^\/(r|c|v)\//.test(path);

  let screen: JSX.Element, title = t('app');
  let m;
  if ((m = match(path, '/r/:token'))) screen = <Receipt token={m.token} />;
  else if ((m = match(path, '/c/:token'))) screen = <Confirm token={m.token} />;
  else if ((m = match(path, '/v/:id'))) screen = <Verify id={m.id} />;
  else if (path === '/privacy') screen = <Privacy />;
  else if (path === '/open') screen = <OpenBatch />;
  else if (!s) screen = <Home />;
  else if (path === '/chat') { screen = <Chat />; title = t('home.chat'); }
  else if (path === '/scan') screen = <Scan />;
  else if ((m = match(path, '/b/:id/:type'))) screen = <EventForm id={m.id} type={m.type} />;
  else if ((m = match(path, '/b/:id'))) screen = <Batch id={m.id} />;
  else screen = <Home />;

  return (
    <div className="app">
      <header className="top">
        {path !== '/' && !path.startsWith('/c/')
          ? <button className="back" aria-label="Back" onClick={() => (history.length > 1 ? history.back() : navigate('/'))}><Icon name="back" size={22} /></button>
          : <Mark size={32} />}
        <h1>{title}</h1>
        {!path.startsWith('/c/') && <button onClick={() => setLang(i18n.language === 'hi' ? 'en' : 'hi')} aria-label="Switch language"><Icon name="globe" size={17} />{t('lang')}</button>}
        {s && !isPublic && (
          <button aria-label={t('signOut')} title={t('signOut')} onClick={() => { void signOutCognito().finally(() => { setSession(null); navigate('/'); }); }}>
            <Icon name="out" size={17} />
          </button>
        )}
      </header>
      {!isPublic && <QueueBanner />}
      {screen}
    </div>
  );
}
