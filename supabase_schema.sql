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
    'home_content_rendered',
    'experiment_exposed',
    'heavy_config_viewed',
    'default_start_clicked',
    'sorting_scope_reduced',
    'result_share_prompt_clicked'
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

-- v3.6 light-list daily ranking and three-day rotation.
-- Run once in the Supabase SQL editor before deploying the app code.

create table if not exists public.light_list_catalog_state (
  template_id text primary key,
  segment text not null check (segment in ('director', 'actor', 'category')),
  status text not null default 'candidate' check (status in ('active', 'candidate')),
  pool_priority int not null default 0,
  display_rank int,
  active_since timestamptz,
  new_until timestamptz,
  last_removed_at timestamptz,
  cooldown_until timestamptz,
  activation_count int not null default 0 check (activation_count >= 0),
  updated_at timestamptz not null default now()
);

create table if not exists public.light_list_daily_stats (
  metric_date date not null,
  template_id text not null references public.light_list_catalog_state(template_id) on delete cascade,
  unique_sessions int not null default 0 check (unique_sessions >= 0),
  computed_at timestamptz not null default now(),
  primary key (metric_date, template_id)
);

create table if not exists public.light_list_rotation_runs (
  run_date date primary key,
  removed_ids jsonb not null default '[]'::jsonb,
  added_ids jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists analytics_events_light_list_daily_idx
on public.analytics_events (
  created_at,
  (coalesce(nullif(payload ->> 'list_id', ''), nullif(template_id, ''), nullif(challenge_id, '')))
)
where event_name in ('list_opened', 'challenge_opened');

create index if not exists light_list_catalog_active_rank_idx
on public.light_list_catalog_state (status, display_rank);

create index if not exists light_list_daily_stats_template_date_idx
on public.light_list_daily_stats (template_id, metric_date desc);

insert into public.light_list_catalog_state (
  template_id, segment, status, pool_priority, display_rank, active_since, activation_count
)
values
  ('douban-top50', 'category', 'active', 1, 1, now(), 1),
  ('nolan', 'director', 'active', 2, 2, now(), 1),
  ('miyazaki', 'director', 'active', 3, 3, now(), 1),
  ('shinkai', 'director', 'active', 4, 4, now(), 1),
  ('chinese-highscore', 'category', 'active', 5, 5, now(), 1),
  ('wong-kar-wai', 'director', 'active', 6, 6, now(), 1),
  ('disney-animation', 'category', 'active', 7, 7, now(), 1),
  ('couple-debate', 'category', 'active', 8, 8, now(), 1),
  ('spielberg', 'director', 'candidate', 101, null, null, 0),
  ('tarantino', 'director', 'candidate', 102, null, null, 0),
  ('denis-villeneuve', 'director', 'candidate', 103, null, null, 0),
  ('david-fincher', 'director', 'candidate', 104, null, null, 0),
  ('bong-joon-ho', 'director', 'candidate', 105, null, null, 0),
  ('hirokazu-koreeda', 'director', 'candidate', 106, null, null, 0),
  ('ang-lee', 'director', 'candidate', 107, null, null, 0),
  ('zhang-yimou', 'director', 'candidate', 108, null, null, 0),
  ('leonardo-dicaprio', 'actor', 'candidate', 201, null, null, 0),
  ('tom-hanks', 'actor', 'candidate', 202, null, null, 0),
  ('cate-blanchett', 'actor', 'candidate', 203, null, null, 0),
  ('denzel-washington', 'actor', 'candidate', 204, null, null, 0),
  ('tony-leung', 'actor', 'candidate', 205, null, null, 0),
  ('maggie-cheung', 'actor', 'candidate', 206, null, null, 0),
  ('song-kang-ho', 'actor', 'candidate', 207, null, null, 0),
  ('zhou-xun', 'actor', 'candidate', 208, null, null, 0),
  ('classic-scifi', 'category', 'candidate', 301, null, null, 0),
  ('courtroom', 'category', 'candidate', 302, null, null, 0),
  ('heist-crime', 'category', 'candidate', 303, null, null, 0),
  ('coming-of-age', 'category', 'candidate', 304, null, null, 0),
  ('horror', 'category', 'candidate', 305, null, null, 0),
  ('world-animation', 'category', 'candidate', 306, null, null, 0),
  ('musical', 'category', 'candidate', 307, null, null, 0),
  ('sports', 'category', 'candidate', 308, null, null, 0)
on conflict (template_id) do update
set
  segment = excluded.segment,
  pool_priority = excluded.pool_priority,
  updated_at = now();

-- Existing v3.6 installations started with eight active lists. Promote the
-- highest-priority eligible candidates once so both fresh and upgraded rosters
-- contain nine entries without resetting any prior rotation state.
do $$
declare
  v_missing int;
  v_next_rank int;
  v_template_id text;
begin
  select greatest(0, 9 - count(*))::int
  into v_missing
  from public.light_list_catalog_state
  where status = 'active';

  if v_missing > 0 then
    update public.light_list_catalog_state
    set display_rank = coalesce(display_rank, 0) + v_missing,
        updated_at = now()
    where status = 'active';
  end if;

  v_next_rank := 0;

  for v_template_id in
    select catalog.template_id
    from public.light_list_catalog_state as catalog
    where catalog.status = 'candidate'
      and (catalog.cooldown_until is null or catalog.cooldown_until <= now())
    order by
      case when catalog.activation_count = 0 then 0 else 1 end,
      catalog.last_removed_at asc nulls first,
      catalog.pool_priority asc,
      catalog.template_id asc
    limit v_missing
  loop
    v_next_rank := v_next_rank + 1;
    update public.light_list_catalog_state
    set
      status = 'active',
      display_rank = v_next_rank,
      active_since = now(),
      new_until = now() + interval '24 hours',
      cooldown_until = null,
      activation_count = activation_count + 1,
      updated_at = now()
    where template_id = v_template_id;
  end loop;
end;
$$;

insert into public.light_list_rotation_runs (run_date, removed_ids, added_ids)
values (
  case
    when (timezone('Asia/Shanghai', now()))::time >= time '03:00'
      then (timezone('Asia/Shanghai', now()))::date - 1
    else (timezone('Asia/Shanghai', now()))::date - 2
  end,
  '[]'::jsonb,
  '[]'::jsonb
)
on conflict (run_date) do nothing;

alter table public.light_list_catalog_state enable row level security;
alter table public.light_list_daily_stats enable row level security;
alter table public.light_list_rotation_runs enable row level security;

revoke all on public.light_list_catalog_state from anon, authenticated;
revoke all on public.light_list_daily_stats from anon, authenticated;
revoke all on public.light_list_rotation_runs from anon, authenticated;

create or replace function public.get_home_light_list_roster()
returns table (
  template_id text,
  display_rank int,
  yesterday_sessions int,
  three_day_sessions int,
  is_new boolean,
  last_rotation_date date,
  next_rotation_date date,
  data_updated_at timestamptz
)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_now timestamptz := now();
  v_beijing_now timestamp := timezone('Asia/Shanghai', now());
  v_metric_date date;
  v_last_metric_date date;
  v_start_date date;
  v_date date;
  v_last_rotation_date date;
  v_removed_ids text[] := array[]::text[];
  v_added_ids text[] := array[]::text[];
  v_segment text;
  v_candidate text;
  v_data_updated_at timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('film_sort_light_list_maintenance'));

  v_metric_date := case
    when v_beijing_now::time >= time '03:00' then v_beijing_now::date - 1
    else v_beijing_now::date - 2
  end;

  select max(s.metric_date)
  into v_last_metric_date
  from public.light_list_daily_stats s;

  -- Once this metric date has been settled, keep the persisted roster and
  -- display_rank unchanged. Later calls only read the small state tables.
  if v_last_metric_date is null or v_last_metric_date < v_metric_date then
  if v_last_metric_date is null then
    v_start_date := v_metric_date - 2;
  else
    v_start_date := greatest(v_last_metric_date + 1, v_metric_date - 29);
  end if;

  if v_start_date <= v_metric_date then
    for v_date in
      select day_value::date
      from generate_series(v_start_date::timestamp, v_metric_date::timestamp, interval '1 day') as day_value
    loop
      insert into public.light_list_daily_stats (metric_date, template_id, unique_sessions, computed_at)
      select
        v_date,
        catalog.template_id,
        count(distinct nullif(events.session_id, ''))::int,
        v_now
      from public.light_list_catalog_state as catalog
      left join public.analytics_events as events
        on events.event_name in ('list_opened', 'challenge_opened')
       and events.created_at >= (v_date::timestamp at time zone 'Asia/Shanghai')
       and events.created_at < ((v_date + 1)::timestamp at time zone 'Asia/Shanghai')
       and coalesce(
             nullif(events.payload ->> 'list_id', ''),
             nullif(events.template_id, ''),
             nullif(events.challenge_id, '')
           ) = catalog.template_id
      group by catalog.template_id
      on conflict on constraint light_list_daily_stats_pkey do update
      set
        unique_sessions = excluded.unique_sessions,
        computed_at = excluded.computed_at;
    end loop;
  end if;

  select max(runs.run_date)
  into v_last_rotation_date
  from public.light_list_rotation_runs as runs;

  if v_last_rotation_date is null then
    insert into public.light_list_rotation_runs (run_date, removed_ids, added_ids)
    values (v_metric_date, '[]'::jsonb, '[]'::jsonb)
    on conflict (run_date) do nothing;
    v_last_rotation_date := v_metric_date;
  end if;

  if v_metric_date >= v_last_rotation_date + 3 then
    select coalesce(
      array_agg(
        ranked.template_id
        order by ranked.three_day_sessions asc,
                 ranked.yesterday_sessions asc,
                 ranked.active_since asc,
                 ranked.template_id asc
      ),
      array[]::text[]
    )
    into v_removed_ids
    from (
      select
        catalog.template_id,
        catalog.active_since,
        coalesce(sum(stats.unique_sessions), 0)::int as three_day_sessions,
        coalesce(max(stats.unique_sessions) filter (where stats.metric_date = v_metric_date), 0)::int as yesterday_sessions
      from public.light_list_catalog_state as catalog
      left join public.light_list_daily_stats as stats
        on stats.template_id = catalog.template_id
       and stats.metric_date between v_metric_date - 2 and v_metric_date
      where catalog.status = 'active'
        and (catalog.new_until is null or catalog.new_until <= v_now)
        and catalog.active_since is not null
        and (timezone('Asia/Shanghai', catalog.active_since))::date <= v_metric_date - 2
      group by catalog.template_id, catalog.active_since
      order by three_day_sessions asc, yesterday_sessions asc, catalog.active_since asc, catalog.template_id asc
      limit 3
    ) as ranked;

    if cardinality(v_removed_ids) = 3 then
      foreach v_segment in array array['director', 'actor', 'category']
      loop
        v_candidate := null;
        select catalog.template_id
        into v_candidate
        from public.light_list_catalog_state as catalog
        where catalog.status = 'candidate'
          and catalog.segment = v_segment
          and (catalog.cooldown_until is null or catalog.cooldown_until <= v_now)
          and not (catalog.template_id = any(v_added_ids))
        order by
          case when catalog.activation_count = 0 then 0 else 1 end,
          catalog.last_removed_at asc nulls first,
          catalog.pool_priority asc,
          catalog.template_id asc
        limit 1;

        if v_candidate is not null then
          v_added_ids := array_append(v_added_ids, v_candidate);
        end if;
      end loop;

      while cardinality(v_added_ids) < 3 loop
        v_candidate := null;
        select catalog.template_id
        into v_candidate
        from public.light_list_catalog_state as catalog
        where catalog.status = 'candidate'
          and (catalog.cooldown_until is null or catalog.cooldown_until <= v_now)
          and not (catalog.template_id = any(v_added_ids))
        order by
          case when catalog.activation_count = 0 then 0 else 1 end,
          catalog.last_removed_at asc nulls first,
          catalog.pool_priority asc,
          catalog.template_id asc
        limit 1;

        exit when v_candidate is null;
        v_added_ids := array_append(v_added_ids, v_candidate);
      end loop;
    end if;

    if cardinality(v_removed_ids) = 3 and cardinality(v_added_ids) = 3 then
      update public.light_list_catalog_state as catalog
      set
        status = 'candidate',
        display_rank = null,
        new_until = null,
        last_removed_at = v_now,
        cooldown_until = v_now + interval '21 days',
        updated_at = v_now
      where catalog.template_id = any(v_removed_ids);

      update public.light_list_catalog_state as catalog
      set
        status = 'active',
        display_rank = array_position(v_added_ids, catalog.template_id),
        active_since = v_now,
        new_until = v_now + interval '24 hours',
        cooldown_until = null,
        activation_count = catalog.activation_count + 1,
        updated_at = v_now
      where catalog.template_id = any(v_added_ids);

      insert into public.light_list_rotation_runs (run_date, removed_ids, added_ids, created_at)
      values (v_metric_date, to_jsonb(v_removed_ids), to_jsonb(v_added_ids), v_now)
      on conflict (run_date) do nothing;

      v_last_rotation_date := v_metric_date;
    end if;
  end if;

  with active_scores as (
    select
      catalog.template_id,
      row_number() over (
        order by
          case when catalog.new_until > v_now then 0 else 1 end,
          case when catalog.new_until > v_now then catalog.display_rank end asc nulls last,
          case when not (catalog.new_until > v_now) then coalesce(yesterday.unique_sessions, 0) end desc nulls last,
          catalog.display_rank asc nulls last,
          catalog.template_id asc
      )::int as new_rank
    from public.light_list_catalog_state as catalog
    left join public.light_list_daily_stats as yesterday
      on yesterday.template_id = catalog.template_id
     and yesterday.metric_date = v_metric_date
    where catalog.status = 'active'
  )
  update public.light_list_catalog_state as catalog
  set
    display_rank = active_scores.new_rank,
    updated_at = v_now
  from active_scores
  where catalog.template_id = active_scores.template_id;
  end if;

  select max(runs.run_date)
  into v_last_rotation_date
  from public.light_list_rotation_runs as runs;

  select max(stats.computed_at)
  into v_data_updated_at
  from public.light_list_daily_stats as stats
  where stats.metric_date = v_metric_date;

  return query
  select
    catalog.template_id,
    catalog.display_rank,
    coalesce(yesterday.unique_sessions, 0)::int as yesterday_sessions,
    coalesce(sum(recent.unique_sessions), 0)::int as three_day_sessions,
    (catalog.new_until > v_now) as is_new,
    v_last_rotation_date,
    v_last_rotation_date + 3,
    v_data_updated_at
  from public.light_list_catalog_state as catalog
  left join public.light_list_daily_stats as yesterday
    on yesterday.template_id = catalog.template_id
   and yesterday.metric_date = v_metric_date
  left join public.light_list_daily_stats as recent
    on recent.template_id = catalog.template_id
   and recent.metric_date between v_metric_date - 2 and v_metric_date
  where catalog.status = 'active'
  group by
    catalog.template_id,
    catalog.display_rank,
    catalog.new_until,
    yesterday.unique_sessions
  order by catalog.display_rank asc, catalog.template_id asc;
