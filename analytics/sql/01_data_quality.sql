-- Film Sort analytics data quality checks.
-- All statements are read-only and target public.analytics_events.

-- 1. Check total event volume and event type distribution.
select
  event_name,
  count(*) as event_count,
  count(distinct session_id) as session_count,
  min(created_at) as first_seen_at,
  max(created_at) as last_seen_at
from public.analytics_events
group by event_name
order by event_count desc, event_name;

-- 2. Check daily event volume trend by canonical event name.
with canonical_events as (
  select
    date_trunc('day', created_at)::date as event_date,
    case event_name
      when 'page_view' then 'visit'
      when 'challenge_opened' then 'list_opened'
      when 'ranking_started' then 'sorting_started'
      when 'share_link_copied' then 'share_copied'
      else event_name
    end as canonical_event_name
  from public.analytics_events
)
select
  event_date,
  canonical_event_name,
  count(*) as event_count
from canonical_events
group by event_date, canonical_event_name
order by event_date desc, canonical_event_name;

-- 3a. Check primary key uniqueness.
select
  count(*) as total_rows,
  count(id) as rows_with_id,
  count(distinct id) as distinct_ids,
  count(*) - count(distinct id) as duplicate_id_count
from public.analytics_events;

-- 3b. Check likely duplicate event signatures.
select
  event_name,
  session_id,
  created_at,
  coalesce(challenge_id, '') as challenge_id,
  coalesce(template_id, '') as template_id,
  coalesce(mode, '') as mode,
  count(*) as duplicate_count
from public.analytics_events
group by
  event_name,
  session_id,
  created_at,
  coalesce(challenge_id, ''),
  coalesce(template_id, ''),
  coalesce(mode, '')
having count(*) > 1
order by duplicate_count desc, created_at desc
limit 100;

-- 4. Check null or empty values for core fields.
select
  count(*) as total_rows,
  count(*) filter (where event_name is null or btrim(event_name) = '') as missing_event_name,
  count(*) filter (where created_at is null) as missing_event_time,
  count(*) filter (where session_id is null or btrim(session_id) = '') as missing_session_id,
  count(*) filter (where payload is null) as missing_payload,
  count(*) filter (where payload is not null and jsonb_typeof(payload) <> 'object') as non_object_payload
from public.analytics_events;

-- 5. Check key property availability by canonical event name.
with canonical_events as (
  select
    case event_name
      when 'page_view' then 'visit'
      when 'challenge_opened' then 'list_opened'
      when 'ranking_started' then 'sorting_started'
      when 'share_link_copied' then 'share_copied'
      else event_name
    end as canonical_event_name,
    payload
  from public.analytics_events
)
select
  canonical_event_name,
  count(*) as event_count,
  round(100.0 * count(*) filter (
    where nullif(payload->>'route', '') is null
  ) / nullif(count(*), 0), 2) as missing_route_pct,
  round(100.0 * count(*) filter (
    where nullif(coalesce(payload->>'list_id', payload->>'template_id'), '') is null
  ) / nullif(count(*), 0), 2) as missing_list_or_template_pct,
  round(100.0 * count(*) filter (
    where nullif(coalesce(payload->>'list_size', payload->>'total', payload->>'item_count'), '') is null
  ) / nullif(count(*), 0), 2) as missing_list_size_pct,
  round(100.0 * count(*) filter (
    where nullif(coalesce(payload->>'comparison_count', payload->>'comparisons'), '') is null
  ) / nullif(count(*), 0), 2) as missing_comparison_count_pct,
  round(100.0 * count(*) filter (
    where nullif(payload->>'device_type', '') is null
  ) / nullif(count(*), 0), 2) as missing_device_type_pct,
  round(100.0 * count(*) filter (
    where nullif(coalesce(payload->>'source', payload->>'utm_source'), '') is null
  ) / nullif(count(*), 0), 2) as missing_source_pct
from canonical_events
group by canonical_event_name
order by event_count desc, canonical_event_name;

-- 6. Check sessions that completed ranking without a sorting start in the same session.
with canonical_events as (
  select
    session_id,
    case event_name
      when 'ranking_started' then 'sorting_started'
      else event_name
    end as canonical_event_name
  from public.analytics_events
  where session_id is not null and btrim(session_id) <> ''
),
session_flags as (
  select
    session_id,
    bool_or(canonical_event_name = 'sorting_started') as has_started,
    bool_or(canonical_event_name = 'ranking_completed') as has_completed
  from canonical_events
  group by session_id
)
select
  count(*) as completed_without_started_sessions
