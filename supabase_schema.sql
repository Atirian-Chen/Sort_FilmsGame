-- Film Sort Ranker / 电影审美名片
-- Run this in the Supabase SQL editor before deploying the public app.

create table if not exists public.challenge_sets (
  id text primary key,
  created_at timestamptz not null default now(),
  theme text not null,
  mode text not null,
  items jsonb not null,
  top_k int,
  seed_text text,
  source text,
  use_count int not null default 0
);

create table if not exists public.analytics_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  event_name text not null,
  session_id text,
  challenge_id text,
  mode text,
  template_id text,
  source_channel text,
  payload jsonb not null default '{}'::jsonb
);

create index if not exists analytics_events_created_at_idx on public.analytics_events (created_at desc);
create index if not exists analytics_events_event_name_idx on public.analytics_events (event_name);
create index if not exists analytics_events_challenge_id_idx on public.analytics_events (challenge_id);
create index if not exists analytics_events_template_id_idx on public.analytics_events (template_id);

alter table public.challenge_sets enable row level security;
alter table public.analytics_events enable row level security;

drop policy if exists "challenge sets are readable" on public.challenge_sets;
drop policy if exists "challenge sets can be created by anon" on public.challenge_sets;
drop policy if exists "analytics events can be inserted by anon" on public.analytics_events;
drop policy if exists "analytics events are readable for app dashboards" on public.analytics_events;

create policy "challenge sets are readable"
on public.challenge_sets for select
to anon
using (true);

create policy "challenge sets can be created by anon"
on public.challenge_sets for insert
to anon
with check (jsonb_array_length(items) between 2 and 300);

create policy "analytics events can be inserted by anon"
on public.analytics_events for insert
to anon
with check (
  event_name in (
    'page_view',
    'challenge_opened',
    'ranking_started',
    'ranking_completed',
    'poster_downloaded',
    'share_link_copied'
  )
);

create policy "analytics events are readable for app dashboards"
on public.analytics_events for select
to anon
using (true);
