// Lazy-loaded: Amplify UI Authenticator (username + password), no self sign-up.
import { Authenticator, translations } from '@aws-amplify/ui-react';
import { I18n } from 'aws-amplify/utils';
import '@aws-amplify/ui-react/styles.css';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { configure, sessionFromToken } from '../lib/auth';
import { setSession } from '../lib/session';

I18n.putVocabularies(translations);
I18n.putVocabulariesForLanguage('hi', {
  'Sign In': 'साइन इन', 'Sign in': 'साइन इन', Username: 'यूज़रनेम', Password: 'पासवर्ड',
  'Enter your Username': 'अपना यूज़रनेम लिखें', 'Enter your Password': 'अपना पासवर्ड लिखें',
  'Forgot your password?': 'पासवर्ड भूल गए?', 'Incorrect username or password.': 'यूज़रनेम या पासवर्ड ग़लत है।',
});

function OnSignedIn() {
  const { t } = useTranslation();
  const [err, setErr] = useState(false);
  useEffect(() => {
    sessionFromToken().then((s) => (s ? setSession(s) : setErr(true)), () => setErr(true));
  }, []);
  return err ? <p className="error">⚠ {t('err.forbidden')}</p> : <p className="muted">…</p>;
}

export default function SignIn() {
  const { i18n } = useTranslation();
  const [ready, setReady] = useState(false);
  useEffect(() => { void configure().then(() => setReady(true)); }, []);
  useEffect(() => { I18n.setLanguage(i18n.language); }, [i18n.language]);
  if (!ready) return <p className="muted">…</p>;
  return (
    <Authenticator hideSignUp loginMechanisms={['username']}>
      {() => <OnSignedIn />}
    </Authenticator>
  );
}
