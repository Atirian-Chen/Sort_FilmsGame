-- Read-only checks for v3.6 light-list automatic maintenance.

select
  count(*) as catalog_count,
  count(*) filter (where status = 'active') as active_count,
  count(*) filter (where status = 'candidate') as candidate_count,
  count(*) filter (where status = 'active') = 9 as active_count_ok
from public.light_list_catalog_state;

select segment, status, count(*) as list_count
from public.light_list_catalog_state
group by segment, status
order by segment, status;

select display_rank, count(*) as duplicate_count
from public.light_list_catalog_state
where status = 'active'
group by display_rank
having count(*) > 1;

select *
from public.get_home_light_list_roster();

select *
from public.get_light_list_rotation_history(12);

select
  metric_date,
  count(*) as template_rows,
  sum(unique_sessions) as total_unique_template_sessions,
  max(computed_at) as computed_at
from public.light_list_daily_stats
group by metric_date
order by metric_date desc
limit 30;

select
  timezone('Asia/Shanghai', now()) as beijing_now,
  case
    when (timezone('Asia/Shanghai', now()))::time >= time '03:00'
      then (timezone('Asia/Shanghai', now()))::date - 1
    else (timezone('Asia/Shanghai', now()))::date - 2
  end as current_metric_date;
