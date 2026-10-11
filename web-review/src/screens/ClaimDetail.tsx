import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { getClaim, postReview, runCheck } from '../lib/api';
import { useT } from '../lib/i18n';
import { useSession } from '../lib/session';
import type { ClaimDetail as Detail, Evidence, ReviewAction, RuleResult } from '../lib/types';
import RuleCard from '../components/RuleCard';
import ScoreBars from '../components/Scores';
import { Err, fmtDate, fmtDateTime, productLabel } from '../components/ui';
import { Icon, type IconName } from '../components/Icon';
import { productIcon } from './ClaimList';

const LineageView = lazy(() => import('../components/Lineage'));

/** The single place this sentence lives. */
export const DISCLAIMER = 'A claim that passes is consistent with the available data. It is not certified as genuine.';

const ACTION_WORD: Record<ReviewAction, string> = { ACCEPT: 'Accepted', REQUEST_EVIDENCE: 'Requested evidence', ESCALATE: 'Escalated', RECYCLER_RESPONSE: 'Recycler response' };
const EV_ICON: Record<string, IconName> = { PHOTO: 'camera', WEIGH_SLIP: 'scale', INVOICE: 'file', POWER_BILL: 'bolt' };
const rank = (r: RuleResult) => (r.outcome === 'FLAG' ? (r.severity === 'HARD' ? 0 : 1) : r.outcome === 'INSUFFICIENT_EVIDENCE' ? 2 : r.outcome === 'INCONCLUSIVE' ? 3 : 4);

