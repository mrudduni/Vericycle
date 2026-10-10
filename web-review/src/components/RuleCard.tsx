import { useState } from 'react';
import { useT } from '../lib/i18n';
import type { RuleResult, Source } from '../lib/types';
import { DemoBadge, OutcomeChip, SourceChip, fmtNum, outcomeInfo } from './ui';

const RULE_NAME: Record<string, string> = {
  R1: 'Plant capacity', R2a: 'Mass balance', R2b: 'Output yield', R3: 'Energy use', R4: 'Chain of custody',
  R5: 'Photo light and time', R6: 'Duplicate photos', R7: 'Documents', R8: 'Weight drift',
};

export default function RuleCard({ r, sources }: { r: RuleResult; sources: Record<string, Source> }) {
  const t = useT();
  const [erratum, setErratum] = useState(false);
  const needsAction = r.outcome === 'INSUFFICIENT_EVIDENCE' || r.outcome === 'INCONCLUSIVE';
  const info = outcomeInfo(r.outcome);
  return (
    <article className={`rule ${r.outcome.toLowerCase()} ${r.outcome === 'FLAG' ? r.severity.toLowerCase() : ''}`} aria-labelledby={`rule-${r.rule_id}`} data-rule={r.rule_id} data-outcome={r.outcome}>
      <header>
        <h3 id={`rule-${r.rule_id}`}><span className="mono">{r.rule_id}</span> {RULE_NAME[r.rule_id] ?? ''}</h3>
        <OutcomeChip outcome={r.outcome} severity={r.severity} />
        {r.demo_value && <DemoBadge />}
      </header>
      <p className="small muted">{info.plain}. {t('severity')}: <strong>{r.severity}</strong></p>
      <dl className="obs">
        <div><dt>{t('observed')}</dt><dd>{fmtNum(r.observed)}</dd></div>
        <div><dt>{t('limit')}</dt><dd>{fmtNum(r.limit)}</dd></div>
      </dl>
      <p className="formula mono">{r.formula_rendered}</p>
      {r.rule_id === 'R1' && (
        <div>
          <button type="button" className="btn secondary" aria-expanded={erratum} aria-controls="erratum" onClick={() => setErratum((x) => !x)}>
            {erratum ? t('hideErratum') : t('showErratum')}
          </button>
          {erratum && (
            <div id="erratum" className="callout erratum" role="note">
              <strong>CPCB erratum.</strong> The CPCB worked example prints <span className="mono">46,200 t</span>. The correct product of
              20 x 4 x 330 is <span className="mono">26,400 t</span>. ClaimGuard uses the correct arithmetic.
            </div>
          )}
        </div>
      )}
      {needsAction && (
        <div className="callout resolve"><strong>{t('resolve')}</strong><p>{r.next_action ?? 'The rule gave no specific next step. Ask the recycler for more evidence, or escalate for review.'}</p></div>
      )}
      {r.outcome === 'FLAG' && r.next_action && <p className="small"><strong>Next step:</strong> {r.next_action}</p>}
      {(r.source_ids.length > 0 || r.evidence_ids.length > 0) && (
        <footer>
          {r.source_ids.map((s) => <SourceChip key={s} id={s} sources={sources} />)}
          {r.evidence_ids.map((e) => <button type="button" key={e} className="chip ev mono" onClick={() => document.getElementById(`evidence-${e}`)?.scrollIntoView({ block: 'center' })}>{e}</button>)}
        </footer>
      )}
    </article>
  );
}
