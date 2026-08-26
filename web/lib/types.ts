export type SourceStatus = {
  source: string;
  status: string;
  message?: string | null;
  checked_at?: string | null;
};

export type OftenWith = {
  id: string;
  title: string;
  overlap_pct: number;
};

export type StanceMix = {
  postpone: number;
  abandon: number;
  bookmark_only: number;
  unclear: number;
};

export type BehaviorCard = {
  id: string;
  title: string;
  family?: string;
  family_label?: string;
  emergent?: boolean;
  didnt_buy_pct: number;
  n: number;
  voices: number;
  mechanism: string;
  intensity: number;
  w2p_stage: string;
  stance_mix: StanceMix;
  source_mix: Record<string, number>;
  often_with: OftenWith[];
  caption?: string;
  quotes?: Quote[];
  levers?: string[];
  unit_ids?: number[];
  header?: BehaviorsHeader;
};

export type Quote = {
  text: string;
  unit_id?: number;
  source?: string;
  url?: string | null;
  confidence?: number;
};

export type BehaviorsHeader = {
  analyzed: number;
  voices: number;
  stance_mix: StanceMix;
  source_status: SourceStatus[];
  last_coded_at?: string | null;
  computed_at?: string | null;
  caption?: string;
  chips?: { id: string; label: string }[];
};

export type BehaviorsResponse = {
  caption: string;
  from_cache?: boolean;
  header: BehaviorsHeader;
  behaviors: BehaviorCard[];
  primary_share_sum: number;
};

export type UnitsResponse = {
  total: number;
  limit: number;
  offset: number;
  caption: string;
  units: UnitRow[];
};

export type UnitRow = {
  id: number;
  source: string;
  source_id: string;
  url?: string | null;
  created_at?: string | null;
  snippet: string;
  primary_barrier: string;
  behavior_id: string;
  behavior_title: string;
  outcome_stance: string;
  intensity: number;
  w2p_stage: string;
  confidence: number;
};

export type UnitDetail = {
  id: number;
  source: string;
  source_id: string;
  url?: string | null;
  created_at?: string | null;
  text: string;
  relevance_status?: string | null;
  coded_at?: string | null;
  code?: Record<string, unknown> | null;
  caption?: string;
};
