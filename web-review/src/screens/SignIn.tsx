// Lazy-loaded: Amplify UI Authenticator (username + password), no self sign-up.
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useEffect, useState } from 'react';
import { configure, sessionFromToken } from '../lib/auth';
import { setSession } from '../lib/session';

function OnSignedIn() {
  const [err, setErr] = useState(false);
  useEffect(() => { sessionFromToken().then((s) => (s ? setSession(s) : setErr(true)), () => setErr(true)); }, []);
  return err ? <p className="error" role="alert">This account has no review role (AUDITOR, RECYCLER or PRODUCER).</p> : <p className="muted">…</p>;
}

export default function SignIn() {
  const [ready, setReady] = useState(false);
  useEffect(() => { void configure().then(() => setReady(true)); }, []);
  if (!ready) return <p className="muted">…</p>;
  return <Authenticator hideSignUp loginMechanisms={['username']}>{() => <OnSignedIn />}</Authenticator>;
}
