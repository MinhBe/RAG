-- Draft only. Do not apply until the target Supabase project is confirmed.
create table if not exists public.runs (
  id uuid primary key,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null,
  metadata jsonb not null default '{}'::jsonb
);
create table if not exists public.evidence (
  id text primary key,
  run_id uuid not null references public.runs(id) on delete cascade,
  source text not null,
  event_type text not null,
  content jsonb not null,
  raw_ref text,
  created_at timestamptz not null default now()
);
create table if not exists public.findings (
  id text primary key,
  run_id uuid not null references public.runs(id) on delete cascade,
  severity text not null,
  disposition text not null,
  title text not null,
  evidence_refs text[] not null,
  analysis jsonb not null default '{}'::jsonb,
  validation_status text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.llm_executions (
  id uuid primary key,
  run_id uuid not null references public.runs(id) on delete cascade,
  gateway text not null,
  requested_model text,
  resolved_provider text,
  resolved_model text,
  latency_ms integer,
  created_at timestamptz not null default now()
);
alter table public.runs enable row level security;
alter table public.evidence enable row level security;
alter table public.findings enable row level security;
alter table public.llm_executions enable row level security;
revoke all on public.runs, public.evidence, public.findings, public.llm_executions from anon, authenticated;
grant select, insert, update, delete on public.runs, public.evidence, public.findings, public.llm_executions to service_role;
-- Vector columns are intentionally deferred until the embedding model and exact dimension are locked.
