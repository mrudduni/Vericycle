import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { getClaim, postReview, runCheck } from '../lib/api';
import { useT } from '../lib/i18n';
import { useSession } from '../lib/session';
import type { ClaimDetail as Detail, Evidence, ReviewAction } from '../lib/types';
import RuleCard from '../components/RuleCard';
import ScoreBars from '../components/Scores';
import { Err, fmtDate, fmtDateTime, productLabel } from '../components/ui';

const LineageView = lazy(() => import('../components/Lineage'));

/** The single place this sentence lives. */
export const DISCLAIMER = 'A claim that passes is consistent with the available data. It is not certified as genuine.';

const ACTION_WORD: Record<ReviewAction, string> = { ACCEPT: 'Accepted', REQUEST_EVIDENCE: 'Requested evidence', ESCALATE: 'Escalated', RECYCLER_RESPONSE: 'Recycler response' };

function kv(o: Record<string, unknown>) {
  const e = Object.entries(o).filter(([k]) => !k.startsWith('_'));
  return e.length ? (
    <dl className="kv">{e.map(([k, v]) => (<div key={k}><dt>{k}</dt><dd className="mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>))}</dl>
  ) : <p className="small muted">None recorded.</p>;
}

function EvidenceItem({ ev }: { ev: Evidence }) {
  return (
    <li id={`evidence-${ev.evidence_id}`} className="ev">
      <div className="row"><strong className="mono">{ev.evidence_id}</strong><span className="chip">{ev.kind.replace(/_/g, ' ')}</span>{ev.batch_id && <span className="chip mono">{ev.batch_id}</span>}</div>
      <p className="small muted">Received {fmtDateTime(ev.received_at_server)}</p>
      <div className="two">
        <div><h4>Extracted values</h4>{kv(ev.extracted)}</div>
        <div><h4>EXIF</h4>{kv(ev.exif)}</div>
      </div>
      <p className="small muted mono">sha256 {ev.sha256?.slice(0, 16) ?? '—'}{ev.phash ? ` · pHash ${ev.phash}` : ''}</p>
    </li>
  );
}

export default function ClaimDetail({ id }: { id: string }) {
  const t = useT();
  const session = useSession();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [resp, setResp] = useState('');
  const [recView, setRecView] = useState(session?.role === 'RECYCLER');
  const [showLineage, setShowLineage] = useState(true);

  const load = useCallback(() => { getClaim(id).then(setD, setErr); }, [id]);
  useEffect(() => { setD(null); setErr(null); load(); }, [load]);
  useEffect(() => { if (session?.role === 'RECYCLER') setRecView(true); }, [session?.role]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr(null);
    try { await fn(); await getClaim(id).then(setD); } catch (e) { setErr(e as Error); } finally { setBusy(false); }
  };
  const isAuditor = session?.role === 'AUDITOR';
  const review = (a: ReviewAction, text: string, clear: () => void) => act(async () => { await postReview(id, a, text); clear(); });

  if (err && !d) return <main><a href="#/">{t('back')}</a><Err e={err} /></main>;
  if (!d) return <main><p className="muted" role="status">{t('loading')}</p></main>;
  const { claim, run } = d;
  const reviews = [...d.reviews].sort((a, b) => b.seq - a.seq);
  const rules = run?.rule_results ?? [];

  return (
    <main className="detail">
      <p className="noprint"><a href="#/">&larr; {t('back')}</a></p>
      <header className="dhead">
        <div>
          <h2 className="mono">{claim.claim_id}</h2>
          <p className="muted">{productLabel(claim.product)} · {claim.recycler_party_id} · {fmtDate(claim.period_start)} to {fmtDate(claim.period_end)}</p>
          {run && <p className="small muted">Last run {fmtDateTime(run.ran_at)} · {run.run_id}</p>}
        </div>
        <div className="actions noprint">
          {isAuditor && <button className="btn" disabled={busy} onClick={() => act(() => runCheck(id, d?.run?.ran_at))}>{busy ? t('running') : t('runClaimGuard')}</button>}
          <button className="btn secondary" onClick={() => window.print()}>{t('print')}</button>
          {session?.role !== 'RECYCLER' && (
            <label className="toggle"><input type="checkbox" checked={recView} onChange={(e) => setRecView(e.target.checked)} /> {t('recyclerView')}</label>
          )}
        </div>
      </header>
      <Err e={err} />
      {recView && (
        <div className="callout recview" role="note">
          <strong>{t('recyclerView')}.</strong> This is what the recycler sees: the same rule results, sources and review trail, without the reviewer controls.
        </div>
      )}

      {run ? <ScoreBars scores={run.scores} /> : <p className="callout">ClaimGuard has not run on this claim yet. {isAuditor && 'Use Run ClaimGuard.'}</p>}
      <p className="disclaimer">{DISCLAIMER}</p>

      <h2>{t('ruleResults')}</h2>
      <div className="rules">{rules.map((r) => <RuleCard key={r.rule_id} r={r} sources={d.sources} />)}</div>

      <h2>{t('evidence')}</h2>
      {d.evidence.length ? <ul className="evlist">{d.evidence.map((e) => <EvidenceItem key={e.evidence_id} ev={e} />)}</ul> : <p className="muted">No evidence attached to this claim.</p>}

      <h2>{t('batches')}</h2>
      {d.lineage.nodes.length > 0 && (
        <button className="btn secondary noprint" aria-expanded={showLineage} onClick={() => setShowLineage((x) => !x)}>{showLineage ? 'Hide' : 'Show'} lineage</button>
      )}
      {showLineage && <Suspense fallback={<p className="muted">{t('loading')}</p>}><LineageView lineage={d.lineage} /></Suspense>}

      <h2>{t('trail')}</h2>
      {reviews.length ? (
        <ol className="trail">
          {reviews.map((r) => (
            <li key={r.seq}>
              <strong>{ACTION_WORD[r.action]}</strong> <span className="small muted">by {r.by_party_id} ({r.by_role.toLowerCase()}) · {fmtDateTime(r.at)}</span>
              {r.note && <p>{r.note}</p>}
            </li>
          ))}
        </ol>
      ) : <p className="muted">{t('noTrail')}</p>}

      {isAuditor && !recView && (
        <section className="review noprint" aria-label="Reviewer actions">
          <label htmlFor="note">{t('note')}</label>
          <textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="row">
            <button className="btn green" disabled={busy} onClick={() => review('ACCEPT', note, () => setNote(''))}>{t('accept')}</button>
            <button className="btn secondary" disabled={busy} onClick={() => review('REQUEST_EVIDENCE', note, () => setNote(''))}>{t('request')}</button>
            <button className="btn secondary" disabled={busy} onClick={() => review('ESCALATE', note, () => setNote(''))}>{t('escalate')}</button>
          </div>
        </section>
      )}
      {recView && (
        <section className="review noprint" aria-label="Recycler response">
          <label htmlFor="resp">{t('respond')}</label>
          <textarea id="resp" value={resp} onChange={(e) => setResp(e.target.value)} disabled={session?.role !== 'RECYCLER'} />
          {session?.role !== 'RECYCLER' && <p className="small muted">Only the owning recycler can send a response. Switch the role to REC-01 to try it.</p>}
          <button className="btn" disabled={busy || session?.role !== 'RECYCLER' || !resp.trim()} onClick={() => review('RECYCLER_RESPONSE', resp, () => setResp(''))}>{t('sendResponse')}</button>
        </section>
      )}
    </main>
  );
}
