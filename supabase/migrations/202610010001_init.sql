-- Hermes cloud reset migration.
-- Destructive: drops all public-schema tables, then recreates Hermes tables only.
-- Does not touch auth, storage, or non-public schemas.

do $$
declare
  r record;
begin
  for r in
    select schemaname, tablename
    from pg_tables
    where schemaname = 'public'
  loop
    execute format('drop table if exists %I.%I cascade', r.schemaname, r.tablename);
  end loop;
end $$;

create table public.runs (
  id uuid primary key,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null,
  metadata jsonb not null default '{}'::jsonb
);

create table public.evidence (
  id text primary key,
  run_id uuid not null references public.runs(id) on delete cascade,
  source text not null,
  event_type text not null,
  content jsonb not null,
  raw_ref text,
  created_at timestamptz not null default now()
);

create table public.findings (
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

create table public.llm_executions (
  id uuid primary key,
  run_id uuid not null references public.runs(id) on delete cascade,
  gateway text not null,
  requested_model text,
  resolved_provider text,
  resolved_model text,
  latency_ms integer,
  created_at timestamptz not null default now()
);

create index if not exists idx_evidence_run_id on public.evidence(run_id);
create index if not exists idx_findings_run_id on public.findings(run_id);
create index if not exists idx_llm_executions_run_id on public.llm_executions(run_id);

alter table public.runs enable row level security;
alter table public.evidence enable row level security;
alter table public.findings enable row level security;
alter table public.llm_executions enable row level security;

create policy deny_all_runs on public.runs for all to public using (false) with check (false);
create policy deny_all_evidence on public.evidence for all to public using (false) with check (false);
create policy deny_all_findings on public.findings for all to public using (false) with check (false);
create policy deny_all_llm_executions on public.llm_executions for all to public using (false) with check (false);

revoke all on public.runs, public.evidence, public.findings, public.llm_executions from anon, authenticated;
grant select, insert, update, delete on public.runs, public.evidence, public.findings, public.llm_executions to service_role;