function kv(o: Record<string, unknown>) {
  const e = Object.entries(o).filter(([k]) => !k.startsWith('_'));
  return e.length ? (
    <dl className="kv">{e.map(([k, v]) => (<div key={k}><dt>{k}</dt><dd className="mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>))}</dl>
  ) : <p className="small muted" style={{ margin: 0 }}>None recorded.</p>;
}

function EvidenceItem({ ev }: { ev: Evidence }) {
  return (
    <li id={`evidence-${ev.evidence_id}`} className="ev">
      <div className="row" style={{ gap: 12 }}>
        <span className="evicon"><Icon name={EV_ICON[ev.kind] ?? 'file'} /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="row"><strong className="mono">{ev.evidence_id}</strong><span className="chip">{ev.kind.replace(/_/g, ' ')}</span>{ev.batch_id && <span className="chip mono">{ev.batch_id}</span>}</div>
          <p className="small muted" style={{ margin: '2px 0 0' }}>Received {fmtDateTime(ev.received_at_server)}</p>
        </div>
      </div>
      <div className="two">
        <div><h4>Extracted values</h4>{kv(ev.extracted)}</div>
        <div><h4>EXIF</h4>{kv(ev.exif)}</div>
      </div>
      <p className="small muted mono" style={{ marginBottom: 0 }}>sha256 {ev.sha256?.slice(0, 16) ?? '—'}{ev.phash ? ` · pHash ${ev.phash}` : ''}</p>
    </li>
  );
}

function Verdict({ rules }: { rules: RuleResult[] | null }) {
  const t = useT();
  const hard = rules?.filter((r) => r.outcome === 'FLAG' && r.severity === 'HARD').length ?? 0;
  const soft = rules?.filter((r) => r.outcome === 'FLAG' && r.severity !== 'HARD').length ?? 0;
  const kind = !rules ? 'ok' : hard ? 'hard' : soft ? 'soft' : 'ok';
  const icon: IconName = kind === 'hard' ? 'alert' : kind === 'soft' ? 'help' : 'check';
  const title = !rules ? t('vNone') : hard ? t('vHard') : soft ? t('vSoft') : t('vOk');
  const body = !rules ? '' : hard ? t('vHardP') : soft ? t('vSoftP') : t('vOkP');
  const counts = rules ? [hard && `${hard} HARD`, soft && `${soft} SOFT`].filter(Boolean).join(' · ') : '';
  return (
    <div className={`verdict ${kind}`} role="status">
      <span className="ring"><Icon name={icon} /></span>
      <div><h3>{title}{counts && <span className="small muted" style={{ fontFamily: 'var(--f-ui)', marginLeft: 10 }}>{counts}</span>}</h3><p>{body}</p></div>
    </div>
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

  if (err && !d) return <main><a className="crumb" href="#/"><Icon name="back" size={16} />{t('back')}</a><Err e={err} /></main>;
  if (!d) {
    return (
      <main role="status" aria-label={t('loading')}>
        <div className="skel" style={{ height: 16, width: 120 }} />
        <div className="skel" style={{ height: 56, width: 260, margin: '22px 0 14px' }} />
        <div className="skel" style={{ height: 90, marginBottom: 16 }} />
        <div className="scores">{[0, 1, 2].map((i) => <div key={i} className="skel" style={{ height: 160 }} />)}</div>
      </main>
    );
  }
  const { claim, run } = d;
  const reviews = [...d.reviews].sort((a, b) => b.seq - a.seq);
  const rules = [...(run?.rule_results ?? [])].sort((a, b) => rank(a) - rank(b));

  return (
    <main className="detail">
      <a className="crumb noprint" href="#/"><Icon name="back" size={16} />{t('back')}</a>
      <header className="dhead">
        <div>
          <span className="eyebrow">{t('claim')}</span>
          <h2 className="mono">{claim.claim_id}</h2>
          <div className="meta">
            <span className="pill"><Icon name={productIcon(claim.product)} size={15} />{productLabel(claim.product)}</span>
            <span className="pill mono">{claim.recycler_party_id}</span>
            <span className="pill">{fmtDate(claim.period_start)} → {fmtDate(claim.period_end)}</span>
            {run && <span className="pill" title={run.run_id}><Icon name="refresh" size={14} />{fmtDateTime(run.ran_at)}</span>}
          </div>
        </div>
        <div className="actions noprint">
          {session?.role !== 'RECYCLER' && (
            <label className="toggle"><input type="checkbox" checked={recView} onChange={(e) => setRecView(e.target.checked)} /> {t('recyclerView')}</label>
          )}
          <button className="btn secondary" onClick={() => window.print()}><Icon name="print" />{t('print')}</button>
          {isAuditor && <button className="btn" disabled={busy} onClick={() => act(() => runCheck(id, d?.run?.ran_at))}><Icon name="refresh" />{busy ? t('running') : t('runClaimGuard')}</button>}
        </div>
      </header>
      <Err e={err} />
      {recView && (
        <div className="callout recview" role="note">
          <strong>{t('recyclerView')}.</strong> This is what the recycler sees: the same rule results, sources and review trail, without the reviewer controls.
        </div>
      )}

      <Verdict rules={run ? run.rule_results : null} />
      {run ? <ScoreBars scores={run.scores} /> : <p className="empty">ClaimGuard has not run on this claim yet. {isAuditor && 'Use Run ClaimGuard.'}</p>}
      <p className="disclaimer"><Icon name="shield" />{DISCLAIMER}</p>

      <div className="section-h"><h2>{t('ruleResults')}</h2><span className="count">{rules.length}</span></div>
      <div className="rules">{rules.map((r) => <RuleCard key={r.rule_id} r={r} sources={d.sources} />)}</div>

      <div className="section-h"><h2>{t('evidence')}</h2><span className="count">{d.evidence.length}</span></div>
      {d.evidence.length ? <ul className="evlist">{d.evidence.map((e) => <EvidenceItem key={e.evidence_id} ev={e} />)}</ul> : <p className="empty">No evidence attached to this claim.</p>}

      <div className="section-h">
        <h2>{t('batches')}</h2>
        {d.lineage.nodes.length > 0 && (
          <button className="btn ghost noprint" style={{ minHeight: 34, marginLeft: 'auto' }} aria-expanded={showLineage} onClick={() => setShowLineage((x) => !x)}>{showLineage ? 'Hide' : 'Show'} lineage</button>
        )}
      </div>
      {showLineage && <Suspense fallback={<div className="skel" style={{ height: 200 }} />}><LineageView lineage={d.lineage} /></Suspense>}

      <div className="section-h"><h2>{t('trail')}</h2><span className="count">{reviews.length}</span></div>
      {reviews.length ? (
        <ol className="trail">
          {reviews.map((r) => (
            <li key={r.seq}>
              <strong>{ACTION_WORD[r.action]}</strong> <span className="small muted">by {r.by_party_id} ({r.by_role.toLowerCase()}) · {fmtDateTime(r.at)}</span>
              {r.note && <p>{r.note}</p>}
            </li>
          ))}
        </ol>
      ) : <p className="empty">{t('noTrail')}</p>}

      {isAuditor && !recView && (
        <section className="review noprint" aria-label="Reviewer actions">
          <label htmlFor="note">{t('note')}</label>
          <textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you check, and what should happen next?" />
          <div className="row">
            <button className="btn green" disabled={busy} onClick={() => review('ACCEPT', note, () => setNote(''))}><Icon name="check" />{t('accept')}</button>
            <button className="btn secondary" disabled={busy} onClick={() => review('REQUEST_EVIDENCE', note, () => setNote(''))}><Icon name="clip" />{t('request')}</button>
            <button className="btn secondary" disabled={busy} onClick={() => review('ESCALATE', note, () => setNote(''))}><Icon name="alert" />{t('escalate')}</button>
          </div>
        </section>
      )}
      {recView && (
        <section className="review noprint" aria-label="Recycler response">
          <label htmlFor="resp">{t('respond')}</label>
          <textarea id="resp" value={resp} onChange={(e) => setResp(e.target.value)} disabled={session?.role !== 'RECYCLER'} />
          {session?.role !== 'RECYCLER' && <p className="small muted">Only the owning recycler can send a response. Switch the role to REC-01 to try it.</p>}
          <button className="btn" disabled={busy || session?.role !== 'RECYCLER' || !resp.trim()} onClick={() => review('RECYCLER_RESPONSE', resp, () => setResp(''))}><Icon name="send" />{t('sendResponse')}</button>
        </section>
      )}
    </main>
  );
}