from session_flags
where has_completed and not has_started;

-- 7. Check sessions where first completion is earlier than first sorting start.
with canonical_events as (
  select
    session_id,
    created_at,
    case event_name
      when 'ranking_started' then 'sorting_started'
      else event_name
    end as canonical_event_name
  from public.analytics_events
  where session_id is not null and btrim(session_id) <> ''
),
session_times as (
  select
    session_id,
    min(created_at) filter (where canonical_event_name = 'sorting_started') as first_started_at,
    min(created_at) filter (where canonical_event_name = 'ranking_completed') as first_completed_at
  from canonical_events
  group by session_id
)
select
  session_id,
  first_started_at,
  first_completed_at
from session_times
where first_started_at is not null
  and first_completed_at is not null
  and first_completed_at < first_started_at
order by first_completed_at desc
limit 100;

-- 8. Check unusually high-frequency sessions.
select
  session_id,
  count(*) as event_count,
  count(*) filter (where event_name = 'comparison_made') as comparison_event_count,
  min(created_at) as first_seen_at,
  max(created_at) as last_seen_at
from public.analytics_events
where session_id is not null and btrim(session_id) <> ''
group by session_id
having count(*) >= 200
order by event_count desc
limit 100;

-- 9. Review candidate internal-test traffic patterns.
-- Current schema has no dedicated is_internal_test field. These rows are only heuristic candidates.
select
  coalesce(source_channel, payload->>'source', payload->>'utm_source', 'unknown') as source_candidate,
  count(*) as event_count,
  count(distinct session_id) as session_count,
  min(created_at) as first_seen_at,
  max(created_at) as last_seen_at
from public.analytics_events
where lower(coalesce(source_channel, payload->>'source', payload->>'utm_source', '')) similar to '%(test|internal|debug|localhost|local|dev|qa)%'
group by source_candidate
order by event_count desc
limit 100;

-- 10. Preview a session-level base table for later funnel analysis.
with canonical_events as (
  select
    session_id,
    created_at,
    case event_name
      when 'page_view' then 'visit'
      when 'challenge_opened' then 'list_opened'
      when 'ranking_started' then 'sorting_started'
      when 'share_link_copied' then 'share_copied'
      else event_name
    end as canonical_event_name,
    challenge_id,
    template_id,
    mode,
    source_channel,
    payload
  from public.analytics_events
  where session_id is not null and btrim(session_id) <> ''
),
session_base as (
  select
    session_id,
    min(created_at) as first_event_at,
    max(created_at) as last_event_at,
    min(created_at) filter (where canonical_event_name = 'visit') as first_visit_at,
    min(created_at) filter (where canonical_event_name = 'home_content_rendered') as first_home_rendered_at,
    min(created_at) filter (where canonical_event_name in ('list_opened', 'list_selected')) as first_list_action_at,
    min(created_at) filter (where canonical_event_name = 'sorting_started') as first_started_at,
    min(created_at) filter (where canonical_event_name = 'ranking_completed') as first_completed_at,
    min(created_at) filter (where canonical_event_name in ('share_copied', 'poster_downloaded')) as first_share_or_download_at,
    count(*) as total_events,
    count(*) filter (where canonical_event_name = 'comparison_made') as comparison_events,
    max(coalesce(template_id, payload->>'template_id')) as any_template_id,
    max(coalesce(challenge_id, payload->>'list_id')) as any_list_id,
    max(coalesce(mode, payload->>'mode')) as any_mode,
    max(coalesce(source_channel, payload->>'source', payload->>'utm_source')) as any_source,
    max(payload->>'device_type') as any_device_type,
    max(coalesce(payload->>'list_size', payload->>'total', payload->>'item_count')) as any_list_size
  from canonical_events
  group by session_id
)
select
  session_id,
  first_event_at,
  last_event_at,
  first_visit_at,
  first_home_rendered_at,
  first_list_action_at,
  first_started_at,
  first_completed_at,
  first_share_or_download_at,
  total_events,
  comparison_events,
  any_template_id,
  any_list_id,
  any_mode,
  any_source,
  any_device_type,
  any_list_size
from session_base
order by last_event_at desc
limit 100;
