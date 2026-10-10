export type Outcome = 'PASS' | 'FLAG' | 'INSUFFICIENT_EVIDENCE' | 'INCONCLUSIVE';
export type Severity = 'HARD' | 'SOFT' | 'NONE';
export type Role = 'AUDITOR' | 'RECYCLER' | 'PRODUCER';
export type Confirmation = 'BOTH_PARTIES_CONFIRMED' | 'HANDLER_CONFIRMED' | 'BUYER_REPORTED' | null;
export type ReviewAction = 'ACCEPT' | 'REQUEST_EVIDENCE' | 'ESCALATE' | 'RECYCLER_RESPONSE';

export interface ClaimRow {
  claim_id: string; recycler_party_id: string; product: string; period_start: string; period_end: string;
  flags: { hard: number; soft: number }; has_run: boolean; coverage: number | null; last_run_at: string | null;
}
export interface RuleResult {
  rule_id: string; rule_version?: string; outcome: Outcome; severity: Severity;
  observed: unknown; limit: unknown; formula_rendered: string;
  evidence_ids: string[]; source_ids: string[]; demo_value: boolean; next_action: string | null;
}
export interface Scores {
  physical_consistency: number | null; physical_capped_by_hard_flag: boolean;
  traceability_coverage: number | null; covered_kg: number; claimed_kg: number;
  evidence_quality: { handler_confirmed: number; same_device_confirmed: number; buyer_reported: number };
  evidence_rules: Record<string, string>;
}
export interface Run { run_id: string; ran_at: string; rule_results: RuleResult[]; scores: Scores }
export interface Evidence {
  evidence_id: string; kind: string; sha256?: string; phash?: string | null; exif: Record<string, unknown>;
  extracted: Record<string, unknown>; received_at_server?: string; batch_id?: string | null;
}
export interface FieldStatus { status: string; channel: string }
export interface LineageEvent {
  seq: number; type: string; at_server: string; actor_party_id: string; weight_kg: number | null; basis: string | null;
  confirmation: Confirmation; fields: Record<string, FieldStatus>; evidence_ids: string[];
}
export interface LineageNode { batch_id: string; material: string; status: string; events: LineageEvent[] }
export interface Lineage {
  root_batch_ids: string[]; nodes: LineageNode[]; edges: { from: string; to: string; kind: string; weight_kg: number | null }[];
}
export interface Review { seq: number; action: ReviewAction; note: string | null; by_party_id: string; by_role: string; at: string }
export interface Source {
  id: string; title: string; status: 'CITED' | 'DEMO_VALUE'; date: string | null; locator: string | null; url: string | null;
  value: unknown; note: string | null; demo_value: boolean;
}
export interface ClaimDetail {
  claim: Record<string, unknown> & { claim_id: string; recycler_party_id: string; product: string; period_start: string; period_end: string };
  run: Run | null; evidence: Evidence[]; lineage: Lineage; reviews: Review[]; sources: Record<string, Source>;
}
export interface Metric { id: string; label: string; value: number; unit: string; source_ids: string[]; demo_value: boolean; note: string }