end;
$$;

create or replace function public.read_home_light_list_roster()
returns table (
  template_id text,
  display_rank int,
  yesterday_sessions int,
  three_day_sessions int,
  is_new boolean,
  last_rotation_date date,
  next_rotation_date date,
  data_updated_at timestamptz
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  with metric_context as (
    select max(stats.metric_date) as metric_date
    from public.light_list_daily_stats as stats
  ),
  rotation_context as (
    select max(runs.run_date) as last_rotation_date
    from public.light_list_rotation_runs as runs
  ),
  updated_context as (
    select max(stats.computed_at) as data_updated_at
    from public.light_list_daily_stats as stats
    cross join metric_context
    where stats.metric_date = metric_context.metric_date
  )
  select
    catalog.template_id,
    catalog.display_rank,
    coalesce(yesterday.unique_sessions, 0)::int as yesterday_sessions,
    coalesce(sum(recent.unique_sessions), 0)::int as three_day_sessions,
    (catalog.new_until > now()) as is_new,
    rotation_context.last_rotation_date,
    rotation_context.last_rotation_date + 3 as next_rotation_date,
    updated_context.data_updated_at
  from public.light_list_catalog_state as catalog
  cross join metric_context
  cross join rotation_context
  cross join updated_context
  left join public.light_list_daily_stats as yesterday
    on yesterday.template_id = catalog.template_id
   and yesterday.metric_date = metric_context.metric_date
  left join public.light_list_daily_stats as recent
    on recent.template_id = catalog.template_id
   and recent.metric_date between metric_context.metric_date - 2 and metric_context.metric_date
  where catalog.status = 'active'
  group by
    catalog.template_id,
    catalog.display_rank,
    catalog.new_until,
    yesterday.unique_sessions,
    rotation_context.last_rotation_date,
    updated_context.data_updated_at
  order by catalog.display_rank asc, catalog.template_id asc;
$$;

create or replace function public.get_light_list_rotation_history(p_limit int default 12)
returns table (
  run_date date,
  removed_ids jsonb,
  added_ids jsonb,
  created_at timestamptz
)
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select runs.run_date, runs.removed_ids, runs.added_ids, runs.created_at
  from public.light_list_rotation_runs as runs
  where jsonb_array_length(runs.removed_ids) > 0
     or jsonb_array_length(runs.added_ids) > 0
  order by runs.run_date desc
  limit greatest(1, least(coalesce(p_limit, 12), 50));
$$;

revoke all on function public.get_home_light_list_roster() from public;
revoke all on function public.read_home_light_list_roster() from public;
revoke all on function public.get_light_list_rotation_history(int) from public;
grant execute on function public.get_home_light_list_roster() to anon, authenticated;
grant execute on function public.read_home_light_list_roster() to anon, authenticated;
grant execute on function public.get_light_list_rotation_history(int) to anon, authenticated;
