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

create table if not exists public.imported_movie_lists (
  id text primary key,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '7 days'),
  source text not null default 'douban_bookmarklet',
  item_count int not null default 0,
  items jsonb not null,
  use_count int not null default 0
);

create table if not exists public.peer_match_contacts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  session_id text,
  contact text not null,
  list_kind text not null,
  list_key text not null default '',
  challenge_id text,
  template_id text,
  mode text,
  champion text not null,
  top_items jsonb not null default '[]'::jsonb,
  ranked_count int not null default 0,
  allow_display boolean not null default true
);

create index if not exists analytics_events_created_at_idx on public.analytics_events (created_at desc);
create index if not exists analytics_events_event_name_idx on public.analytics_events (event_name);
create index if not exists analytics_events_challenge_id_idx on public.analytics_events (challenge_id);
create index if not exists analytics_events_template_id_idx on public.analytics_events (template_id);
create index if not exists imported_movie_lists_expires_at_idx on public.imported_movie_lists (expires_at desc);
create index if not exists peer_match_contacts_created_at_idx on public.peer_match_contacts (created_at desc);
create index if not exists peer_match_contacts_light_idx on public.peer_match_contacts (list_kind, list_key, champion, created_at desc);
create index if not exists peer_match_contacts_heavy_idx on public.peer_match_contacts (list_kind, created_at desc);

alter table public.challenge_sets enable row level security;
alter table public.analytics_events enable row level security;
alter table public.imported_movie_lists enable row level security;
alter table public.peer_match_contacts enable row level security;

drop policy if exists "challenge sets are readable" on public.challenge_sets;
drop policy if exists "challenge sets can be created by anon" on public.challenge_sets;
drop policy if exists "analytics events can be inserted by anon" on public.analytics_events;
drop policy if exists "analytics events are readable for app dashboards" on public.analytics_events;
drop policy if exists "imported movie lists can be created by anon" on public.imported_movie_lists;
drop policy if exists "imported movie lists are readable before expiry" on public.imported_movie_lists;
drop policy if exists "peer match contacts can be created by anon" on public.peer_match_contacts;
drop policy if exists "peer match contacts are readable when allowed" on public.peer_match_contacts;

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
    'share_link_copied',
    'visit',
    'list_opened',
    'list_selected',
    'sorting_started',
    'comparison_made',
    'share_copied',
    'result_viewed',
    'qr_viewed',
    'home_content_rendered'
  )
);

create policy "analytics events are readable for app dashboards"
on public.analytics_events for select
to anon
using (true);

create policy "imported movie lists can be created by anon"
on public.imported_movie_lists for insert
to anon
with check (
  id ~ '^db-[a-z0-9]{12,32}$'
  and source in ('douban_bookmarklet')
  and item_count between 2 and 1500
  and jsonb_typeof(items) = 'array'
  and jsonb_array_length(items) between 2 and 1500
);

create policy "imported movie lists are readable before expiry"
on public.imported_movie_lists for select
to anon
using (expires_at > now());

create policy "peer match contacts can be created by anon"
on public.peer_match_contacts for insert
to anon
with check (
  allow_display = true
  and list_kind in ('light', 'heavy')
  and length(contact) between 2 and 80
  and length(champion) between 1 and 120
  and ranked_count between 1 and 1500
  and jsonb_typeof(top_items) = 'array'
  and jsonb_array_length(top_items) between 1 and 20
);

create policy "peer match contacts are readable when allowed"
on public.peer_match_contacts for select
to anon
using (allow_display = true);
